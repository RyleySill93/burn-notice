import time
import uuid

from fastapi import status
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

from src.common import context


def get_user_ip_address_from_request(request: Request):
    x_forwarded_for = request.headers.get('x-forwarded-for')
    return get_user_ip_address_from_header(x_forwarded_for)


def get_user_ip_address_from_header(forwarded_header: str) -> str:
    """
    Expects the result of "x-forwarded-for" which will be
    a list of IPs separated by a ',' accounting for all
    proxy servers encountered
    """
    user_ip = forwarded_header.split(',')[0] if forwarded_header else ''
    return user_ip.strip()


def _get_additional_request_log_meta(request: Request, start_time: float):
    user_agent = request.headers.get('user-agent', 'unknown')
    duration = round((time.time() - start_time), 3)
    http_method = request.method
    user_ip = get_user_ip_address_from_request(request)
    client_host = request.client.host

    return dict(
        endpoint=request['path'],
        user_agent=user_agent,
        duration=duration,
        http_method=http_method,
        user_ip=user_ip,
        client_host=client_host,
    )


def _get_request_id(request: Request) -> str:
    # This is set in nginx in non-local environments
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    return request_id


class RequestResponseMiddleware(BaseHTTPMiddleware):
    """
    Inject request to context and to loggers downstream of uvicorn
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        start_time = time.time()
        request_id = _get_request_id(request)

        # Set application context request id to match
        context.set_request_id(request_id)
        # Uses context vars to bind any kwargs passed through
        with logger.contextualize(
            request_id=request_id,
        ):
            try:
                response = await call_next(request)
            except Exception:
                logger.error(
                    f'{request.client.host}:{request.client.port} {request.method.upper()} {request["path"]} {request.scope["type"].upper()} {status.HTTP_500_INTERNAL_SERVER_ERROR}',
                    http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    **_get_additional_request_log_meta(request, start_time=start_time),
                )
                raise
            else:
                level = response.status_code // 100
                if level == 4:
                    log_level = logger.warning
                elif level == 5:
                    log_level = logger.error
                else:
                    log_level = logger.info

                log_level(
                    f'{request.client.host}:{request.client.port} {request.method.upper()} {request["path"]} {request.scope["type"].upper()} {response.status_code}',
                    http_status_code=response.status_code,
                    **_get_additional_request_log_meta(request, start_time=start_time),
                )

        return response
