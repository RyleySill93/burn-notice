from typing import Optional

from fastapi import Depends, Request, params, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from loguru import logger

from src import settings
from src.common import context
from src.common.exceptions import APIException
from src.common.request import get_user_ip_address_from_request
from src.core.authentication.domains import AuthenticatedUser, TokenContent
from src.core.authentication.services.authentication_service import (
    AuthenticationService,
    AuthTokenExpired,
    AuthTokenInvalid,
)


class OAuth2Token(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        # Check for existence of raw token
        authorization = request.headers.get('Authorization')
        scheme, token = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != 'bearer':
            if self.auto_error:
                raise APIException(
                    code=status.HTTP_403_FORBIDDEN,
                    message='Not authenticated',
                )
            else:
                return None
        return token


oauth = OAuth2Token(
    scheme_name='username-password-authentication',
    tokenUrl='api/auth/login-with-email-and-password',
    description='Authenticate with username and password',
)


def authenticate_user(
    request: Request,
    token: str = Depends(oauth),
    authn_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> AuthenticatedUser:
    try:
        token = authn_service.verify_jwt_token(token)
    except AuthTokenExpired:
        raise APIException(
            code=status.HTTP_401_UNAUTHORIZED,
            message='Expired access token',
        )
    except AuthTokenInvalid:
        # Force a refresh for this so users will be booted back to login screen
        raise APIException(
            code=status.HTTP_401_UNAUTHORIZED,
            message='Invalid access token',
        )

    # Token.ip and user_ip will be empty on localhost!
    if settings.ENVIRONMENT != 'local' and not settings.SKIP_IP_CHECK:
        # Check for differences in issuing IP vs current
        authenticate_ip_address(request=request, token=token)

    # Update global context with authenticated user
    impersonator_id = None
    if token.imp_sub:
        impersonator_id = token.imp_sub
        context.set_impersonator_id(impersonator_id=impersonator_id)

    context.set_user(
        user_type=context.AppContextUserType.USER.value,
        user_id=token.sub,
        impersonator_id=impersonator_id,
    )

    return AuthenticatedUser(
        id=token.sub,
        impersonator_id=impersonator_id,
        token=token,
    )


def authenticate_ip_address(request: Request, token: TokenContent):
    """
    Anytime a user's IP address is different than the one assigned
    to the JWT, force them to hit a refresh to ensure it is still
    valid for IP whitelisting
    """
    user_ip = get_user_ip_address_from_request(request)

    ip_has_changed = token.ip != user_ip
    if ip_has_changed:
        logger.debug(f'forcing refresh due to ip change: {token.ip} vs {user_ip}')
        # This should force a hard refresh where we will check
        # if the user has any special IP configuration required
        raise APIException(
            code=status.HTTP_401_UNAUTHORIZED,
            message='IP address has changed',
        )


class AuthenticatedUserGuard(params.Security):
    """
    Wrap me to make guards with specific scope requirements
    Use:
        StaffUser(_AbstractGuard)
    in router:
        user: AuthenticatedUser = StaffUser()
    """

    def __init__(
        self,
        *,
        use_cache: bool = True,
    ):
        super().__init__(
            dependency=authenticate_user,
            use_cache=use_cache,
        )
