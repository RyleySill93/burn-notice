from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from loguru import logger
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.errors import ServerErrorMiddleware

from src import settings
from src.common.exceptions import (
    APIException,
    InternalException,
    api_exception_handler,
    inbound_validation_exception_handler,
    internal_exception_handler,
)
from src.common.middleware import HTTPAppContextMiddleware
from src.common.request import RequestResponseMiddleware
from src.common.security_headers import SecurityHeadersMiddleware
from src.network.database.middleware import HTTPSessionManagerMiddleware
from src.network.http.router import api_router

if not settings.USE_MOCK_SENTRY_CLIENT:

    def traces_sampler(sampling_context):
        """
        Custom filter for sentry traces
        """
        IGNORE_PATHS = {
            # Healthchecks using up the majority of our transaction bandwidth
            '/healthcheck/api',
        }
        if 'asgi_scope' in sampling_context:
            if sampling_context['asgi_scope']['path'] in IGNORE_PATHS:
                # Dont send for anything in ignore
                return 0

        return settings.SENTRY_DEFAULT_SAMPLE_RATE

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        ignore_errors=[APIException],
        environment=settings.ENVIRONMENT,
        integrations=[
            # Both integrations must be instantiated
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        enable_tracing=False,
    )


async def on_startup():
    if not settings.USE_MOCK_WEBSOCKETS:
        from src.setup import configure_broadcast, configure_websockets

        configure_broadcast()
        ConnectionManager = configure_websockets()
        await ConnectionManager.subscribe()

    logger.info(f'{server.title} is ready!')
    logger.info(f'check out API docs here: {settings.HOST}/docs')


async def on_shutdown():
    if not settings.USE_MOCK_WEBSOCKETS:
        # Shut down the websocket connection manager which is running separately
        from src.network.websockets.connection import ConnectionManager

        await ConnectionManager.unsubscribe()

    logger.info('💀 Shutting down!')


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


server = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    openapi_url=f'{settings.API_PREFIX}/openapi.json' if settings.IS_LOCAL else None,
    generate_unique_id_function=lambda route: route.name,
    lifespan=lifespan,
    redirect_slashes=False,
    version='0.0.1',
    docs_url='/docs' if settings.IS_LOCAL else None,
    redoc_url='/redoc' if settings.IS_LOCAL else None,
    separate_input_output_schemas=False,
)

# Middlewares are inserted(0) last will run first!
# Add security headers to all responses
server.add_middleware(SecurityHeadersMiddleware)
# Handle database transaction for request lifecycle
server.add_middleware(HTTPSessionManagerMiddleware, commit_on_success=settings.ATOMIC_REQUESTS)
server.add_middleware(RequestResponseMiddleware)
server.add_middleware(HTTPAppContextMiddleware)

if settings.DEBUG:
    # This serves up traceback responses
    server.add_middleware(ServerErrorMiddleware, debug=True)
    # We can use the below to also drop into a breakpoint on error
    # from pdbr.middlewares.starlette import PdbrMiddleware
    # server.add_middleware(PdbrMiddleware, debug=True)

# Custom exception handler
server.exception_handler(RequestValidationError)(inbound_validation_exception_handler)
server.exception_handler(InternalException)(internal_exception_handler)
server.exception_handler(APIException)(api_exception_handler)


# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    server.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=settings.CORS_ALLOWED_METHODS,
        allow_headers=settings.CORS_ALLOWED_HEADERS,
    )

server.include_router(api_router, prefix=settings.API_PREFIX)
