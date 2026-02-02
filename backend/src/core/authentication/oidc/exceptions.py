"""OIDC-specific exceptions."""

from src.common.exceptions import InternalException


class OIDCException(InternalException):
    """Base exception for OIDC-related errors."""

    pass


class OIDCStaffProviderMissing(OIDCException):
    """Raised when staff OIDC provider is not configured."""

    pass


class MissingEnabledOIDCProvider(OIDCException):
    """Raised when an OIDC provider is not found or not enabled."""

    pass


class OIDCUserProvisionDisabled(OIDCException):
    """Raised when auto-provisioning is disabled for an OIDC provider."""

    pass


class OIDCTokenExchangeError(OIDCException):
    """Raised when token exchange with OIDC provider fails."""

    pass


class OIDCTokenValidationError(OIDCException):
    """Raised when ID token validation fails."""

    pass


class OIDCDiscoveryError(OIDCException):
    """Raised when OIDC discovery endpoint fails."""

    pass


class OIDCMissingClaimsError(OIDCException):
    """Raised when required claims are missing from ID token."""

    pass
