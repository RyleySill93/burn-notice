"""OIDC-specific domain models."""

from datetime import datetime

from pydantic import field_serializer

from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType


class OIDCProviderOption(BaseDomain):
    """OIDC provider option for login"""

    provider_id: NanoIdType
    display_name: str
    customer_id: NanoIdType | None = None


class OIDCProviderCreate(BaseDomain):
    id: NanoIdType | None = None
    display_name: str
    discovery_endpoint: str | None = None
    client_id: str
    client_secret: str  # Will be encrypted automatically by EncryptedString field
    client_auth_method: str = 'client_secret_post'
    issuer: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    jwks_uri: str | None = None
    auto_create_users: bool = False
    default_role_id: NanoIdType | None = None


class OIDCProviderUpdate(OIDCProviderCreate):
    id: NanoIdType
    client_secret: str | None = None  # Optional for updates


class OIDCProviderRead(BaseDomain):
    id: NanoIdType
    display_name: str
    discovery_endpoint: str | None
    client_id: str
    client_secret: str | None = None  # Will be masked via field_serializer
    client_auth_method: str
    issuer: str | None
    authorization_endpoint: str | None
    token_endpoint: str | None
    userinfo_endpoint: str | None
    jwks_uri: str | None
    auto_create_users: bool
    default_role_id: NanoIdType | None = None

    @field_serializer('client_secret')
    def mask_client_secret(self, value: str | None) -> str | None:
        """Mask the client secret for security"""
        if value:
            # Show last 4 characters like API keys often do
            if len(value) > 4:
                return '•' * 12 + value[-4:]
            else:
                return '•' * 16
        return None


class OIDCProviderUserCreate(BaseDomain):
    id: NanoIdType | None = None
    user_id: NanoIdType
    oidc_provider_id: NanoIdType
    external_user_id: str
    external_email: str | None = None
    idp_refresh_token: str | None = None
    last_idp_validation: datetime | None = None
    idp_user_info: dict | None = None  # Store claims/user info from IdP


class OIDCProviderUserUpdate(OIDCProviderUserCreate):
    id: NanoIdType


class OIDCProviderUserRead(OIDCProviderUserUpdate):
    pass
