"""OIDC-specific database models."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.common.encrypted_field import EncryptedString
from src.common.model import BaseModel
from src.common.nanoid import NanoIdType
from src.core.authentication.oidc.domains import (
    OIDCProviderCreate,
    OIDCProviderRead,
    OIDCProviderUserCreate,
    OIDCProviderUserRead,
)


class OIDCProvider(BaseModel[OIDCProviderRead, OIDCProviderCreate]):
    """OIDC provider configuration - one per CustomerAuthSettings"""

    display_name: Mapped[str] = mapped_column(String(100))  # "Login with ACME SSO"

    # OIDC Configuration
    discovery_endpoint: Mapped[str | None] = mapped_column(nullable=True)
    client_id: Mapped[str] = mapped_column(nullable=False)
    client_secret: Mapped[str] = mapped_column(
        EncryptedString, nullable=False
    )  # Stored encrypted, but field is just "client_secret"
    client_auth_method: Mapped[str] = mapped_column(
        String(20),
        default='client_secret_post',
    )

    # Autodiscovered endpoints
    issuer: Mapped[str | None] = mapped_column(nullable=True)
    authorization_endpoint: Mapped[str | None] = mapped_column(nullable=True)
    token_endpoint: Mapped[str | None] = mapped_column(nullable=True)
    userinfo_endpoint: Mapped[str | None] = mapped_column(nullable=True)
    jwks_uri: Mapped[str | None] = mapped_column(nullable=True)

    # Settings
    auto_create_users: Mapped[bool] = mapped_column(default=False)
    default_role_id: Mapped[NanoIdType | None] = mapped_column(
        ForeignKey('accessrole.id', ondelete='SET NULL'),
        nullable=True,
    )

    __pk_abbrev__ = 'oidc'
    __system_audit__ = True
    __read_domain__ = OIDCProviderRead
    __create_domain__ = OIDCProviderCreate


class OIDCProviderUser(BaseModel[OIDCProviderUserRead, OIDCProviderUserCreate]):
    """Map OIDC provider users to Burn Notice users with their claims"""

    user_id: Mapped[NanoIdType] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    oidc_provider_id: Mapped[NanoIdType] = mapped_column(
        ForeignKey('oidcprovider.id', ondelete='CASCADE'), nullable=False
    )
    external_user_id: Mapped[str] = mapped_column(nullable=False)  # IDP's user ID (sub claim)
    external_email: Mapped[str | None] = mapped_column(nullable=True)  # Email at time of mapping

    # Store IDP refresh token for validation on our token refresh
    idp_refresh_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    last_idp_validation: Mapped[datetime | None] = mapped_column(nullable=True)

    # Store user claims/info from IdP for audit and debugging
    idp_user_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "external_user_id IS NOT NULL AND external_user_id != ''",
            name='external_user_id_not_empty',
        ),
    )

    __pk_abbrev__ = 'oidp'
    __system_audit__ = True
    __read_domain__ = OIDCProviderUserRead
    __create_domain__ = OIDCProviderUserCreate
