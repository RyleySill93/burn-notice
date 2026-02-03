import os
from datetime import timedelta
from typing import Any

from decouple import Choices, Csv, config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_MODULE = 'src'
SRC_DIR = os.path.join(BASE_DIR, BASE_MODULE)
# Used for local file storage
TEMP_DIR = os.path.join(BASE_DIR, 'tmp')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# pdf dir
PDF_CSS_DIR = os.path.join(SRC_DIR, 'platform/pdf/css')

COMPANY_NAME = config('COMPANY_NAME')
COMPANY_FULL_NAME = config('VITE_COMPANY_NAME')
SUPPORT_EMAIL = config('VITE_SUPPORT_EMAIL')
COMPANY_WEBSITE = config('VITE_COMPANY_WEBSITE')
COMPANY_LOGO_URL = config('VITE_LOGO_URL')

# API Documentation
API_TITLE = config('API_TITLE', default=f'{COMPANY_NAME} API')
API_DESCRIPTION = config('API_DESCRIPTION', default='API Documentation')

HOST = 'http://127.0.0.1'
SECRET_KEY = config('SECRET_KEY', default='secret')
DEBUG = config('DEBUG', default=False, cast=bool)
ENVIRONMENT = config(
    'ENVIRONMENT', default='local', cast=Choices(['local', 'testing', 'demo', 'staging', 'production'])
)
IS_LOCAL = ENVIRONMENT == 'local'
IS_PRODUCTION = ENVIRONMENT == 'production'
IS_STAGING = ENVIRONMENT == 'staging'
IS_DEMO = ENVIRONMENT == 'demo'
IS_TESTING = ENVIRONMENT == 'testing'  # Set in conf.test
IS_DEPLOYED_ENV = IS_PRODUCTION or IS_STAGING or IS_DEMO
SERVER_NAME = config('EC2_INSTANCE_ID', default='unknown')

BACKEND_CORS_ORIGINS = config(
    'BACKEND_CORS_ORIGINS', default='http://localhost:5173', cast=lambda v: list(v.split(','))
)
CORS_ALLOWED_METHODS = config(
    'CORS_ALLOWED_METHODS', default='GET,POST,PUT,PATCH,DELETE,OPTIONS', cast=lambda v: list(v.split(','))
)
CORS_ALLOWED_HEADERS = config(
    'CORS_ALLOWED_HEADERS',
    default='Accept,Accept-Language,Content-Type,Content-Language,Authorization,X-Requested-With',
    cast=lambda v: list(v.split(',')),
)

# Security Headers Configuration
ENABLE_SECURITY_HEADERS = config('ENABLE_SECURITY_HEADERS', default=True, cast=bool)
# Only enable HSTS in production environments to avoid development issues
ENABLE_HSTS = config('ENABLE_HSTS', default=IS_DEPLOYED_ENV, cast=bool)

# Content Security Policy - Adjust based on your actual resource needs
# This is a restrictive policy that only allows resources from the same origin
CSP_POLICY = config(
    'CSP_POLICY',
    default=(
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # unsafe-eval needed for some frontend frameworks
        "style-src 'self' 'unsafe-inline'; "  # unsafe-inline needed for inline styles
        "img-src 'self' data: https:; "  # Allow images from self, data URIs, and any HTTPS source
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
)

API_PREFIX = ''

ATOMIC_REQUESTS = config('ATOMIC_REQUESTS', default=True, cast=bool)
LOG_LEVEL = config('LOG_LEVEL', 'INFO')

AUTH_SETTINGS = {
    'CHALLENGE_TOKEN_LIFETIME': timedelta(hours=24),
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'MFA_CODE': timedelta(minutes=20),  # Increased for TOTP setup flow with QR scanning
    'REFRESH_TOKEN_LIFETIME': timedelta(days=90),  # 'BLACKLIST_AFTER_ROTATION': True,
    'EXCEL_CHALLENGE_TOKEN_LIFETIME': timedelta(minutes=15),
}

# Support both DATABASE_URL (Railway) and individual vars (local)
DATABASE_URL = config('DATABASE_URL', default=None)
if DATABASE_URL:
    # Parse DATABASE_URL: postgresql://user:password@host:port/dbname
    from urllib.parse import urlparse
    parsed = urlparse(DATABASE_URL)
    DB_NAME = parsed.path[1:]  # Remove leading /
    DB_USER = parsed.username
    DB_PASSWORD = parsed.password
    DB_HOST = parsed.hostname
    DB_PORT = parsed.port or 5432
else:
    DB_NAME = config('DB_NAME')
    DB_USER = config('DB_USER')
    DB_PASSWORD = config('DB_PASSWORD', default='dev1')
    DB_HOST = config('DB_HOST', default='127.0.0.1')
    DB_PORT = config('DB_PORT', default=5432, cast=int)
DB_HOST_RO = config('DB_HOST_RO', default=DB_HOST)
DB_LOG_STATEMENTS = config('DB_LOG_STATEMENTS', default=False, cast=bool)
DB_ENCRYPTION_KEY = config('DB_ENCRYPTION_KEY', default='default-key')
DB_ENCRYPTION_SALT = config('DB_ENCRYPTION_SALT', default=f'{COMPANY_NAME}-encryption-salt')

# Event Bus
EVENT_BUS_SUBSCRIBER_REGISTRY: list[Any] = []

# Define boundaries to ensure
BOUNDARIES = [
    'network.queue',
    'platform.event',
    'platform.files',
    'platform.audit',
    'platform.slack',
    'core.user',
    'core.authentication',
    'core.authorization',
    'core.invitation',
    'app.engineers',
    'app.usage',
    'app.leaderboard',
]

# Support REDIS_URL (Railway) or individual vars (local)
REDIS_URL = config('REDIS_URL', default=None)
if REDIS_URL:
    from urllib.parse import urlparse
    parsed_redis = urlparse(REDIS_URL)
    REDIS_DOMAIN = parsed_redis.hostname
    REDIS_PORT = parsed_redis.port or 6379
else:
    REDIS_DOMAIN = config('REDIS_DOMAIN', default='localhost')
    REDIS_PORT = config('REDIS_PORT', default=6379)
    REDIS_URL = f'redis://{REDIS_DOMAIN}:{REDIS_PORT}'

FRONTEND_ORIGIN = config('FRONTEND_ORIGIN', default='http://localhost:5173')
BACKEND_ORIGIN = config('BACKEND_ORIGIN', default='http://localhost:80')

# Document Storage
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='burn-notice-files')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default=None)
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default=None)
AWS_REGION_NAME = config('AWS_REGION_NAME', default='us-east-1')
AWS_SES_ACCESS_KEY_ID = config('AWS_SES_ACCESS_KEY_ID', default=None)
AWS_SES_SECRET_ACCESS_KEY = config('AWS_SES_SECRET_ACCESS_KEY', default=None)
AWS_SNS_ACCESS_KEY_ID = config('AWS_SNS_ACCESS_KEY_ID', default=None)
AWS_SNS_SECRET_ACCESS_KEY = config('AWS_SNS_SECRET_ACCESS_KEY', default=None)

# Email
EMAIL_FROM_ADDRESS = config('EMAIL_FROM_ADDRESS', default='noreply@burn-notice.app')
EMAIL_BACKEND = config('EMAIL_BACKEND', default='file', cast=Choices(['file', 'mailpit', 'live']))
# Used for mailpit only
EMAIL_SMTP_PORT = config('EMAIL_SMTP_PORT', default=1025)
EMAIL_SMTP_HOST = config('EMAIL_SMTP_PORT', default='localhost')

# SMS
SMS_BACKEND = config('SMS_BACKEND', default='file', cast=Choices(['file', 'mailpit', 'live']))

# Dramatiq Settings
DRAMATIQ_EAGER_MODE = config('DRAMATIQ_EAGER_MODE', default=False, cast=bool)
DRAMATIQ_SECRET_KEY = config('DRAMATIQ_SECRET_KEY', default='secret')

# Azure
AZURE_TENANT_ID = config('AZURE_TENANT_ID', default=None)
AZURE_CLIENT_ID = config('AZURE_CLIENT_ID', default=None)
AZURE_CLIENT_SECRET = config('AZURE_CLIENT_SECRET', default=None)
AZURE_REDIRECT_URI = f'{FRONTEND_ORIGIN}/auth/azure-sso-callback'

# Staff Authentication Configuration
# Comma-separated list of allowed authentication methods for staff (e.g., 'OIDC,PASSWORD')
STAFF_AUTHENTICATION_METHODS = config(
    'STAFF_AUTHENTICATION_METHODS', default='OIDC', cast=Csv(post_process=lambda methods: [m.upper() for m in methods])
)
STAFF_OIDC_PROVIDER_ID = 'oidc-staff'
STAFF_OIDC_CLIENT_ID = config('STAFF_OIDC_CLIENT_ID', default=None)
STAFF_OIDC_CLIENT_SECRET = config('STAFF_OIDC_CLIENT_SECRET', default=None)
STAFF_OIDC_ISSUER = config('STAFF_OIDC_ISSUER', default=None)
STAFF_OIDC_AUTHORIZATION_ENDPOINT = config('STAFF_OIDC_AUTHORIZATION_ENDPOINT', default=None)
STAFF_OIDC_TOKEN_ENDPOINT = config('STAFF_OIDC_TOKEN_ENDPOINT', default=None)
STAFF_OIDC_USERINFO_ENDPOINT = config('STAFF_OIDC_USERINFO_ENDPOINT', default=None)
STAFF_OIDC_JWKS_URI = config('STAFF_OIDC_JWKS_URI', default=None)
STAFF_OIDC_AUTO_CREATE_USERS = config('STAFF_OIDC_AUTO_CREATE_USERS', default=True, cast=bool)

# Sendgrid
SENDGRID_API_KEY = config('SENDGRID_API_KEY', default=None)


# Sentry
SENTRY_DSN = config('SENTRY_DSN', default=None)
SENTRY_DEFAULT_SAMPLE_RATE = config('SENTRY_DEFAULT_SAMPLE_RATE', default=1, cast=int)

# Slack
SLACK_EVENT_CHANNEL = config('SLACK_EVENT_CHANNEL', default='#test-slack-client')
SLACK_BOT_TOKEN = config('SLACK_BOT_TOKEN', default=None)
SLACK_SIGNING_SECRET = config('SLACK_SIGNING_SECRET', default=None)
SLACK_LEADERBOARD_WEBHOOK_URL = config('SLACK_LEADERBOARD_WEBHOOK_URL', default=None)

# AI
OPENAI_API_KEY = config('OPENAI_API_KEY', default=None)
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default=None)
AI_AUDIT_ENABLED = config('AI_AUDIT_ENABLED', default=True)

# Telemetry
TELEMETRY_ENABLED = config('TELEMETRY_ENABLED', default=False, cast=bool)
TELEMETRY_CONSOLE_LOG = config('TELEMETRY_CONSOLE_LOG', default=False, cast=bool)
TELEMETRY_EXPORT = config('TELEMETRY_EXPORT', default=False, cast=bool)
TRACE_EXPORT_ENDPOINT = config('TRACE_EXPORT_ENDPOINT', default='http://localhost:4317')

# Mocks
USE_MOCK_WEBSOCKETS = config('USE_MOCK_DRAMATIQ_BROKER', default=False, cast=bool)
USE_MOCK_DRAMATIQ_BROKER = config('USE_MOCK_DRAMATIQ_BROKER', default=False, cast=bool)
USE_MOCK_SENTRY_CLIENT = config('USE_MOCK_SENTRY_CLIENT', default=False, cast=bool)
USE_MOCK_FILE_CLIENT = config('USE_MOCK_FILE_CLIENT', default=False, cast=bool)
USE_MOCK_EMAIL_CLIENT = config('USE_MOCK_EMAIL_CLIENT', default=False, cast=bool)
USE_MOCK_SMS_CLIENT = config('USE_MOCK_SMS_CLIENT', default=False, cast=bool)
USE_MOCK_SLACK_CLIENT = config('USE_MOCK_SLACK_CLIENT', default=False, cast=bool)
USE_MOCK_OPENAI_CLIENT = config('USE_MOCK_OPENAI_CLIENT', default=False, cast=bool)
USE_MOCK_ANTHROPIC_CLIENT = config('USE_MOCK_ANTHROPIC_CLIENT', default=False, cast=bool)
