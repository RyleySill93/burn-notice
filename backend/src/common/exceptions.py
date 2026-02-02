import re
from typing import Any

import sentry_sdk
from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger


class InternalException(Exception):
    """
    All internal exceptions should inherit from this. We are handled
    vaguely publicly
    """

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Internal failure.'
    default_code = 'internal_failure'

    def __init__(self, message: str | None = None, context: dict[Any, Any] | Any = None):
        self.message = message or self.default_detail
        self.context = context or dict()

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.message})'


class APIException(Exception):
    """
    API view layer exceptions
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid Request.'
    default_code = 'invalid_request'

    # Match the internal interface message
    def __init__(self, message: str | None = None, code: int | None = None, error_type: str | None = None):
        self.message = message or self.default_detail
        self.code = code or self.status_code
        self.error_type = error_type


async def internal_exception_handler(request: Request, exc: InternalException) -> JSONResponse:
    """
    This catches validation errors and is registered at the app level
    """
    logger.exception(exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({'detail': exc.message}),
    )


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    This catches validation errors and is registered at the app level
    """
    content = {'detail': exc.message}
    if exc.error_type:
        content['error_type'] = exc.error_type
    return JSONResponse(
        status_code=exc.code,
        content=jsonable_encoder(content),
    )


async def inbound_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    This catches pydantic validation errors and is registered at the app level
    """
    # Create a custom fingerprint based on the error locations
    details = exc.errors()

    # Create a fingerprint based on the error locations
    error_locations = []
    for error in details:
        # Extract the field path that's missing/invalid
        if 'loc' in error:
            # Join the location parts to create a path string
            loc_path = '.'.join(str(part) for part in error['loc'])
            error_locations.append(f"{error['type']}:{loc_path}")

    if error_locations:
        generalized_errors = []
        for location in error_locations:
            # Safely split and handle missing colons
            # Convert "extra_forbidden:body.0.my_field" to "extra_forbidden:my_field"
            parts = location.split(':', 1)
            if len(parts) != 2:
                continue  # Skip malformed locations

            error_type, field_path = parts
            clean_path = re.sub(r'\.[0-9]+(?=\.|$)', '', field_path)
            generalized_errors.append(f'{error_type}:{clean_path}')

        if generalized_errors:
            with sentry_sdk.configure_scope() as scope:
                transaction_name = scope.transaction.name if scope.transaction else 'unknown'
                fingerprint_parts = [transaction_name] + list(set(generalized_errors))
                scope.fingerprint = fingerprint_parts

    # We want to know about these:
    sentry_sdk.capture_exception()

    modified_details = []
    for error in details:
        modified_details.append(
            {
                'loc': error['loc'],
                'message': error['msg'],
                'input': error['input'],
                'type': error['type'],
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({'detail': modified_details}),
    )
