from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    These headers help protect against common web vulnerabilities.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        if settings.ENABLE_SECURITY_HEADERS:
            # Prevent clickjacking attacks by disallowing the page to be embedded in frames
            response.headers['X-Frame-Options'] = 'DENY'

            # Prevent MIME type sniffing
            response.headers['X-Content-Type-Options'] = 'nosniff'

            # Enable XSS protection in older browsers (modern browsers have this by default)
            response.headers['X-XSS-Protection'] = '1; mode=block'

            # Control what information is sent in the Referer header
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

            # Restrict browser features and APIs
            response.headers['Permissions-Policy'] = (
                'accelerometer=(), camera=(), geolocation=(), gyroscope=(), '
                'magnetometer=(), microphone=(), payment=(), usb=()'
            )

            # Content Security Policy - Restrict resource loading to prevent XSS
            if settings.CSP_POLICY:
                response.headers['Content-Security-Policy'] = settings.CSP_POLICY

            # HTTP Strict Transport Security - Force HTTPS connections
            # Only enable in production to avoid development issues
            if settings.ENABLE_HSTS:
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        return response
