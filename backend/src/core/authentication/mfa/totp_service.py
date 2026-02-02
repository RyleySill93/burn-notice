import base64
import secrets
from datetime import datetime
from io import BytesIO
from typing import List, Tuple

import pyotp
import qrcode

from src.common.nanoid import NanoIdType
from src.core.authentication.constants import MFAMethodTypeEnum
from src.core.authentication.domains import MFASecretCreate, MFASecretRead
from src.core.authentication.models import MFASecret
from src.network.database.repository.exceptions import RepositoryObjectNotFound


class TOTPService:
    """Service for managing TOTP-based MFA"""

    # Constants
    def __init__(self):
        from src import settings

        self.TOTP_ISSUER = settings.COMPANY_NAME  # Appears in authenticator apps

    CODE_DIGITS = 6
    TIME_STEP = 30  # seconds
    BACKUP_CODE_COUNT = 8
    BACKUP_CODE_LENGTH = 10

    @classmethod
    def factory(cls) -> 'TOTPService':
        return cls()

    def generate_secret(self) -> str:
        """
        Generate a new random TOTP secret.
        Returns base32-encoded secret (recommended by RFC 6238).
        """
        return pyotp.random_base32()

    def generate_backup_codes(self) -> List[str]:
        """
        Generate single-use backup codes for account recovery.
        Format: XXXX-XXXX-XX (10 chars, dashed for readability)
        """
        codes = []
        for _ in range(self.BACKUP_CODE_COUNT):
            # Generate random alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(self.BACKUP_CODE_LENGTH))
            # Format with dashes: XXXX-XXXX-XX
            formatted = f'{code[:4]}-{code[4:8]}-{code[8:]}'
            codes.append(formatted)
        return codes

    def create_totp_secret(self, user_id: NanoIdType) -> Tuple[MFASecretRead, str]:
        """
        Create a new TOTP secret for a user (or replace existing unverified one).
        Returns tuple of (secret_record, plain_secret_for_qr).

        Note: If user already has a verified TOTP secret, this should fail.
        Users must disable TOTP before re-enabling with a new secret.
        """
        # Check for existing verified secret
        try:
            _ = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.TOTP,
                MFASecret.is_verified == True,
            )
            raise ValueError('User already has verified TOTP enabled. Disable first.')
        except RepositoryObjectNotFound:
            pass  # Good - no verified secret exists

        # Delete any unverified secrets (abandoned setup)
        try:
            unverified = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.TOTP,
                MFASecret.is_verified == False,
            )
            MFASecret.delete(MFASecret.id == unverified.id)
        except RepositoryObjectNotFound:
            pass

        # Generate new secret and backup codes
        secret = self.generate_secret()
        backup_codes = self.generate_backup_codes()

        # Store in database (encrypted automatically by EncryptedString field)
        totp_record = MFASecret.create(
            MFASecretCreate(
                user_id=user_id,
                mfa_method=MFAMethodTypeEnum.TOTP,
                secret=secret,
                is_verified=False,
                backup_codes=backup_codes,
            )
        )

        return totp_record, secret

    def generate_qr_code(self, secret: str, user_email: str) -> str:
        """
        Generate QR code image for TOTP secret.
        Returns base64-encoded PNG image.
        """
        # Create provisioning URI (otpauth:// format)
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user_email, issuer_name=self.TOTP_ISSUER)

        # Add logo image parameter (supported by some authenticator apps like Authy)
        # Apps that don't support it will simply ignore this parameter
        logo_url = 'https://static.burn_notice.com/logos/icon-128.png'
        uri += f'&image={logo_url}'

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        # Convert to image
        img = qr.make_image(fill_color='black', back_color='white')

        # Convert to base64 string
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return img_str

    def verify_totp_code(self, user_id: NanoIdType, code: str, allow_unverified: bool = False) -> bool:
        """
        Verify a TOTP code for a user.

        Args:
            user_id: User to verify code for
            code: 6-digit TOTP code
            allow_unverified: If True, allows verification of unverified secrets
                             (used during setup flow)

        Returns:
            True if code is valid, False otherwise
        """
        try:
            # Get user's TOTP secret
            filters = [MFASecret.user_id == user_id, MFASecret.mfa_method == MFAMethodTypeEnum.TOTP]
            if not allow_unverified:
                filters.append(MFASecret.is_verified == True)

            totp_record = MFASecret.get(*filters)

            # Verify code with ±1 window (90 second total window)
            totp = pyotp.TOTP(totp_record.secret)
            is_valid = totp.verify(code, valid_window=1)

            if is_valid and totp_record.is_verified:
                # Update last used timestamp for verified secrets
                MFASecret.update(totp_record.id, last_used_at=datetime.utcnow())

            return is_valid

        except RepositoryObjectNotFound:
            return False

    def verify_backup_code(self, user_id: NanoIdType, code: str) -> bool:
        """
        Verify and consume a backup code.
        Backup codes are single-use.

        Returns:
            True if code is valid, False otherwise
        """
        try:
            totp_record = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.TOTP,
                MFASecret.is_verified == True,
            )

            # Normalize code (remove dashes, uppercase)
            normalized_code = code.replace('-', '').upper()

            # Check if code exists in backup codes
            if totp_record.backup_codes:
                for backup_code in totp_record.backup_codes:
                    normalized_backup = backup_code.replace('-', '').upper()
                    if normalized_code == normalized_backup:
                        # Valid code - remove it (single use)
                        updated_codes = [bc for bc in totp_record.backup_codes if bc != backup_code]
                        MFASecret.update(totp_record.id, backup_codes=updated_codes, last_used_at=datetime.utcnow())
                        return True

            return False

        except RepositoryObjectNotFound:
            return False

    def enable_totp(self, user_id: NanoIdType, verification_code: str) -> bool:
        """
        Enable TOTP for a user after verifying setup code.
        Marks the secret as verified.

        Enforces rate limiting: max 5 verification attempts.

        Returns:
            True if verification succeeded and TOTP enabled, False otherwise

        Raises:
            ValueError: If max verification attempts exceeded
        """
        try:
            totp_record = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.TOTP,
                MFASecret.is_verified == False,
            )
        except RepositoryObjectNotFound:
            return False

        # Check rate limiting
        if totp_record.verification_attempts >= 5:
            # Delete the secret - user must start over
            MFASecret.delete(MFASecret.id == totp_record.id)
            raise ValueError('Maximum verification attempts exceeded. Please generate a new TOTP secret.')

        # Verify code against unverified secret
        if self.verify_totp_code(user_id, verification_code, allow_unverified=True):
            # Success - enable TOTP
            MFASecret.update(
                totp_record.id,
                is_verified=True,
                verified_at=datetime.utcnow(),
                verification_attempts=0,  # Reset counter
            )
            return True
        else:
            # Failed - increment counter
            MFASecret.update(totp_record.id, verification_attempts=totp_record.verification_attempts + 1)
            return False

    def disable_totp(self, user_id: NanoIdType) -> bool:
        """
        Disable TOTP for a user.
        Deletes the TOTP secret and backup codes.

        Returns:
            True if TOTP was disabled, False if user didn't have TOTP enabled
        """
        try:
            totp_record = MFASecret.get(MFASecret.user_id == user_id, MFASecret.mfa_method == MFAMethodTypeEnum.TOTP)
            MFASecret.delete(MFASecret.id == totp_record.id)
            return True
        except RepositoryObjectNotFound:
            return False

    def has_totp_enabled(self, user_id: NanoIdType) -> bool:
        """
        Check if user has TOTP enabled (verified secret exists).
        """
        try:
            MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.TOTP,
                MFASecret.is_verified == True,
            )
            return True
        except RepositoryObjectNotFound:
            return False

    def get_totp_info(self, user_id: NanoIdType) -> dict:
        """
        Get TOTP status information for a user (without sensitive data).
        """
        try:
            totp_record = MFASecret.get(MFASecret.user_id == user_id, MFASecret.mfa_method == MFAMethodTypeEnum.TOTP)
            return {
                'enabled': totp_record.is_verified,
                'created_at': totp_record.created_at,
                'verified_at': totp_record.verified_at,
                'last_used_at': totp_record.last_used_at,
                'backup_codes_remaining': len(totp_record.backup_codes or []),
            }
        except RepositoryObjectNotFound:
            return {
                'enabled': False,
                'created_at': None,
                'verified_at': None,
                'last_used_at': None,
                'backup_codes_remaining': 0,
            }
