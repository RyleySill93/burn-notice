from datetime import datetime

from src import settings
from src.common.nanoid import NanoId
from src.core.authentication.domains import MfaAuthCodeCreate, MfaAuthCodeRead
from src.core.authentication.models import MfaAuthCode
from src.core.authentication.utils import generate_mfa_code
from src.network.database.repository.exceptions import RepositoryObjectNotFound


class MfaEmailCodeService:
    @classmethod
    def factory(cls) -> 'MfaEmailCodeService':
        return cls()

    def delete_prior_code(self, user_id: NanoId):
        """
        Delete any existing MFA code for the user.
        """
        try:
            code_to_delete = MfaAuthCode.get(MfaAuthCode.user_id == user_id)
            MfaAuthCode.delete(MfaAuthCode.id == code_to_delete.id)
        except RepositoryObjectNotFound:
            # If no code exists, nothing needs to be done
            pass

    def create_email_code(self, user_id: NanoId) -> MfaAuthCodeRead:
        """
        Create an email type MFA code after deleting any existing ones.
        """
        # Ensure no prior code exists
        self.delete_prior_code(user_id)

        # Generate a new MFA code
        return MfaAuthCode.create(
            MfaAuthCodeCreate(
                code=generate_mfa_code(6),
                user_id=user_id,
                expiration_at=datetime.utcnow() + settings.AUTH_SETTINGS['MFA_CODE'],
            )
        )

    def check_code(self, user_id: NanoId, code: str) -> bool:
        """
        Check the table for an auth code matching the type, user_id, and code,
        which is not expired. If it does not exist or is expired, return False.
        """
        now = datetime.utcnow()
        try:
            mfa_code = MfaAuthCode.get(
                MfaAuthCode.user_id == user_id,
                MfaAuthCode.code == code,
                MfaAuthCode.expiration_at > now,
            )
            # If the code is valid, immediately delete it to prevent reuse
            MfaAuthCode.delete(MfaAuthCode.id == mfa_code.id)
            return True
        except RepositoryObjectNotFound:
            return False
