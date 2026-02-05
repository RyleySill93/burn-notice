from typing import Any, List

from fastapi import APIRouter, Body, Depends, Request, status
from pydantic import EmailStr
from loguru import logger

from src import settings
from src.common.domain import BaseDomain
from src.common.exceptions import APIException, InternalException
from src.common.nanoid import NanoIdType
from src.common.request import get_user_ip_address_from_request
from src.core.authentication.constants import (
    AuthenticationMethodEnum,
    EmailChallengeTemplatesEnum,
    MultiFactorMethodEnum,
)
from src.core.authentication.domains import (
    AuthenticationUrl,
    MfaToken,
    RefreshTokenPayload,
    SMSCodePayload,
    SMSEnablePayload,
    SMSSetupPayload,
    SMSSetupResponse,
    Token,
    TokenContent,
    TOTPEnablePayload,
    TOTPSetupPayload,
    TOTPSetupResponse,
)
from src.core.authentication.guards import AuthenticatedUser, AuthenticatedUserGuard
from src.core.authentication.oidc.exceptions import (
    MissingEnabledOIDCProvider,
    OIDCException,
    OIDCStaffProviderMissing,
    OIDCUserProvisionDisabled,
)
from src.core.authentication.services.authentication_service import (
    AuthChallengeExpired,
    AuthChallengeFailed,
    AuthChallengeTokenUsed,
    AuthenticationService,
    AuthException,
    AuthIpBlocked,
    AuthMethodNotAllowed,
    AuthPasswordFailed,
    AuthTokenExpired,
    AuthTokenInvalid,
    AuthUserArchived,
    AuthUserNotFound,
    EmailAlreadyExists,
    OIDCService,
    PasswordFailsPolicyCheck,
)
from src.core.authorization.guards import CustomerAdminGuard

router = APIRouter()


class EmailChallenge(BaseDomain):
    token: str
    user_id: str


class EmailPayload(BaseDomain):
    email: EmailStr


class PasswordCreatePayload(BaseDomain):
    password_string: str
    token: str


class PasswordLoginPayload(BaseDomain):
    password_string: str
    email: str


class SignupPayload(BaseDomain):
    email: str
    password: str
    first_name: str
    last_name: str


class GetCustomerAuthSettingsPayload(BaseDomain):
    customer_ids: List[NanoIdType]


class CheckMfaCodePayload(BaseDomain):
    email: str
    mfa_code: str
    mfa_token: str
    mfa_method: MultiFactorMethodEnum = MultiFactorMethodEnum.EMAIL  # Default to EMAIL for backwards compatibility


class MfaChallengePayload(BaseDomain):
    email: str
    # TODO - future will have the various MFA types


class AuthenticateChallengePayload(BaseDomain):
    customer_ids: List[NanoIdType]


@router.post('/signup')
def signup(
    request: Request,
    payload: SignupPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token:
    """Create a new user account with email and password"""
    ip_address = get_user_ip_address_from_request(request)

    try:
        return auth_service.signup(
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            ip_address=ip_address,
        )
    except EmailAlreadyExists as e:
        logger.error(f'Signup failed - email already exists: {str(e)}')
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message='An account with this email already exists',
        )
    except PasswordFailsPolicyCheck:
        logger.error('User attempting to signup with weak password')
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message='Password must be at least 8 characters long',
        )
    except AuthIpBlocked:
        logger.error(f'Signup blocked from IP: {ip_address}')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Registration is not allowed from your location',
        )
    except AuthMethodNotAllowed as e:
        logger.error(f'Signup not allowed: {str(e)}')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Account registration is currently disabled. Please contact your administrator.',
        )
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f'Unexpected error during signup: {str(e)}')
        raise APIException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message='An error occurred during registration. Please try again later.',
        )


@router.post('/generate-email-challenge', status_code=201)
def generate_email_challenge(
    payload: EmailPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Any:
    """
    Send user a login magic link email
    """
    try:
        auth_service.send_email_challenge_link(payload.email, challenge_type=EmailChallengeTemplatesEnum.MAGIC_LINK)
    except AuthUserNotFound:
        # Don't reveal if the email exists or not for security
        logger.info(f'Magic link requested for non-existent email: {payload.email}')
        # Return success anyway to prevent email enumeration
        return {'message': 'If an account exists with this email, you will receive a login link shortly.'}


@router.post('/generate-setup-email', status_code=201)
def generate_setup_email(
    payload: EmailPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Any:
    """
    Send user a initial password setup email
    """

    try:
        auth_service.send_email_challenge_link(
            payload.email, challenge_type=EmailChallengeTemplatesEnum.PASSWORD_CREATE
        )
    except AuthUserNotFound:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=f'No user found for email: {payload.email}')


@router.post('/generate-password-reset-email', status_code=201)
def generate_password_reset_email(
    payload: EmailPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Send user a password reset email
    """
    try:
        auth_service.send_email_challenge_link(
            payload.email, challenge_type=EmailChallengeTemplatesEnum.PASSWORD_RESET
        )
    except AuthUserNotFound:
        # Obfuscate that a user may or may not exist with this email
        pass

    # Always return success to prevent email enumeration
    return {'message': 'If an account exists with this email, you will receive a password reset link shortly.'}


@router.post('/authenticate-email-challenge/{user_id}/{token}')
def authenticate_email_challenge(
    request: Request,
    user_id: NanoIdType,
    token: str,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token | MfaToken:
    """
    Authenticate email challenge
    """
    user_ip = get_user_ip_address_from_request(request)
    try:
        return auth_service.authenticate_email_challenge(
            user_id=user_id,
            token=token,
            ip_address=user_ip,
        )
    except AuthMethodNotAllowed:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Magic link is not an allowed login method',
        )
    except AuthIpBlocked:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='IP address not within specified range',
        )
    except AuthChallengeFailed:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Invalid authentication link')
    except AuthChallengeExpired:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Authentication link expired')
    except AuthChallengeTokenUsed:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Authentication token already redeemed')


@router.post('/authenticate-password')
def authenticate_password(
    request: Request,
    password_payload: PasswordLoginPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token | MfaToken:
    """
    If a user has MFA enabled, this will return a MFA Token which
    is part of the requirements for authenticating in authenticate_mfa
    Otherwise, it will return a full Access / Refresh Token
    """
    user_ip = get_user_ip_address_from_request(request)
    try:
        return auth_service.authenticate_with_password_login(
            user_ip=user_ip, email=password_payload.email, password=password_payload.password_string
        )
    except AuthIpBlocked:
        logger.error('Attempted login not within specified IP range')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Your IP address is not allowed to access this system',
        )
    except AuthPasswordFailed as e:
        logger.error(f'Invalid email/password combo: {str(e)}')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            # Intentionally vague to prevent user enumeration
            message='Invalid email or password',
        )
    except AuthUserArchived as e:
        logger.error(f'Archived user attempted login: {str(e)}')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Your account has been deactivated. Please contact support.',
        )
    except AuthMethodNotAllowed as e:
        logger.error(f'Password login not allowed: {str(e)}')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Password login is not enabled for your account. Please use an alternative login method.',
        )
    # FE should block, but surface a generic error to hide the policy verification
    # or that a user might exist for attackers
    except PasswordFailsPolicyCheck:
        logger.error('User attempting to login with password that fails policy')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            # Intentionally vague to prevent user enumeration
            message='Invalid email or password',
        )


@router.get('/azure-sso-login-url')
def get_azure_sso_login_url(
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> str:
    """
    Get the Azure SSO login URL
    """
    return auth_service.initialize_azure_sso_auth_flow()


@router.post('/azure-sso-callback')
def azure_sso_callback(
    request: Request,
    auth_response: dict = Body(..., embed=True),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
):
    user_ip = get_user_ip_address_from_request(request)
    try:
        token = auth_service.authenticate_with_azure_sso(
            auth_response,
            ip_address=user_ip,
        )
        return token
    except AuthMethodNotAllowed:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Azure SSO is not an allowed login method',
        )
    except AuthIpBlocked:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='IP address not within specified range',
        )
    except AuthException as e:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )


# OIDC Authentication Endpoints
@router.get('/oidc/{provider_id}/login')
def initiate_oidc_login(
    provider_id: NanoIdType,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> AuthenticationUrl:
    """
    Start OIDC flow - redirect to IDP using internal provider ID
    """
    from src.core.authentication.oidc.exceptions import (
        MissingEnabledOIDCProvider,
        OIDCException,
        OIDCStaffProviderMissing,
    )

    try:
        return auth_service.initialize_oidc_auth_flow_for_provider_id(provider_id)
    except MissingEnabledOIDCProvider as e:
        raise APIException(
            code=status.HTTP_404_NOT_FOUND, message=str(e) or f'OIDC provider {provider_id} not found or disabled'
        )
    except OIDCStaffProviderMissing:
        raise APIException(
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message='Staff OIDC provider not configured. Please check environment settings.',
        )
    except OIDCException as e:
        logger.error(f'OIDC initialization error: {str(e)}')
        raise APIException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='Failed to initialize OIDC authentication'
        )
    except Exception as e:
        logger.error(f'Unexpected error in OIDC initialization: {str(e)}')
        raise APIException(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='An unexpected error occurred')


@router.get('/oidc/initiate/{client_id}/login')
def initiate_oidc_login_by_client_id(
    client_id: str,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> AuthenticationUrl:
    """
    Start OIDC flow using OAuth client ID - for IdP-initiated SSO flows

    This endpoint is used when users come from IdP portals (Azure AD My Apps, Okta, etc.)
    where we know the client_id but not the internal provider ID.

    The client_id must match the OAuth client ID configured in both:
    - The IdP (Azure AD, Okta, etc.)
    - The OIDC provider settings in our database
    """
    from src.core.authentication.oidc.exceptions import (
        MissingEnabledOIDCProvider,
        OIDCException,
        OIDCStaffProviderMissing,
    )

    try:
        return auth_service.initialize_oidc_auth_flow_for_client_id(client_id)
    except MissingEnabledOIDCProvider as e:
        raise APIException(
            code=status.HTTP_404_NOT_FOUND,
            message=str(e) or f'No enabled OIDC provider found for client ID: {client_id}',
        )
    except OIDCStaffProviderMissing:
        raise APIException(
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message='Staff OIDC provider not configured. Please check environment settings.',
        )
    except OIDCException as e:
        logger.error(f'OIDC initialization error: {str(e)}')
        raise APIException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='Failed to initialize OIDC authentication'
        )
    except Exception as e:
        logger.error(f'Unexpected error in OIDC initialization: {str(e)}')
        raise APIException(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='An unexpected error occurred')


@router.get('/oidc/callback')
def oidc_callback(
    request: Request,
    code: str,
    state: str,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token:
    """
    Handle IDP callback
    """
    import base64
    import json

    # Decode state to extract provider_id
    try:
        # Add padding if needed
        padding = 4 - len(state) % 4
        if padding != 4:
            state += '=' * padding

        state_data = json.loads(base64.urlsafe_b64decode(state))
        provider_id = state_data.get('provider_id')
        if not provider_id:
            raise ValueError('Missing provider_id in state')
    except Exception as e:
        logger.error(f'Failed to decode state: {str(e)}')
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message='Invalid state parameter')

    user_ip = get_user_ip_address_from_request(request)
    try:
        token = auth_service.authenticate_with_oidc(
            provider_id=provider_id,
            code=code,
            ip_address=user_ip,
        )
        return token
    # Authentication service exceptions
    except AuthMethodNotAllowed:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='OIDC is not an allowed login method',
        )
    except AuthIpBlocked:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='IP address not within specified range',
        )
    except AuthUserNotFound as e:
        # Pass through the detailed error message from the service
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message=str(e) if str(e) else 'User not found. Contact your administrator for access.',
        )
    except AuthUserArchived:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='User account has been archived. Contact your administrator.',
        )
    # OIDC-specific exceptions
    except MissingEnabledOIDCProvider as e:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message=str(e) or 'OIDC provider not found or disabled')
    except OIDCUserProvisionDisabled as e:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message=e.message)
    except OIDCStaffProviderMissing:
        raise APIException(code=status.HTTP_503_SERVICE_UNAVAILABLE, message='Staff OIDC provider not configured')
    except OIDCException as e:
        # OIDC protocol errors (token validation, etc.)
        logger.error(f'OIDC protocol error: {str(e)}')
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message=f'OIDC authentication failed: {str(e)}',
            error_type='OIDC_PROTOCOL_ERROR',
        )
    except AuthException as e:
        # Catch-all for other auth exceptions
        logger.error(f'Authentication error: {str(e)}')
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )
    except InternalException as e:
        # General internal errors from OIDCService
        logger.error(f'Internal OIDC error: {str(e)}')
        # Check if it's about auto-provisioning being disabled
        if 'Auto-provisioning is disabled' in str(e):
            raise APIException(code=status.HTTP_403_FORBIDDEN, message=str(e))
        raise APIException(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='Authentication service error')
    except Exception as e:
        # Unexpected errors
        logger.error('Unexpected error in OIDC callback: {}', str(e), exc_info=True)
        raise APIException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='An unexpected error occurred during authentication'
        )


@router.post('/refresh', response_model=Token)
def refresh_jwt_token(
    request: Request,
    refresh_token: RefreshTokenPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token:
    user_ip = get_user_ip_address_from_request(request=request)
    return auth_service.refresh_jwt_token(user_ip=user_ip, refresh_token=refresh_token)


@router.get('/introspect', response_model=TokenContent)
def introspect_token(user: AuthenticatedUser = AuthenticatedUserGuard()) -> Any:
    """
    Get OAuth2 access token
    """
    return TokenContent(
        sub=user.token.sub,
        imp_sub=user.token.imp_sub,
        exp=user.token.exp,
        iat=user.token.iat,
        nbf=user.token.nbf,
        jti=user.token.jti,
        ip=user.token.ip,
    )


@router.post('/update-password', status_code=201)
def update_password(
    request: Request,
    user_id: NanoIdType,
    password_payload: PasswordCreatePayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token | MfaToken:
    user_ip = get_user_ip_address_from_request(request)
    try:
        # Update the password
        auth_service.update_password_for_login(
            user_id, user_ip, password_payload.password_string, token=password_payload.token
        )

        # After successful password update, create and return auth tokens
        # This allows user to be automatically logged in after password reset
        return auth_service.create_auth_token(user_id=user_id, ip_address=user_ip)

    except AuthChallengeTokenUsed:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Authentication token already redeemed')
    except AuthIpBlocked:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='IP address not within specified range',
        )
    # FE should block, but surface a generic error to hide the policy verification
    # or that a user might exist for attackers
    except PasswordFailsPolicyCheck:
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Invalid email or password')


@router.post('/generate-mfa-challenge', status_code=201)
def generate_mfa_challenge(
    request: Request,
    payload: MfaChallengePayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> None:
    try:
        auth_service.send_mfa_verification_email(payload.email)
    except AuthUserNotFound:
        # Obfuscate that a user may or may not exist with this email
        ...


@router.post('/authenticate-mfa')
def authenticate_mfa(
    payload: CheckMfaCodePayload, auth_service: AuthenticationService = Depends(AuthenticationService.factory)
) -> Token:
    try:
        return auth_service.authenticate_with_mfa_code(
            email=payload.email,
            code=payload.mfa_code,
            token=payload.mfa_token,
            mfa_method=payload.mfa_method,
        )
    except AuthChallengeFailed:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message='Invalid code')
    except (AuthTokenExpired, AuthTokenInvalid):
        raise APIException(code=status.HTTP_403_FORBIDDEN, message='Code is no longer valid')


# Staff OIDC Provider Configuration
# Staff OIDC is now configured via environment variables:
# - STAFF_OIDC_CLIENT_ID
# - STAFF_OIDC_CLIENT_SECRET
# - STAFF_OIDC_DISCOVERY_URL


@router.get('/get-staff-oidc-provider')
def get_staff_oidc_provider() -> dict | None:
    """
    Get the staff OIDC provider configuration if available.
    Returns None if not configured in environment.
    """
    # Check if staff OIDC is configured in environment
    if not all(
        [
            AuthenticationMethodEnum.OIDC.value in settings.STAFF_AUTHENTICATION_METHODS,
            settings.STAFF_OIDC_CLIENT_ID,
            settings.STAFF_OIDC_CLIENT_SECRET,
            settings.STAFF_OIDC_DISCOVERY_URL,
        ]
    ):
        return None

    return {
        'id': settings.STAFF_OIDC_PROVIDER_ID,
        'display_name': f'Staff SSO ({settings.ENVIRONMENT})',
        'enabled': True,
        'configured': True,
        'environment': settings.ENVIRONMENT,
    }


# Customer Authentication Settings
# These endpoints manage authentication methods for customers (organization-wide)


@router.get('/customer/{customer_id}/auth-settings', dependencies=[CustomerAdminGuard()])
def get_customer_auth_settings(
    customer_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Get customer authentication settings (requires customer admin permission)"""
    # Get the customer's auth settings
    from src.core.authentication.models import CustomerAuthSettings
    from src.core.authentication.oidc.models import OIDCProvider

    settings = CustomerAuthSettings.get_or_none(customer_id=customer_id)

    # Check if OIDC is configured for this customer
    oidc_provider = None
    if settings and settings.oidc_provider_id:
        oidc_provider = OIDCProvider.get_or_none(id=settings.oidc_provider_id)

    # Default settings if none exist
    if not settings:
        return {
            'enabledAuthMethods': [AuthenticationMethodEnum.PASSWORD.value, AuthenticationMethodEnum.MAGIC_LINK.value],
            'mfaMethods': [],
            'passwordEnabled': True,
            'magicLinkEnabled': True,
            'oidcProviderId': oidc_provider.id if oidc_provider else None,
            'oidcProviderName': oidc_provider.display_name if oidc_provider else None,
        }

    return {
        'enabledAuthMethods': settings.enabled_auth_methods or [],
        'mfaMethods': settings.mfa_methods or [],
        'passwordEnabled': AuthenticationMethodEnum.PASSWORD.value in (settings.enabled_auth_methods or []),
        'magicLinkEnabled': AuthenticationMethodEnum.MAGIC_LINK.value in (settings.enabled_auth_methods or []),
        'oidcProviderId': oidc_provider.id if oidc_provider else None,
        'oidcProviderName': oidc_provider.display_name if oidc_provider else None,
    }


@router.post('/customer/{customer_id}/auth-settings', dependencies=[CustomerAdminGuard()])
def update_customer_auth_settings(
    customer_id: NanoIdType,
    payload: dict = Body(...),
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Update customer authentication settings (requires customer admin permission)"""
    from src.core.authentication.models import CustomerAuthSettings

    # Update or create settings for the customer
    settings = CustomerAuthSettings.get_or_none(customer_id=customer_id)

    enabled_auth_methods = payload.get('enabledAuthMethods', [])
    mfa_methods = payload.get('mfaMethods', [])

    # If password authentication is not enabled, clear MFA methods
    if AuthenticationMethodEnum.PASSWORD not in enabled_auth_methods:
        mfa_methods = []

    update_data = {
        'enabled_auth_methods': enabled_auth_methods,
        'mfa_methods': mfa_methods,
    }

    if settings:
        CustomerAuthSettings.update(settings.id, **update_data)
    else:
        from src.core.authentication.domains import CustomerAuthSettingsCreate

        new_settings = CustomerAuthSettingsCreate(
            customer_id=customer_id,
            enabled_auth_methods=update_data['enabled_auth_methods'],
            mfa_methods=update_data['mfa_methods'],
        )
        CustomerAuthSettings.create(new_settings)

    return {'success': True, 'message': 'Settings updated successfully'}


# Customer OIDC Provider Configuration
# These endpoints allow customers to configure their OIDC providers for organization-wide SSO


@router.get('/get-customer-oidc-provider', dependencies=[CustomerAdminGuard()])
def get_customer_oidc_provider(
    customer_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    oidc_service: OIDCService = Depends(OIDCService.factory),
) -> dict | None:
    """Get the customer's OIDC provider configuration (requires customer admin permission)"""

    # Use the shared private function to get the provider for the customer
    return _get_oidc_provider_for_customer(customer_id, oidc_service)


@router.post('/save-customer-oidc-provider', dependencies=[CustomerAdminGuard()])
def save_customer_oidc_provider(
    customer_id: NanoIdType,
    config: dict = Body(...),
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Create or update customer OIDC provider configuration (requires customer admin permission)"""

    # Use the shared private function to save the provider for the customer
    return _save_oidc_provider_for_customer(customer_id, config)


@router.post('/test-customer-oidc-provider', dependencies=[CustomerAdminGuard()])
def test_customer_oidc_provider(
    customer_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Test customer OIDC provider configuration (requires customer admin permission)"""
    # OIDC providers are currently customer-specific
    return {'success': False, 'message': 'Customer-level OIDC not yet implemented'}


# Customer Authentication Settings (Legacy Endpoints)
# These endpoints manage authentication methods (password, magic link, SSO, MFA) for entities


@router.get('/customer/{customer_id}/auth-settings-direct', dependencies=[CustomerAdminGuard()])
def get_customer_auth_settings_direct(
    customer_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Get customer authentication settings (legacy endpoint - requires customer admin permission)"""
    from src.core.authentication.models import CustomerAuthSettings

    # Get settings directly from model
    settings = CustomerAuthSettings.get_or_none(customer_id=customer_id)

    # Check if OIDC is configured for this customer
    from src.core.authentication.oidc.models import OIDCProvider

    oidc_provider = None
    if settings and settings.oidc_provider_id:
        oidc_provider = OIDCProvider.get_or_none(id=settings.oidc_provider_id)

    return {
        'enabledAuthMethods': settings.enabled_auth_methods if settings else [],
        'mfaMethods': settings.mfa_methods if settings else [],
        'passwordEnabled': AuthenticationMethodEnum.PASSWORD in (settings.enabled_auth_methods or [])
        if settings
        else True,
        'magicLinkEnabled': AuthenticationMethodEnum.MAGIC_LINK in (settings.enabled_auth_methods or [])
        if settings
        else True,
        'oidcProviderId': oidc_provider.id if oidc_provider else None,
        'oidcProviderName': oidc_provider.display_name if oidc_provider else None,
    }


@router.post('/customer/{customer_id}/auth-settings-direct', dependencies=[CustomerAdminGuard()])
def update_customer_auth_settings_direct(
    customer_id: NanoIdType,
    payload: dict = Body(...),
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Update customer authentication settings (legacy endpoint - requires customer admin permission)"""
    from src.core.authentication.models import CustomerAuthSettings

    # Update or create settings
    settings = CustomerAuthSettings.get_or_none(customer_id=customer_id)

    enabled_auth_methods = payload.get('enabledAuthMethods', [])
    mfa_methods = payload.get('mfaMethods', [])

    # If password authentication is not enabled, clear MFA methods
    if AuthenticationMethodEnum.PASSWORD not in enabled_auth_methods:
        mfa_methods = []

    update_data = {
        'enabled_auth_methods': enabled_auth_methods,
        'mfa_methods': mfa_methods,
    }

    if settings:
        CustomerAuthSettings.update(settings.id, **update_data)
    else:
        from src.core.authentication.domains import CustomerAuthSettingsCreate

        new_settings = CustomerAuthSettingsCreate(
            customer_id=customer_id,
            enabled_auth_methods=update_data['enabled_auth_methods'],
            mfa_methods=update_data['mfa_methods'],
        )
        CustomerAuthSettings.create(new_settings)

    return {'success': True, 'message': 'Settings updated successfully'}


# Customer OIDC Provider Configuration (Helper Functions)
# These endpoints allow entities to configure their own OIDC providers for customer SSO


def _get_oidc_provider_for_customer(customer_id: NanoIdType, oidc_service: OIDCService) -> dict | None:
    """
    Private helper function to get OIDC provider configuration for a customer.
    """
    from src.core.authentication.models import CustomerAuthSettings

    auth_settings = CustomerAuthSettings.get_or_none(customer_id=customer_id)
    if not auth_settings or not auth_settings.oidc_provider_id:
        return None

    provider = oidc_service.get_provider_by_id(provider_id=auth_settings.oidc_provider_id)
    if not provider:
        return None

    return {
        'id': provider.id,
        'display_name': provider.display_name,
        'client_id': provider.client_id,
        'discovery_endpoint': provider.discovery_endpoint,
        'issuer': provider.issuer,
        'authorization_endpoint': provider.authorization_endpoint,
        'token_endpoint': provider.token_endpoint,
        'userinfo_endpoint': provider.userinfo_endpoint,
        'jwks_uri': provider.jwks_uri,
        'client_auth_method': provider.client_auth_method,
        'auto_create_users': provider.auto_create_users,
        'default_role_id': provider.default_role_id,
    }


def _save_oidc_provider_for_customer(customer_id: NanoIdType, config: dict) -> dict:
    """
    Private helper function to save OIDC provider configuration for a customer.
    Handles both creation and updates with discovery endpoint resolution and validation.
    """
    from src.core.authentication.models import CustomerAuthSettings
    from src.core.authentication.oidc.domains import OIDCProviderCreate
    from src.core.authentication.oidc.models import OIDCProvider
    from src.core.authentication.oidc.service import OIDCService

    # Check if provider already exists for this customer through auth settings
    auth_settings = CustomerAuthSettings.get_or_none(customer_id=customer_id)
    provider = None
    if auth_settings and auth_settings.oidc_provider_id:
        provider = OIDCProvider.get_or_none(id=auth_settings.oidc_provider_id)

    # If discovery endpoint provided, fetch metadata
    if 'discovery_endpoint' in config and config['discovery_endpoint']:
        oidc_service = OIDCService()
        try:
            metadata = oidc_service.discover_endpoints(config['discovery_endpoint'])
            config.update(
                {
                    'issuer': metadata.get('issuer'),
                    'authorization_endpoint': metadata.get('authorization_endpoint'),
                    'token_endpoint': metadata.get('token_endpoint'),
                    'userinfo_endpoint': metadata.get('userinfo_endpoint'),
                    'jwks_uri': metadata.get('jwks_uri'),
                }
            )
        except Exception as e:
            logger.error(f'Failed to fetch OIDC metadata from {config["discovery_endpoint"]}: {e}')
            raise APIException(
                code=status.HTTP_400_BAD_REQUEST,
                message=f'Failed to discover OIDC endpoints: {str(e)}. Please verify the discovery URL is correct and accessible.',
            )

    # Validate that critical endpoints are present
    required_fields = ['authorization_endpoint', 'token_endpoint', 'jwks_uri', 'issuer']
    missing_fields = [field for field in required_fields if not config.get(field)]
    if missing_fields:
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message=f'Missing required OIDC configuration fields: {", ".join(missing_fields)}. '
            'Please provide a valid discovery endpoint or configure these fields manually.',
        )

    if provider:
        # Update existing provider
        OIDCProvider.update(provider.id, **config)
        return {'success': True, 'message': 'Provider updated successfully', 'created': False}
    else:
        # Create new provider
        provider_data = OIDCProviderCreate(
            display_name=config.get('display_name', 'Customer SSO Provider'),
            client_id=config.get('client_id'),
            client_secret=config.get('client_secret'),
            client_auth_method=config.get('client_auth_method', 'client_secret_post'),
            discovery_endpoint=config.get('discovery_endpoint'),
            issuer=config.get('issuer'),
            authorization_endpoint=config.get('authorization_endpoint'),
            token_endpoint=config.get('token_endpoint'),
            userinfo_endpoint=config.get('userinfo_endpoint'),
            jwks_uri=config.get('jwks_uri'),
            auto_create_users=config.get('auto_create_users', False),
        )

        new_provider = OIDCProvider.create(provider_data)

        # Link the provider to the customer's auth settings
        if not auth_settings:
            raise ValueError('Missing CustomerAuthSettings')
        # Update existing auth settings to link to the provider
        CustomerAuthSettings.update(auth_settings.id, oidc_provider_id=new_provider.id)

        return {'success': True, 'message': 'Provider created successfully', 'created': True}


@router.get('/get-customer-oidc-provider-direct', dependencies=[CustomerAdminGuard()])
def get_customer_oidc_provider_direct(
    customer_id: NanoIdType,
    oidc_service: OIDCService = Depends(OIDCService.factory),
) -> dict | None:
    """Get the customer's OIDC provider configuration (legacy endpoint - requires customer admin permission)"""
    return _get_oidc_provider_for_customer(customer_id, oidc_service)


@router.post('/save-customer-oidc-provider-direct', dependencies=[CustomerAdminGuard()])
def save_customer_oidc_provider_direct(
    customer_id: NanoIdType,
    config: dict = Body(...),
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Create or update customer OIDC provider configuration (legacy endpoint - requires customer admin permission)"""
    return _save_oidc_provider_for_customer(customer_id, config)


@router.post('/test-customer-oidc-provider-direct', dependencies=[CustomerAdminGuard()])
def test_customer_oidc_provider_direct(
    customer_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
) -> dict:
    """Test customer OIDC provider configuration (legacy endpoint - requires customer admin permission)"""
    # Get the provider through auth settings
    from src.core.authentication.models import CustomerAuthSettings
    from src.core.authentication.oidc.models import OIDCProvider
    from src.core.authentication.oidc.service import OIDCService

    auth_settings = CustomerAuthSettings.get_or_none(customer_id=customer_id)
    provider = None
    if auth_settings and auth_settings.oidc_provider_id:
        provider = OIDCProvider.get_or_none(id=auth_settings.oidc_provider_id)
    if not provider:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message='Provider not found for this customer')

    oidc_service = OIDCService()

    try:
        # Test fetching JWKS
        jwks = oidc_service._get_jwks(provider)

        # Test discovery endpoint if present
        if provider.discovery_endpoint:
            _ = oidc_service.discover_endpoints(provider.discovery_endpoint)

        return {
            'success': True,
            'message': 'Provider configuration is valid',
            'details': {
                'jwks_available': bool(jwks.get('keys')),
                'endpoints_discovered': bool(provider.discovery_endpoint),
            },
        }
    except Exception as e:
        return {'success': False, 'message': f'Provider test failed: {str(e)}'}


# TOTP Management Endpoints
@router.post('/generate-totp-secret', status_code=201, response_model=TOTPSetupResponse)
def generate_totp_secret(
    payload: TOTPSetupPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> TOTPSetupResponse:
    """
    Generate TOTP secret during MFA setup flow.
    Returns QR code and backup codes.

    **Important**: User must save backup codes - they won't be shown again!

    This endpoint accepts an MFA token (not a full JWT) for use during login flow.
    """
    try:
        # Validate MFA token and get user
        user = auth_service.get_valid_user_from_mfa_token(payload.email, payload.mfa_token)

        setup_response = auth_service.initiate_totp_setup(user_id=user.id, user_email=user.email)
        return setup_response

    except (AuthTokenExpired, AuthTokenInvalid):
        raise APIException(
            code=status.HTTP_403_FORBIDDEN, message='MFA token is no longer valid', error_type='MFA_TOKEN_INVALID'
        )
    except ValueError as e:
        # User already has TOTP enabled
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e), error_type='TOTP_ALREADY_ENABLED')
    except Exception as e:
        logger.error(f'TOTP setup error: {str(e)}')
        raise APIException(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='Failed to generate TOTP secret')


@router.post('/enable-totp', status_code=201)
def enable_totp(
    payload: TOTPEnablePayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token:
    """
    Enable TOTP by verifying first code from authenticator during MFA setup flow.
    This activates TOTP for the user and returns a full auth token.

    Rate limited to 5 attempts - after that user must generate new secret.
    This endpoint accepts an MFA token (not a full JWT) for use during login flow.
    """
    try:
        # Validate MFA token and get user
        user = auth_service.get_valid_user_from_mfa_token(payload.email, payload.mfa_token)

        success = auth_service.complete_totp_setup(user_id=user.id, verification_code=payload.code)

        if success:
            # Return full auth token - user has proven they have both password and MFA device
            return auth_service.create_auth_token(user_id=user.id, ip_address=None)
        else:
            raise APIException(
                code=status.HTTP_400_BAD_REQUEST, message='Invalid verification code', error_type='INVALID_TOTP_CODE'
            )
    except (AuthTokenExpired, AuthTokenInvalid):
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Your session has expired. Please log in again.',
            error_type='MFA_TOKEN_EXPIRED',
        )
    except ValueError as e:
        # Max attempts exceeded
        raise APIException(code=status.HTTP_429_TOO_MANY_REQUESTS, message=str(e), error_type='TOTP_MAX_ATTEMPTS')


@router.post('/disable-totp', status_code=201)
def disable_totp(
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Disable TOTP for authenticated user.
    Requires re-authentication via password or magic link.
    """
    success = auth_service.disable_totp_for_user(user.id)

    if success:
        return {'success': True, 'message': 'TOTP disabled successfully'}
    else:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message='TOTP was not enabled')


@router.get('/get-totp-status')
def get_totp_status(
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Get TOTP status for authenticated user.
    """
    return auth_service.totp_service.get_totp_info(user.id)


@router.post('/authenticated/generate-totp-secret', status_code=201, response_model=TOTPSetupResponse)
def authenticated_generate_totp_secret(
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> TOTPSetupResponse:
    """
    Generate TOTP secret for authenticated user who wants to enable TOTP.
    Returns QR code and backup codes.

    **Important**: User must save backup codes - they won't be shown again!
    """
    try:
        # Get user email from user object
        user_email = getattr(user, 'email', None) or user.token.sub
        setup_response = auth_service.initiate_totp_setup(user_id=user.id, user_email=user_email)
        return setup_response
    except ValueError as e:
        # User already has TOTP enabled
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e), error_type='TOTP_ALREADY_ENABLED')
    except Exception as e:
        logger.error(f'TOTP setup error for user {user.id}: {str(e)}')
        logger.exception(e)
        raise APIException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f'Failed to generate TOTP secret: {str(e)}'
        )


@router.post('/authenticated/enable-totp', status_code=201)
def authenticated_enable_totp(
    code: str,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Enable TOTP by verifying first code from authenticator for authenticated user.
    This activates TOTP for the user.

    Rate limited to 5 attempts - after that user must generate new secret.
    """
    try:
        success = auth_service.complete_totp_setup(user_id=user.id, verification_code=code)

        if success:
            return {'success': True, 'message': 'TOTP enabled successfully'}
        else:
            raise APIException(
                code=status.HTTP_400_BAD_REQUEST, message='Invalid verification code', error_type='INVALID_TOTP_CODE'
            )
    except ValueError as e:
        if 'Maximum attempts' in str(e):
            raise APIException(
                code=status.HTTP_429_TOO_MANY_REQUESTS,
                message='Too many failed attempts. Please generate a new secret.',
                error_type='TOTP_MAX_ATTEMPTS',
            )
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e))


# SMS MFA Management Endpoints
@router.post('/setup-sms-mfa', status_code=201, response_model=SMSSetupResponse)
def setup_sms_mfa(
    payload: SMSSetupPayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> SMSSetupResponse:
    """
    Setup SMS MFA during MFA setup flow.
    Sends verification code to provided phone number.

    This endpoint accepts an MFA token (not a full JWT) for use during login flow.
    """
    try:
        # Validate MFA token and get user
        user = auth_service.get_valid_user_from_mfa_token(payload.email, payload.mfa_token)

        setup_response = auth_service.initiate_sms_setup(user_id=user.id, phone_number=payload.phone_number)
        return setup_response

    except (AuthTokenExpired, AuthTokenInvalid):
        raise APIException(
            code=status.HTTP_403_FORBIDDEN, message='MFA token is no longer valid', error_type='MFA_TOKEN_INVALID'
        )
    except ValueError as e:
        # User already has SMS MFA enabled or invalid phone number
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e), error_type='SMS_SETUP_FAILED')
    except Exception as e:
        logger.error(f'SMS MFA setup error: {str(e)}')
        raise APIException(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='Failed to setup SMS MFA')


@router.post('/enable-sms-mfa', status_code=201)
def enable_sms_mfa(
    payload: SMSEnablePayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token:
    """
    Enable SMS MFA by verifying code sent via SMS during MFA setup flow.
    This activates SMS MFA for the user and returns a full auth token.

    Rate limited to 5 attempts - after that user must start setup again.
    This endpoint accepts an MFA token (not a full JWT) for use during login flow.
    """
    try:
        # Validate MFA token and get user
        user = auth_service.get_valid_user_from_mfa_token(payload.email, payload.mfa_token)

        success = auth_service.complete_sms_setup(user_id=user.id, verification_code=payload.code)

        if success:
            # Return full auth token - user has proven they have both password and MFA device
            return auth_service.create_auth_token(user_id=user.id, ip_address=None)
        else:
            raise APIException(
                code=status.HTTP_400_BAD_REQUEST, message='Invalid verification code', error_type='INVALID_SMS_CODE'
            )
    except (AuthTokenExpired, AuthTokenInvalid):
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Your session has expired. Please log in again.',
            error_type='MFA_TOKEN_EXPIRED',
        )
    except ValueError as e:
        # Max attempts exceeded
        raise APIException(code=status.HTTP_429_TOO_MANY_REQUESTS, message=str(e), error_type='SMS_MAX_ATTEMPTS')


@router.post('/send-sms-code', status_code=201)
def send_sms_code(
    payload: SMSCodePayload,
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Send SMS verification code during login flow.
    This endpoint accepts an MFA token (not a full JWT).
    """
    try:
        # Validate MFA token and get user
        user = auth_service.get_valid_user_from_mfa_token(payload.email, payload.mfa_token)

        masked_phone = auth_service.send_sms_login_code(user_id=user.id)

        return {'success': True, 'message': f'Verification code sent to {masked_phone}'}

    except (AuthTokenExpired, AuthTokenInvalid):
        raise APIException(
            code=status.HTTP_403_FORBIDDEN, message='MFA token is no longer valid', error_type='MFA_TOKEN_INVALID'
        )
    except ValueError as e:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e), error_type='SMS_NOT_ENABLED')
    except Exception as e:
        logger.error(f'SMS code send error: {str(e)}')
        raise APIException(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='Failed to send SMS code')


@router.post('/disable-sms-mfa', status_code=201)
def disable_sms_mfa(
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Disable SMS MFA for authenticated user.
    Requires re-authentication via password or magic link.
    """
    success = auth_service.disable_sms_for_user(user.id)

    if success:
        return {'success': True, 'message': 'SMS MFA disabled successfully'}
    else:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message='SMS MFA was not enabled')


@router.get('/get-sms-status')
def get_sms_status(
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Get SMS MFA status for authenticated user.
    """
    return auth_service.sms_service.get_sms_info(user.id)


@router.post('/authenticated/setup-sms-mfa', status_code=201, response_model=SMSSetupResponse)
def authenticated_setup_sms_mfa(
    phone_number: str,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> SMSSetupResponse:
    """
    Setup SMS MFA for authenticated user who wants to enable SMS.
    Sends verification code to provided phone number.
    """
    try:
        setup_response = auth_service.initiate_sms_setup(user_id=user.id, phone_number=phone_number)
        return setup_response
    except ValueError as e:
        if 'already enabled' in str(e).lower():
            raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e), error_type='SMS_ALREADY_ENABLED')
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e))
    except Exception as e:
        logger.error(f'SMS setup error: {str(e)}')
        raise APIException(code=status.HTTP_500_INTERNAL_SERVER_ERROR, message='Failed to setup SMS MFA')


@router.post('/authenticated/enable-sms-mfa', status_code=201)
def authenticated_enable_sms_mfa(
    code: str,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    auth_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> dict:
    """
    Enable SMS MFA by verifying code sent via SMS for authenticated user.
    This activates SMS MFA for the user.

    Rate limited to 5 attempts - after that user must start setup again.
    """
    try:
        success = auth_service.complete_sms_setup(user_id=user.id, verification_code=code)

        if success:
            return {'success': True, 'message': 'SMS MFA enabled successfully'}
        else:
            raise APIException(
                code=status.HTTP_400_BAD_REQUEST, message='Invalid verification code', error_type='INVALID_SMS_CODE'
            )
    except ValueError as e:
        if 'Maximum attempts' in str(e):
            raise APIException(
                code=status.HTTP_429_TOO_MANY_REQUESTS,
                message='Too many failed attempts. Please start setup again.',
                error_type='SMS_MAX_ATTEMPTS',
            )
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e))
