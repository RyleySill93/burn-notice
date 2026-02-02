import secrets
from datetime import datetime

from src.common.nanoid import NanoIdType
from src.core.authentication.constants import MFAMethodTypeEnum
from src.core.authentication.domains import MFASecretCreate, MFASecretRead
from src.core.authentication.models import MFASecret
from src.network.database.repository.exceptions import RepositoryObjectNotFound
from src.platform.sms import SMS


class SMSService:
    """Service for managing SMS-based MFA"""

    # Constants
    CODE_DIGITS = 6
    CODE_EXPIRY_MINUTES = 10
    MAX_VERIFICATION_ATTEMPTS = 5

    @classmethod
    def factory(cls) -> 'SMSService':
        return cls()

    def generate_verification_code(self) -> str:
        """
        Generate a random 6-digit verification code.
        """
        return ''.join(str(secrets.randbelow(10)) for _ in range(self.CODE_DIGITS))

    def mask_phone_number(self, phone_number: str) -> str:
        """
        Mask phone number for display.
        Example: +18452428261 -> +1******8261
        """
        if len(phone_number) <= 7:
            return phone_number
        # Show country code (+X) and last 4 digits, mask everything else
        return f'{phone_number[:2]}{"*" * (len(phone_number) - 6)}{phone_number[-4:]}'

    def send_verification_code(self, phone_number: str, code: str) -> None:
        """
        Send verification code via SMS.

        Args:
            phone_number: E.164 format phone number
            code: 6-digit verification code
        """
        from src import settings

        message = f'Your {settings.COMPANY_NAME} verification code is: {code}\n\nThis code will expire in {self.CODE_EXPIRY_MINUTES} minutes.'

        sms = SMS(phone_number=phone_number, message=message, sender_id=settings.COMPANY_NAME)
        sms.send()

    def create_sms_secret(self, user_id: NanoIdType, phone_number: str) -> MFASecretRead:
        """
        Create a new SMS MFA secret for a user (or replace existing unverified one).

        Note: If user already has a verified SMS secret, this should fail.
        Users must disable SMS MFA before re-enabling with a new phone number.
        """
        # Check for existing verified secret
        try:
            _ = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.SMS,
                MFASecret.is_verified == True,
            )
            raise ValueError('User already has verified SMS MFA enabled. Disable first.')
        except RepositoryObjectNotFound:
            pass  # Good - no verified secret exists

        # Delete any unverified secrets (abandoned setup)
        try:
            unverified = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.SMS,
                MFASecret.is_verified == False,
            )
            MFASecret.delete(MFASecret.id == unverified.id)
        except RepositoryObjectNotFound:
            pass

        # Generate verification code (no backup codes for SMS - use alternative MFA methods as backup)
        verification_code = self.generate_verification_code()

        # Store in database
        sms_record = MFASecret.create(
            MFASecretCreate(
                user_id=user_id,
                mfa_method=MFAMethodTypeEnum.SMS,
                phone_number=phone_number,
                secret=verification_code,  # Store current verification code temporarily
                is_verified=False,
                backup_codes=None,
            )
        )

        # Send verification code
        self.send_verification_code(phone_number, verification_code)

        return sms_record

    def verify_sms_code(self, user_id: NanoIdType, code: str, allow_unverified: bool = False) -> bool:
        """
        Verify an SMS code for a user.

        Args:
            user_id: User to verify code for
            code: 6-digit SMS code
            allow_unverified: If True, allows verification of unverified secrets
                             (used during setup flow)

        Returns:
            True if code is valid, False otherwise
        """
        try:
            # Get user's SMS secret
            filters = [MFASecret.user_id == user_id, MFASecret.mfa_method == MFAMethodTypeEnum.SMS]
            if not allow_unverified:
                filters.append(MFASecret.is_verified == True)

            sms_record = MFASecret.get(*filters)

            # For verified secrets, we need to generate and send a new code first
            # The secret field stores the current valid verification code
            is_valid = sms_record.secret == code

            if is_valid and sms_record.is_verified:
                # Update last used timestamp for verified secrets
                MFASecret.update(sms_record.id, last_used_at=datetime.utcnow())

            return is_valid

        except RepositoryObjectNotFound:
            return False

    def enable_sms(self, user_id: NanoIdType, verification_code: str) -> bool:
        """
        Enable SMS MFA for a user after verifying setup code.
        Marks the secret as verified.

        Enforces rate limiting: max 5 verification attempts.

        Returns:
            True if verification succeeded and SMS MFA enabled, False otherwise

        Raises:
            ValueError: If max verification attempts exceeded
        """
        try:
            sms_record = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.SMS,
                MFASecret.is_verified == False,
            )
        except RepositoryObjectNotFound:
            return False

        # Check rate limiting
        if sms_record.verification_attempts >= self.MAX_VERIFICATION_ATTEMPTS:
            # Delete the secret - user must start over
            MFASecret.delete(MFASecret.id == sms_record.id)
            raise ValueError('Maximum verification attempts exceeded. Please start SMS setup again.')

        # Verify code against unverified secret
        if self.verify_sms_code(user_id, verification_code, allow_unverified=True):
            # Success - enable SMS MFA
            # Clear the verification code from secret field after verification
            MFASecret.update(
                sms_record.id,
                is_verified=True,
                verified_at=datetime.utcnow(),
                verification_attempts=0,  # Reset counter
                secret=None,  # Clear temporary verification code
            )
            return True
        else:
            # Failed - increment counter
            MFASecret.update(sms_record.id, verification_attempts=sms_record.verification_attempts + 1)
            return False

    def send_login_code(self, user_id: NanoIdType) -> str:
        """
        Send a new verification code for login.
        Returns masked phone number.

        Raises:
            ValueError: If user doesn't have SMS MFA enabled
        """
        try:
            sms_record = MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.SMS,
                MFASecret.is_verified == True,
            )
        except RepositoryObjectNotFound:
            raise ValueError('User does not have SMS MFA enabled')

        # Generate new verification code
        code = self.generate_verification_code()

        # Update the secret with new code
        MFASecret.update(sms_record.id, secret=code)

        # Send SMS
        self.send_verification_code(sms_record.phone_number, code)

        return self.mask_phone_number(sms_record.phone_number)

    def disable_sms(self, user_id: NanoIdType) -> bool:
        """
        Disable SMS MFA for a user.
        Deletes the SMS secret.

        Returns:
            True if SMS MFA was disabled, False if user didn't have it enabled
        """
        try:
            sms_record = MFASecret.get(MFASecret.user_id == user_id, MFASecret.mfa_method == MFAMethodTypeEnum.SMS)
            MFASecret.delete(MFASecret.id == sms_record.id)
            return True
        except RepositoryObjectNotFound:
            return False

    def has_sms_enabled(self, user_id: NanoIdType) -> bool:
        """
        Check if user has SMS MFA enabled (verified secret exists).
        """
        try:
            MFASecret.get(
                MFASecret.user_id == user_id,
                MFASecret.mfa_method == MFAMethodTypeEnum.SMS,
                MFASecret.is_verified == True,
            )
            return True
        except RepositoryObjectNotFound:
            return False

    def get_sms_info(self, user_id: NanoIdType) -> dict:
        """
        Get SMS MFA status information for a user (without sensitive data).
        """
        try:
            sms_record = MFASecret.get(MFASecret.user_id == user_id, MFASecret.mfa_method == MFAMethodTypeEnum.SMS)
            return {
                'enabled': sms_record.is_verified,
                'phone_number': self.mask_phone_number(sms_record.phone_number) if sms_record.phone_number else None,
                'created_at': sms_record.created_at,
                'verified_at': sms_record.verified_at,
                'last_used_at': sms_record.last_used_at,
            }
        except RepositoryObjectNotFound:
            return {
                'enabled': False,
                'phone_number': None,
                'created_at': None,
                'verified_at': None,
                'last_used_at': None,
            }
