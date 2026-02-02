from src.common.enum import BaseEnum


class MultiFactorMethodEnum(BaseEnum):
    SMS = 'SMS'
    EMAIL = 'EMAIL'
    TOTP = 'TOTP'


class MFAMethodTypeEnum(BaseEnum):
    """Database enum for MFA secret types"""

    TOTP = 'TOTP'
    SMS = 'SMS'


class AuthenticationMethodEnum(BaseEnum):
    PASSWORD = 'PASSWORD'
    MAGIC_LINK = 'MAGIC_LINK'
    AZURE_SSO = 'AZURE_SSO'
    OIDC = 'OIDC'


class AuthenticationInitialRoute(BaseEnum):
    VERIFY_EMAIL = 'verify-email'
    CREATE_PASSWORD = 'create-password'
    LOGIN = 'login'


# These are redirected to password creation after invite
PASSWORD_INVITE_AUTH_METHODS = [
    AuthenticationMethodEnum.PASSWORD,
]


# These are redirected to email verification after invite
EMAIL_INVITE_AUTH_METHODS = [
    AuthenticationMethodEnum.MAGIC_LINK,
]


# All SSO's should be redirected to login
LOGIN_INVITE_AUTH_METHODS = [
    AuthenticationMethodEnum.AZURE_SSO,
    AuthenticationMethodEnum.OIDC,
]


class EmailChallengeTemplatesEnum(BaseEnum):
    MAGIC_LINK = 'auth-email-challenge.html'
    PASSWORD_CREATE = 'auth-password-create.html'
    PASSWORD_RESET = 'auth-password-reset.html'


EmailChallengeAuthRoute = {
    EmailChallengeTemplatesEnum.MAGIC_LINK: 'verify-email',
    EmailChallengeTemplatesEnum.PASSWORD_CREATE: 'create-password',
    EmailChallengeTemplatesEnum.PASSWORD_RESET: 'reset-password',
}
