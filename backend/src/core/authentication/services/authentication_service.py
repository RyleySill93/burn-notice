import string
import uuid
from datetime import datetime, timezone
from typing import List

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
from sqlalchemy.exc import IntegrityError

from src import settings
from src.common.exceptions import InternalException
from src.common.nanoid import NanoIdType, generate_custom_nanoid
from src.core.authentication.azure.exceptions import AzureAuthFailure
from src.core.authentication.azure.service import AzureSSOService
from src.core.authentication.constants import (
    EMAIL_INVITE_AUTH_METHODS,
    LOGIN_INVITE_AUTH_METHODS,
    PASSWORD_INVITE_AUTH_METHODS,
    AuthenticationInitialRoute,
    AuthenticationMethodEnum,
    EmailChallengeAuthRoute,
    EmailChallengeTemplatesEnum,
    MultiFactorMethodEnum,
)
from src.core.authentication.domains import (
    AuthenticationChallenge,
    AuthenticationUrl,
    CustomerAuthSettingsRead,
    MfaToken,
    RefreshTokenPayload,
    SMSSetupResponse,
    Token,
    TokenContent,
    TOTPSetupResponse,
    UserAuthSettings,
)
from src.core.authentication.mfa.email_service import MfaEmailCodeService
from src.core.authentication.mfa.sms_service import SMSService
from src.core.authentication.mfa.totp_service import TOTPService
from src.core.authentication.oidc.domains import OIDCProviderOption
from src.core.authentication.oidc.exceptions import OIDCDiscoveryError, OIDCStaffProviderMissing
from src.core.authentication.oidc.models import OIDCProvider
from src.core.authentication.oidc.service import OIDCService
from src.core.authentication.services.challenge_token_service import ChallengeTokenService
from src.core.authentication.services.customer_settings_service import CustomerAuthSettingsService
from src.core.authentication.utils import create_derived_key
from src.core.membership import MembershipService
from src.core.user import UserCreate, UserNotFound, UserRead, UserService, UserUpdate
from src.platform.email.email import Email


class AuthException(InternalException): ...


class AuthTokenInvalid(AuthException): ...


class AuthTokenExpired(AuthException): ...


class AuthChallengeFailed(AuthException):
    pass


class AuthChallengeExpired(AuthException):
    pass


class AuthChallengeTokenUsed(AuthException):
    pass


class AuthUserNotFound(AuthException):
    pass


class AuthUserArchived(AuthException):
    pass


class InvalidOIDCToken(AuthException):
    pass


class AuthPasswordFailed(AuthException):
    pass


class AuthIpBlocked(AuthException):
    pass


class AuthMethodNotAllowed(AuthException):
    pass


class EmailAlreadyExists(AuthException):
    pass


class PasswordFailsPolicyCheck(AuthException):
    pass


class AuthenticationService:
    _password_hasher = PasswordHasher()
    _JWT_SIGNING_ALGORITHM = 'HS256'

    def __init__(
        self,
        user_service: UserService,
        customer_auth_settings_service: CustomerAuthSettingsService,
        mfa_email_service: MfaEmailCodeService,
        challenge_token_service: ChallengeTokenService,
        azure_sso_service: AzureSSOService,
        oidc_service: OIDCService | None = None,
        totp_service: TOTPService | None = None,
        sms_service: SMSService | None = None,
    ):
        self.user_service = user_service or UserService()
        self.azure_sso_service = azure_sso_service or AzureSSOService.factory()
        self.customer_auth_settings_service = customer_auth_settings_service or CustomerAuthSettingsService()
        self.mfa_email_service = mfa_email_service or MfaEmailCodeService()
        self.challenge_token_service = challenge_token_service or ChallengeTokenService()
        self.oidc_service = oidc_service or OIDCService.factory()
        self.totp_service = totp_service or TOTPService.factory()
        self.sms_service = sms_service or SMSService.factory()

    @classmethod
    def factory(cls) -> 'AuthenticationService':
        return cls(
            user_service=UserService.factory(),
            customer_auth_settings_service=CustomerAuthSettingsService.factory(),
            mfa_email_service=MfaEmailCodeService.factory(),
            challenge_token_service=ChallengeTokenService.factory(),
            azure_sso_service=AzureSSOService.factory(),
            oidc_service=OIDCService.factory(),
            totp_service=TOTPService.factory(),
            sms_service=SMSService.factory(),
        )

    def get_customer_auth_settings_from_user(self, user_id: NanoIdType) -> UserAuthSettings:
        # Get customer IDs from user memberships
        user = self.user_service.get_user_for_id(user_id)
        customer_ids = MembershipService.factory().list_membership_customers_for_user_by_email(user.email)
        return self.get_customer_auth_settings(user_id=user_id, customer_ids=customer_ids)

    def update_password_for_login(self, user_id: str, user_ip: str, plain_password: str, token: str) -> None:
        """
        used by both initial creation flow & password reset flows. first validate update came from email tokens
        """
        auth_settings = self.get_customer_auth_settings_from_user(user_id)
        self._verify_ip_whitelist(user_ip=user_ip, auth_settings=auth_settings)
        self.password_meets_policy(plain_password)
        user = self.get_valid_user_from_challenge_token(user_id, token)
        hashed_password = self.hash_password(plain_password)
        self.user_service.update_user(
            user.id, UserUpdate(first_name=user.first_name, last_name=user.last_name, hashed_password=hashed_password)
        )
        if not user.is_active:
            # Activate them here since they've now verified their email
            self.user_service.activate_user(user_id=user.id)

    def signup(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        ip_address: str | None = None,
    ) -> Token:
        """
        Create a new user account and authenticate them
        """
        # Check if user already exists
        try:
            existing_user = self.user_service.get_user_for_email(email)
            if existing_user:
                raise EmailAlreadyExists(f'User with email {email} already exists')
        except UserNotFound:
            # This is expected - user doesn't exist, so we can create them
            pass

        # Validate password meets policy
        self.password_meets_policy(password)

        # Create the user
        user = self.user_service.create_user(
            UserCreate(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
        )

        # Hash and set the password
        hashed_password = self.hash_password(password)
        self.user_service.update_user(
            user.id,
            UserUpdate(first_name=first_name, last_name=last_name, hashed_password=hashed_password),
        )

        # Authenticate and return token
        return self.authenticate_with_password_login(
            user_ip=ip_address or '',
            email=email,
            password=password,
            ip_address=ip_address,
        )

    def authenticate_with_password_login(
        self,
        user_ip: str,
        email: str,
        password: str,
        ip_address: str | None = None,
    ) -> Token | MfaToken:
        """
        Exposed directly from API to authenticate via password
        If MFA is required for login, this will return an MFA
        Token that is only good for matching the MFA code, otherwise
        this will return a full login token with refresh / access granted
        """
        try:
            user = self.user_service.get_auth_user_for_email(email)
        except UserNotFound:
            raise AuthPasswordFailed('User not found')

        if user.archived_at is not None:
            raise AuthUserArchived(f'User archived at {user.archived_at}')

        self.password_meets_policy(password)
        auth_settings = self.get_customer_auth_settings_from_user(user.id)
        self._verify_ip_whitelist(user_ip=user_ip, auth_settings=auth_settings)

        password_login_enabled = AuthenticationMethodEnum.PASSWORD in auth_settings.auth_methods
        if not password_login_enabled:
            raise AuthMethodNotAllowed(message='Password login not allowed')

        try:
            self.is_password_match(password, user.hashed_password)
        except Argon2Error:
            raise AuthPasswordFailed('Invalid password for user')

        if auth_settings.mfa_methods:
            # Check which MFA methods user has actually configured
            configured_mfa_methods = []
            if MultiFactorMethodEnum.EMAIL in auth_settings.mfa_methods:
                configured_mfa_methods.append(MultiFactorMethodEnum.EMAIL.value)
            if MultiFactorMethodEnum.TOTP in auth_settings.mfa_methods and self.totp_service.has_totp_enabled(user.id):
                configured_mfa_methods.append(MultiFactorMethodEnum.TOTP.value)
            if MultiFactorMethodEnum.SMS in auth_settings.mfa_methods and self.sms_service.has_sms_enabled(user.id):
                configured_mfa_methods.append(MultiFactorMethodEnum.SMS.value)

            # There will be another step after this, send them an MFA token
            return self.create_mfa_token(
                email=email,
                ip_address=ip_address,
                configured_mfa_methods=configured_mfa_methods,
            )

        # Otherwise authenticate the user
        return self.create_auth_token(
            user_id=user.id, ip_address=ip_address, auth_method=AuthenticationMethodEnum.PASSWORD.value
        )

    def authenticate_email_challenge(
        self,
        user_id: str,
        token: str,
        ip_address: str,
    ) -> Token | MfaToken:
        """
        Exposed directly from API to authenticate a challenge email
        aka magic link
        """
        user = self.get_valid_user_from_challenge_token(user_id, token)
        if user.archived_at is not None:
            raise AuthUserArchived(f'User archived at {user.archived_at}')

        # Check ip address within range if whitelist
        auth_settings = self.get_customer_auth_settings_from_user(user.id)
        self._verify_ip_whitelist(user_ip=ip_address, auth_settings=auth_settings)
        # Ensure magic link is permitted
        magic_link_enabled = AuthenticationMethodEnum.MAGIC_LINK in auth_settings.auth_methods
        if not magic_link_enabled:
            raise AuthMethodNotAllowed(message='Magic link not allowed')
        if not user.is_active:
            self.user_service.activate_user(user_id=user.id)

        if auth_settings.mfa_methods:
            # Check which MFA methods user has actually configured
            configured_mfa_methods = []
            if MultiFactorMethodEnum.EMAIL in auth_settings.mfa_methods:
                configured_mfa_methods.append(MultiFactorMethodEnum.EMAIL.value)
            if MultiFactorMethodEnum.TOTP in auth_settings.mfa_methods and self.totp_service.has_totp_enabled(user.id):
                configured_mfa_methods.append(MultiFactorMethodEnum.TOTP.value)
            if MultiFactorMethodEnum.SMS in auth_settings.mfa_methods and self.sms_service.has_sms_enabled(user.id):
                configured_mfa_methods.append(MultiFactorMethodEnum.SMS.value)

            # There will be another step after this, send them an MFA token
            return self.create_mfa_token(
                email=user.email,
                ip_address=ip_address,
                configured_mfa_methods=configured_mfa_methods,
            )

        # Otherwise authenticate the user
        return self.create_auth_token(
            user_id=user.id, ip_address=ip_address, auth_method=AuthenticationMethodEnum.MAGIC_LINK.value
        )

    def initialize_azure_sso_auth_flow(self) -> str:
        return self.azure_sso_service.initialize_authentication_flow()

    def authenticate_with_azure_sso(self, auth_flow: dict, ip_address: str | None) -> Token:
        try:
            user_id = self.azure_sso_service.authenticate_with_azure(auth_flow)
            user = self.user_service.get_user_for_id(user_id=user_id)
            if user.archived_at is not None:
                raise AuthUserArchived(f'User archived at {user.archived_at}')

            auth_settings = self.get_customer_auth_settings_from_user(user_id)
            self._verify_ip_whitelist(user_ip=ip_address, auth_settings=auth_settings)

            azure_sso_enabled = AuthenticationMethodEnum.AZURE_SSO in auth_settings.auth_methods
            if not azure_sso_enabled:
                raise AuthMethodNotAllowed(message='Azure SSO is not an allowed login method')

            return self.create_auth_token(
                user_id=user_id, ip_address=ip_address, auth_method=AuthenticationMethodEnum.AZURE_SSO.value
            )
        except AzureAuthFailure as exc:
            # Handle Azure authentication failures
            raise AuthException(message=exc.message)

    def initialize_oidc_auth_flow_for_provider_id(self, provider_id: NanoIdType) -> AuthenticationUrl:
        return self.oidc_service.initialize_auth_flow_for_provider_id(provider_id=provider_id)

    def initialize_oidc_auth_flow_for_client_id(self, client_id: str) -> AuthenticationUrl:
        return self.oidc_service.initialize_auth_flow_for_client_id(client_id=client_id)

    def authenticate_with_oidc(self, provider_id: NanoIdType, code: str, ip_address: str | None) -> Token:
        """
        Authenticate user via OIDC provider.
        """
        # Complete OIDC authentication flow
        user, provider, claims = self.oidc_service.authenticate_user(provider_id=provider_id, code=code)

        # Verify user is not archived
        if user.archived_at is not None:
            raise AuthUserArchived(f'User archived at {user.archived_at}')

        # Get auth settings and verify
        auth_settings = self.get_customer_auth_settings_from_user(user.id)
        self._verify_ip_whitelist(user_ip=ip_address, auth_settings=auth_settings)

        # Check OIDC is enabled
        if AuthenticationMethodEnum.OIDC not in auth_settings.auth_methods:
            raise AuthMethodNotAllowed(message='OIDC login not allowed')

        # Return Burn Notice JWT token with OIDC auth method and provider ID claims (used during refresh)
        return self.create_auth_token(
            user_id=user.id,
            ip_address=ip_address,
            auth_method=AuthenticationMethodEnum.OIDC.value,
            oidc_provider_id=provider.id,
        )

    def _verify_ip_whitelist(self, user_ip: str, auth_settings: UserAuthSettings) -> None:
        # localhost bypass whitelist check - no IP
        if settings.IS_LOCAL:
            return
        allowed_ip = auth_settings.is_ip_within_range(user_ip)
        if not allowed_ip:
            raise AuthIpBlocked

    def refresh_jwt_token(self, user_ip: str, refresh_token: RefreshTokenPayload):
        try:
            token_content = self.verify_jwt_token(refresh_token.refresh)
        except (AuthTokenExpired, AuthTokenInvalid):
            # If these failed for the refresh token, it is time to login again
            # This allows us to force users to login across the platform
            # the frontend client will redirect users to the login page if this
            # is thrown during refresh journey.
            raise AuthTokenInvalid('New login required - impersonation ended')
        user_id = token_content.sub
        user = self.user_service.get_user_for_id(user_id=user_id)
        if user.archived_at is not None:
            raise AuthUserArchived(f'User archived at {user.archived_at}')

        # Check if this user authenticated via OIDC and validate with IDP
        is_oidc_token = token_content.auth_method == AuthenticationMethodEnum.OIDC.value
        if is_oidc_token and token_content.oidc_provider_id:
            self.oidc_service.validate_user_on_refresh(user_id, token_content.oidc_provider_id)
        elif is_oidc_token and not token_content.oidc_provider_id:
            raise InvalidOIDCToken(message='OIDC token missing required provider claim')

        auth_settings = self.get_customer_auth_settings_from_user(user_id=user_id)
        self._verify_ip_whitelist(user_ip, auth_settings)
        return self.refresh_access_token(
            refresh_token.refresh,
            ip_address=user_ip,
        )

    def impersonate_user(
        self,
        access_token: str,
        target_user_id: str,
        ip_address: str | None,
    ) -> Token:
        from src.core.authorization import PermissionService

        auth_service = PermissionService.factory()
        token_content = self.verify_jwt_token(access_token)
        # At this point the impersonator is the sub
        impersonator_user_id = token_content.sub
        is_staff_impersonator_user = auth_service.is_staff_user_id(user_id=impersonator_user_id)
        # Only staff users can impersonate
        if not is_staff_impersonator_user:
            raise AuthMethodNotAllowed('Incorrect permission for impersonation')

        try:
            target_user = self.user_service.get_user_for_id(target_user_id)
        except UserNotFound:
            raise AuthUserNotFound(f'User with id: {target_user_id} not found')

        # Staff users cant impersonate other staff users
        is_staff_user = auth_service.is_staff_user_id(user_id=target_user.id)
        is_target_super_staff_user = auth_service.is_super_staff_user_id(user_id=target_user.id)
        is_super_staff_impersonator_user = auth_service.is_super_staff_user_id(user_id=impersonator_user_id)
        if is_staff_user and not is_super_staff_impersonator_user:
            raise AuthMethodNotAllowed('Non super Staff users can not impersonate other staff users')
        if is_target_super_staff_user:
            raise AuthMethodNotAllowed('Super Staff users can not be impersonated')

        return self.create_auth_token(
            user_id=target_user.id, impersonator_id=impersonator_user_id, ip_address=ip_address
        )

    def cancel_impersonate_user(
        self,
        access_token: str,
        ip_address: str | None,
    ) -> Token:
        from src.core.authorization import PermissionService

        token_content = self.verify_jwt_token(access_token)

        impersonator_user_id = token_content.imp_sub
        is_staff_impersonator_user = PermissionService.factory().is_staff_user_id(user_id=impersonator_user_id)
        # Only staff users can cancel impersonating user
        if not is_staff_impersonator_user:
            raise AuthMethodNotAllowed('Incorrect permission for impersonation')

        return self.create_auth_token(user_id=impersonator_user_id, ip_address=ip_address)

    @classmethod
    def refresh_access_token(
        cls,
        refresh_token: str,
        ip_address: str | None,
    ) -> Token:
        """
        Exposed directly from API to refresh an access token
        """
        token_content = cls.verify_jwt_token(refresh_token)
        return cls.create_auth_token(
            user_id=token_content.sub,
            ip_address=ip_address,
            impersonator_id=token_content.imp_sub,
            auth_method=token_content.auth_method,
            oidc_provider_id=token_content.oidc_provider_id,
        )

    @classmethod
    def create_auth_token(
        cls,
        user_id: NanoIdType,
        ip_address: str | None,
        impersonator_id: str | None = None,
        auth_method: str | None = None,
        oidc_provider_id: str | None = None,
    ) -> Token:
        access_token = cls._create_access_token(
            user_id,
            ip_address=ip_address,
            impersonator_id=impersonator_id,
            auth_method=auth_method,
            oidc_provider_id=oidc_provider_id,
        )
        refresh_token = cls._create_refresh_token(
            user_id,
            ip_address=ip_address,
            impersonator_id=impersonator_id,
            auth_method=auth_method,
            oidc_provider_id=oidc_provider_id,
        )
        return Token(access_token=access_token, refresh_token=refresh_token)

    @classmethod
    def _create_access_token(
        cls,
        user_id: NanoIdType,
        ip_address: str | None,
        impersonator_id: str | None = None,
        auth_method: str | None = None,
        oidc_provider_id: str | None = None,
    ) -> str:
        expires_at = datetime.now(tz=timezone.utc) + settings.AUTH_SETTINGS['ACCESS_TOKEN_LIFETIME']
        return cls._create_token(
            user_id,
            expires_at,
            ip_address=ip_address,
            impersonator_id=impersonator_id,
            auth_method=auth_method,
            oidc_provider_id=oidc_provider_id,
        )

    @classmethod
    def _create_refresh_token(
        cls,
        user_id: NanoIdType,
        ip_address: str | None,
        impersonator_id: str | None = None,
        auth_method: str | None = None,
        oidc_provider_id: str | None = None,
    ) -> str:
        expires_at = datetime.now(tz=timezone.utc) + settings.AUTH_SETTINGS['REFRESH_TOKEN_LIFETIME']
        return cls._create_token(
            user_id,
            expires_at,
            ip_address=ip_address,
            impersonator_id=impersonator_id,
            auth_method=auth_method,
            oidc_provider_id=oidc_provider_id,
        )

    @classmethod
    def _create_token(
        cls,
        sub: str,
        expire: datetime,
        ip_address: str | None = None,
        secret_key: str | None = None,
        impersonator_id: str | None = None,
        auth_method: str | None = None,
        oidc_provider_id: str | None = None,
    ):
        secret_key = secret_key or settings.SECRET_KEY
        jwt_content = {
            'jti': str(uuid.uuid4()),
            'exp': int(expire.timestamp()),
            'sub': sub,
            'imp_sub': impersonator_id,
            'nbf': int(datetime.now(tz=timezone.utc).timestamp()),
            'ip': ip_address or '',
            'auth_method': auth_method,  # Track how user authenticated
            'oidc_provider_id': oidc_provider_id,  # Which OIDC provider (if any)
        }
        encoded_jwt = jwt.encode(jwt_content, secret_key, algorithm=cls._JWT_SIGNING_ALGORITHM)
        return encoded_jwt

    @classmethod
    def is_password_match(cls, plain_password: str, hashed_password: str) -> bool:
        return cls._password_hasher.verify(hashed_password, plain_password)

    @classmethod
    def hash_password(cls, password: str) -> str:
        return cls._password_hasher.hash(password)

    @classmethod
    def password_meets_policy(cls, password: str) -> None:
        meets_policy = len(password) >= 8
        if not meets_policy:
            raise PasswordFailsPolicyCheck

    @classmethod
    def create_challenge_token(cls, email: str, ip_address: str | None) -> str:
        """
        Similar to Access token but uses email as sub with a different
        expiration used to verify magic link
        """
        now = datetime.now(tz=timezone.utc)
        expires_at = now + settings.AUTH_SETTINGS['CHALLENGE_TOKEN_LIFETIME']

        return cls._create_token(email, expires_at, ip_address=ip_address)

    @classmethod
    def create_mfa_token(
        cls,
        email: str,
        ip_address: str | None,
        configured_mfa_methods: list[str] = None,
    ) -> MfaToken:
        """
        Similar to Access token but uses email as sub with a different
        expiration used to verify magic link
        """
        now = datetime.now(tz=timezone.utc)
        expires_at = now + settings.AUTH_SETTINGS['MFA_CODE']
        mfa_secret_key = cls._generate_mfa_token_secret()

        token = cls._create_token(
            email,
            expires_at,
            ip_address=ip_address,
            secret_key=mfa_secret_key,
        )
        return MfaToken(token=token, configured_mfa_methods=configured_mfa_methods or [])

    def send_excel_email_challenge_token(self, email: str) -> AuthenticationChallenge:
        try:
            user = self.user_service.get_user_for_email(email)
        except UserNotFound:
            raise AuthUserNotFound(f'User with email: {email} not found')

        char_pool = list(set(string.ascii_uppercase + string.digits))
        token = generate_custom_nanoid(size=6, char_pool=char_pool)

        Email(
            subject=f'{token} - Burn Notice Log In Code',
            recipients=[email],
            template_name='auth-email-excel-challenge.html',
            context={
                'token': token,
                'full_name': user.full_name,
            },
        ).send()

        return AuthenticationChallenge(
            user_id=user.id,
            email=email,
            token=token,
        )

    def send_email_challenge_link(
        self,
        email: str,
        challenge_type: EmailChallengeTemplatesEnum,
    ) -> AuthenticationChallenge:
        authorization_route = EmailChallengeAuthRoute[challenge_type.value]

        try:
            user = self.user_service.get_user_for_email(email)
        except UserNotFound:
            raise AuthUserNotFound(f'User with email: {email} not found')

        auth_url = self.generate_authentication_url(
            user_id=user.id,
            email=user.email,
            route=authorization_route,
        )

        Email(
            subject='Log in to Burn Notice',
            recipients=[email],
            template_name=challenge_type.value,
            context={
                'auth_challenge_url': auth_url.url,
                'full_name': user.full_name,
            },
        ).send()

        return AuthenticationChallenge(user_id=user.id, email=email, token=auth_url.challenge_token, url=auth_url.url)

    def send_mfa_verification_email(self, email: str):
        try:
            user = self.user_service.get_user_for_email(email)
        except UserNotFound:
            raise AuthUserNotFound(f'User with email: {email} not found')
        mfa_code = self.mfa_email_service.create_email_code(user_id=user.id)
        Email(
            subject=f'{mfa_code.code} - Burn Notice log in code',
            recipients=[user.email],
            template_name='auth-email-mfa.html',
            context={'mfa_code': mfa_code.code},
        ).send()

    def authenticate_with_mfa_code(
        self, email: str, code: str, token: str, mfa_method: MultiFactorMethodEnum = MultiFactorMethodEnum.EMAIL
    ):
        """
        Token is used to verify that a user previously authenticated and is
        on the MFA step. This token would have been issued previously and is
        only good for MFA.

        Enhanced to support both EMAIL and TOTP MFA methods.
        """
        try:
            user = self.user_service.get_user_for_email(email)
        except UserNotFound:
            raise AuthUserNotFound(f'User with email: {email} not found')

        self.verify_mfa_token(token)

        # Route to appropriate MFA verification method
        is_valid = False
        if mfa_method == MultiFactorMethodEnum.EMAIL:
            is_valid = self.mfa_email_service.check_code(user.id, code)
        elif mfa_method == MultiFactorMethodEnum.TOTP:
            # Check TOTP code first
            is_valid = self.totp_service.verify_totp_code(user.id, code)
            # If TOTP fails, try backup codes
            if not is_valid:
                is_valid = self.totp_service.verify_backup_code(user.id, code)
        elif mfa_method == MultiFactorMethodEnum.SMS:
            # Verify SMS code - no backup codes for SMS (use different MFA method as backup)
            is_valid = self.sms_service.verify_sms_code(user.id, code)
        else:
            raise AuthException(f'Unsupported MFA method: {mfa_method}')

        if is_valid:
            return self.create_auth_token(user_id=user.id, ip_address=None)
        else:
            raise AuthChallengeFailed('Invalid MFA code')

    def generate_invitation_url(self, user_id: NanoIdType, email: str) -> AuthenticationUrl:
        """
        If a users settings allow, send them the password setup flow
        Otherwise they can authenticate via email challenge
        """
        auth_settings = self.get_customer_auth_settings_from_user(user_id=user_id)

        if any(method in auth_settings.auth_methods for method in EMAIL_INVITE_AUTH_METHODS):
            route = AuthenticationInitialRoute.VERIFY_EMAIL
        elif any(method in auth_settings.auth_methods for method in PASSWORD_INVITE_AUTH_METHODS):
            route = AuthenticationInitialRoute.CREATE_PASSWORD
        elif any(method in auth_settings.auth_methods for method in LOGIN_INVITE_AUTH_METHODS):
            route = AuthenticationInitialRoute.LOGIN
        else:
            raise AuthMethodNotAllowed('Ambiguous auth route for user invitation')

        auth_url = self.generate_authentication_url(
            user_id=user_id,
            email=email,
            route=route,
        )
        return auth_url

    def generate_authentication_url(
        self,
        user_id: NanoIdType,
        email: str,
        route: str = AuthenticationInitialRoute.VERIFY_EMAIL,
        ip_address: str = None,
    ) -> AuthenticationUrl:
        challenge_token = self.create_challenge_token(email=email, ip_address=None)
        if route == AuthenticationInitialRoute.LOGIN:
            # This should prefill the login page with the correct email
            url = f'{settings.FRONTEND_ORIGIN}/{route}?email={email}'
        else:
            # Other routes for email verification and password creation match React Router patterns
            url = f'{settings.FRONTEND_ORIGIN}/{route}/{user_id}/{challenge_token}'

        return AuthenticationUrl(url=url, challenge_token=challenge_token)

    @classmethod
    def verify_jwt_token(cls, token: str) -> TokenContent:
        if token is None:
            raise AuthTokenInvalid(message='Token missing')
        if not isinstance(token, str):
            raise AuthTokenInvalid(message='Invalid token format')

        try:
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[cls._JWT_SIGNING_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthTokenExpired(message='Token expired')
        except jwt.InvalidTokenError:
            raise AuthTokenInvalid(message='Token invalid')

        return TokenContent(**decoded_token)

    def get_valid_user_from_challenge_token(self, user_id: NanoIdType, token: str) -> UserRead:
        try:
            token_content = self.verify_challenge_token(token)
            user = self.user_service.get_user_for_email(email=token_content.sub)
            # Check the user matches the url user
            if user.id != user_id:
                raise AuthChallengeFailed()
        except (AuthChallengeFailed, UserNotFound):
            raise AuthChallengeFailed('Invalid authentication link')
        except AuthChallengeExpired:
            raise  # Re-raise the same exception
        if not user:
            raise ValueError('Unrecognized user')
        return user

    def verify_challenge_token(self, token: str) -> TokenContent:
        try:
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[self._JWT_SIGNING_ALGORITHM])

        except jwt.ExpiredSignatureError:
            raise AuthChallengeExpired

        except jwt.InvalidTokenError:
            raise AuthChallengeFailed

        token_content = TokenContent(**decoded_token)
        # Once token has been validated blacklist it
        try:
            self.challenge_token_service.record_used_challenge_token(
                token_content.jti, expiration_at=datetime.fromtimestamp(token_content.exp)
            )
        except IntegrityError:
            raise AuthChallengeTokenUsed
        return token_content

    @classmethod
    def verify_mfa_token(cls, token: str) -> TokenContent:
        secret = cls._generate_mfa_token_secret()
        try:
            decoded_token = jwt.decode(token, secret, algorithms=[cls._JWT_SIGNING_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthTokenExpired(message='Token expired')
        except jwt.InvalidTokenError:
            raise AuthTokenInvalid(message='Token invalid')

        return TokenContent(**decoded_token)

    def get_valid_user_from_mfa_token(self, email: str, token: str) -> UserRead:
        """
        Validate MFA token and return the user.
        Used during TOTP setup flow when user only has MFA token (not full JWT).
        """
        try:
            token_content = self.verify_mfa_token(token)
            # Verify the email in token matches the provided email
            if token_content.sub != email:
                raise AuthTokenInvalid(message='Token email mismatch')

            user = self.user_service.get_user_for_email(email)
            return user

        except UserNotFound:
            raise AuthUserNotFound(f'User with email: {email} not found')

    @staticmethod
    def _generate_mfa_token_secret() -> str:
        """
        Repeatable hashed key based off the secret key
        """
        return create_derived_key(settings.SECRET_KEY)

    def _determine_minimum_settings(self, settings_list: List[CustomerAuthSettingsRead]) -> UserAuthSettings:
        include_magic_link = True
        include_password = True
        include_azure_sso = False
        include_oidc = False
        ip_whitelist = None
        refresh_frequency = 900
        oidc_provider = None
        mfa_settings = set()

        for entity_setting in settings_list:
            if (
                entity_setting.enabled_auth_methods is not None
                and AuthenticationMethodEnum.PASSWORD in entity_setting.enabled_auth_methods
            ):
                include_password = True
            if (
                entity_setting.enabled_auth_methods is None
                or AuthenticationMethodEnum.MAGIC_LINK not in entity_setting.enabled_auth_methods
            ):
                include_magic_link = False
            if (
                entity_setting.enabled_auth_methods is not None
                and AuthenticationMethodEnum.AZURE_SSO in entity_setting.enabled_auth_methods
            ):
                include_azure_sso = True
            if (
                entity_setting.enabled_auth_methods is not None
                and AuthenticationMethodEnum.OIDC in entity_setting.enabled_auth_methods
            ):
                include_oidc = True
                # Take the first OIDC provider found
                # TODO: To support multiple providers, would need UX to select entity context first
                if entity_setting.oidc_provider_id and not oidc_provider:
                    provider = OIDCProvider.get_or_none(id=entity_setting.oidc_provider_id)
                    if provider:
                        oidc_provider = OIDCProviderOption(
                            provider_id=provider.id,
                            display_name=provider.display_name,
                            entity_id=entity_setting.entity_id,
                        )
                elif entity_setting.oidc_provider_id and oidc_provider:
                    # Full support for this would require entity context selection UX
                    # Like show them a screen of which entities are available to access and track them on the FE
                    # Multiple OIDC providers found - not currently supported
                    raise NotImplementedError('User belongs to multiple entities with OIDC providers.')

            if entity_setting.mfa_methods is not None:
                for mfa_method in entity_setting.mfa_methods:
                    mfa_settings.add(str(mfa_method))
            if entity_setting.ip_whitelist:
                ip_whitelist = entity_setting.ip_whitelist
            if (
                entity_setting.token_refresh_frequency is not None
                and entity_setting.token_refresh_frequency < refresh_frequency
            ):
                refresh_frequency = entity_setting.token_refresh_frequency

        # @todo this function is a mess and idk what to do about it.
        auth_methods = []
        if include_password:
            auth_methods.append(AuthenticationMethodEnum.PASSWORD.value)
        if include_magic_link:
            auth_methods.append(AuthenticationMethodEnum.MAGIC_LINK.value)
        if include_azure_sso:
            auth_methods.append(AuthenticationMethodEnum.AZURE_SSO.value)
        if include_oidc:
            auth_methods.append(AuthenticationMethodEnum.OIDC.value)

        return UserAuthSettings(
            mfa_methods=list(mfa_settings) if mfa_settings else [],
            auth_methods=auth_methods,
            ip_whitelist=ip_whitelist,
            token_refresh_frequency=refresh_frequency,
            oidc_provider=oidc_provider,
        )

    def get_customer_auth_settings(self, user_id: NanoIdType, customer_ids: List[NanoIdType]) -> UserAuthSettings:
        from src.core.authorization import PermissionService

        is_staff_user = PermissionService.factory().is_staff_user_id(user_id=user_id)
        # staff user bypass check IP check
        if is_staff_user:
            return self.get_staff_auth_settings()

        # otherwise attempt to take the strictest settings from customer memberships
        customer_settings = self.customer_auth_settings_service.list_customer_auth_settings(customer_ids=customer_ids)
        return self._determine_minimum_settings(customer_settings)

    def get_staff_auth_settings(self):
        """
        Determines appropriate staff authentication settings based on application settings.
        STAFF_AUTHENTICATION_METHODS can be a list of methods (e.g., ['OIDC', 'PASSWORD'])
        """
        auth_methods = []
        mfa_methods = []
        staff_oidc_provider = None

        # Check each enabled authentication method
        if AuthenticationMethodEnum.OIDC.value in settings.STAFF_AUTHENTICATION_METHODS:
            # Get virtual staff OIDC provider from environment
            try:
                staff_provider = self.oidc_service.get_staff_provider()
                staff_oidc_provider = OIDCProviderOption(
                    provider_id=staff_provider.id,
                    display_name=staff_provider.display_name,
                    customer_id=None,  # Staff provider isn't tied to a specific customer
                )
                auth_methods.append(AuthenticationMethodEnum.OIDC)
            except (OIDCStaffProviderMissing, OIDCDiscoveryError):
                # If OIDC provider fails to load, skip it
                pass

        if AuthenticationMethodEnum.PASSWORD.value in settings.STAFF_AUTHENTICATION_METHODS:
            auth_methods.append(AuthenticationMethodEnum.PASSWORD)
            # Password auth supports all MFA methods
            mfa_methods.extend([MultiFactorMethodEnum.EMAIL, MultiFactorMethodEnum.SMS, MultiFactorMethodEnum.TOTP])

        if AuthenticationMethodEnum.MAGIC_LINK.value in settings.STAFF_AUTHENTICATION_METHODS:
            auth_methods.append(AuthenticationMethodEnum.MAGIC_LINK)

        if not auth_methods:
            raise AuthException(
                f'No valid authentication methods configured. STAFF_AUTHENTICATION_METHODS: {settings.STAFF_AUTHENTICATION_METHODS}'
            )

        return UserAuthSettings(
            mfa_methods=list(set(mfa_methods)),
            auth_methods=auth_methods,
            oidc_provider=staff_oidc_provider,
        )

    def initiate_totp_setup(self, user_id: NanoIdType, user_email: str) -> TOTPSetupResponse:
        """
        Initiate TOTP setup for a user.
        Returns QR code and backup codes for user to save.
        """
        # Create TOTP secret
        totp_record, plain_secret = self.totp_service.create_totp_secret(user_id)

        # Generate QR code
        qr_code = self.totp_service.generate_qr_code(plain_secret, user_email)

        return TOTPSetupResponse(secret=plain_secret, qr_code=qr_code, backup_codes=totp_record.backup_codes)

    def complete_totp_setup(self, user_id: NanoIdType, verification_code: str) -> bool:
        """
        Complete TOTP setup by verifying the first code from the authenticator.

        Raises:
            ValueError: If max verification attempts exceeded
        """
        return self.totp_service.enable_totp(user_id, verification_code)

    def disable_totp_for_user(self, user_id: NanoIdType) -> bool:
        """
        Disable TOTP for a user.
        Should also remove TOTP from entity auth settings MFA methods.
        """
        return self.totp_service.disable_totp(user_id)

    def initiate_sms_setup(self, user_id: NanoIdType, phone_number: str) -> SMSSetupResponse:
        """
        Initiate SMS MFA setup for a user.
        Sends verification code to phone number and returns masked phone.
        """
        # Create SMS MFA secret and send verification code
        self.sms_service.create_sms_secret(user_id, phone_number)

        # Return masked phone number
        masked_phone = self.sms_service.mask_phone_number(phone_number)
        return SMSSetupResponse(phone_number=masked_phone, code_sent=True)

    def complete_sms_setup(self, user_id: NanoIdType, verification_code: str) -> bool:
        """
        Complete SMS MFA setup by verifying the code sent via SMS.

        Raises:
            ValueError: If max verification attempts exceeded
        """
        return self.sms_service.enable_sms(user_id, verification_code)

    def send_sms_login_code(self, user_id: NanoIdType) -> str:
        """
        Send SMS verification code for login flow.
        Returns masked phone number.

        Raises:
            ValueError: If user doesn't have SMS MFA enabled
        """
        return self.sms_service.send_login_code(user_id)

    def disable_sms_for_user(self, user_id: NanoIdType) -> bool:
        """
        Disable SMS MFA for a user.
        Should also remove SMS from entity auth settings MFA methods.
        """
        return self.sms_service.disable_sms(user_id)
