from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from src.common.encrypted_field import EncryptedString
from src.common.model import BaseModel
from src.common.nanoid import NanoIdType
from src.core.authentication.constants import AuthenticationMethodEnum, MFAMethodTypeEnum
from src.core.authentication.domains import (
    ChallengeTokenCreate,
    ChallengeTokenRead,
    CustomerAuthSettingsCreate,
    CustomerAuthSettingsRead,
    MfaAuthCodeCreate,
    MfaAuthCodeRead,
    MFASecretCreate,
    MFASecretRead,
)


class CustomerAuthSettings(BaseModel[CustomerAuthSettingsRead, CustomerAuthSettingsCreate]):
    # AuthenticationMethod
    enabled_auth_methods: Mapped[list] = mapped_column(
        ARRAY(String), default=lambda: [AuthenticationMethodEnum.MAGIC_LINK.value]
    )
    # MFA Type enum
    mfa_methods: Mapped[list] = mapped_column(ARRAY(String), nullable=True)
    # any IP ranges will be truthy for whitelist checks
    ip_whitelist: Mapped[list] = mapped_column(ARRAY(INET), nullable=True)
    # JWT token fresh in seconds. default 15 minutes
    token_refresh_frequency: Mapped[int] = mapped_column(default=900)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    # OIDC provider reference (optional - only if OIDC is enabled)
    oidc_provider_id: Mapped[NanoIdType | None] = mapped_column(
        ForeignKey('oidcprovider.id', ondelete='SET NULL'), nullable=True
    )

    __table_args__ = (
        # Ensures that if "PASSWORD" is not enabled, `mfa_methods` must be empty or null.
        CheckConstraint(
            """
            ('PASSWORD' = ANY(enabled_auth_methods)) OR 
            (NOT 'PASSWORD' = ANY(enabled_auth_methods) AND cardinality(mfa_methods) = 0)
            """,
            name='password_for_2fa',
        ),
    )

    __pk_abbrev__ = 'cas'
    __system_audit__ = True
    __read_domain__ = CustomerAuthSettingsRead
    __create_domain__ = CustomerAuthSettingsCreate


class MfaAuthCode(BaseModel[MfaAuthCodeRead, MfaAuthCodeCreate]):
    user_id: Mapped[NanoIdType] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(nullable=False)
    expiration_at: Mapped[datetime] = mapped_column(nullable=False)

    __pk_abbrev__ = 'mfac'
    __system_audit__ = True
    __read_domain__ = MfaAuthCodeRead
    __create_domain__ = MfaAuthCodeCreate


class ChallengeToken(BaseModel[ChallengeTokenRead, ChallengeTokenCreate]):
    jwt_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, unique=True)
    expiration_at: Mapped[datetime] = mapped_column(nullable=False)

    __pk_abbrev__ = 'chtk'
    __system_audit__ = True
    __read_domain__ = ChallengeTokenRead
    __create_domain__ = ChallengeTokenCreate


class MFASecret(BaseModel[MFASecretRead, MFASecretCreate]):
    """Unified MFA secret storage for TOTP, SMS, and future MFA methods"""

    user_id: Mapped[NanoIdType] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    mfa_method: Mapped[MFAMethodTypeEnum] = mapped_column(nullable=False)
    secret: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)  # For TOTP
    phone_number: Mapped[str | None] = mapped_column(String(length=20), nullable=True)  # For SMS (E.164)
    is_verified: Mapped[bool] = mapped_column(default=False)
    verification_attempts: Mapped[int] = mapped_column(default=0)
    backup_codes: Mapped[list] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __pk_abbrev__ = 'mfas'
    __system_audit__ = True
    __read_domain__ = MFASecretRead
    __create_domain__ = MFASecretCreate
