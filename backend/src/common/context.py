"""
Used to track global application context
User information
Request information
API path information
Used for database audits, request logging etc.
"""

import uuid
from contextvars import ContextVar, Token
from typing import Any, Dict

import ddtrace
from sentry_sdk import (
    set_tag as set_sentry_tag,
)
from sentry_sdk import (
    set_user as set_sentry_user,
)

from src import settings
from src.common.enum import BaseEnum

_app_context: ContextVar[Dict[str, Any] | None] = ContextVar('_app_context', default=None)

# System
_user_type_key = 'user'
_user_id_key = 'user_id'
_api_key_id_key = 'api_key_id'
_impersonator_id_key = 'impersonator_id'
_request_id_key = 'request_id'

# Application
_event_id_key = 'event_id'
_event_type_key = 'event_type'
_breadcrumb_key = 'breadcrumb'
_event_context_key = 'event_context'
_unknown = 'UNKNOWN'


class AppContextUserType(BaseEnum):
    UNKNOWN = _unknown  # Default but should be overridden by every entry point
    USER = 'U'  # Implies data was modified by App user
    API = 'A'  # Implies data was modified by API key
    MANUAL = 'M'  # Implies data was modified by engineer
    SYSTEM = 'S'  # Implies data was modified through scheduled system process


def reset(token: Token[Dict[str, Any] | None]) -> None:
    _app_context.reset(token)


def initialize(
    user_type: AppContextUserType = AppContextUserType.UNKNOWN,
    user_id: str | None = None,
    impersonator_id: str | None = None,
    request_id: str | None = None,
    breadcrumb: str | None = None,
    event_id: uuid.UUID | None = None,
    event_type: str | None = None,
    event_context: Dict[str, Any] | None = None,
) -> Token[Dict[str, Any] | None]:
    context = {
        _user_type_key: user_type,
        _user_id_key: user_id,
        _impersonator_id_key: impersonator_id,
        _request_id_key: request_id,
        _event_id_key: event_id or str(uuid.uuid4()),
        _event_type_key: event_type or _unknown,
        _breadcrumb_key: breadcrumb,
        _event_context_key: event_context,
    }
    token = _app_context.set(context)
    return token


def set_user(
    user_type: AppContextUserType,
    user_id: str | None = None,
    api_key_id: str | None = None,
    impersonator_id: str | None = None,
) -> None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')

    app_ctx[_user_type_key] = user_type
    app_ctx[_user_id_key] = user_id
    app_ctx[_api_key_id_key] = api_key_id
    set_sentry_user(dict(id=user_id))
    # This sucks but ddog is patched ahead of where these are applied
    if settings.TELEMETRY_ENABLED:
        dd_tags: Dict[str | bytes, Any] = {'user_id': user_id}
        if impersonator_id:
            dd_tags['impersonator_id'] = impersonator_id

        if api_key_id:
            dd_tags['api_key_id'] = api_key_id

        current_span = ddtrace.tracer.current_root_span()
        if current_span is not None:
            current_span.set_tags(dd_tags)


def set_impersonator_id(impersonator_id: str) -> None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    app_ctx[_impersonator_id_key] = impersonator_id


def set_request_id(request_id: str) -> None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    app_ctx[_request_id_key] = request_id
    set_sentry_tag('request_id', request_id)
    # This sucks but ddog is patched ahead of where these are applied
    if settings.TELEMETRY_ENABLED:
        current_span = ddtrace.tracer.current_root_span()
        if current_span is not None:
            current_span.set_tags({'request_id': request_id})


def set_breadcrumb(breadcrumb: str) -> None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    app_ctx[_breadcrumb_key] = breadcrumb


def set_event_id(event_id: uuid.UUID) -> None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    app_ctx[_event_id_key] = str(event_id)


def set_event_type(event_type: str) -> None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    app_ctx[_event_type_key] = str(event_type)


def set_event_context(event_context: str) -> None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    app_ctx[_event_context_key] = event_context


def get_request_id() -> str:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    return str(app_ctx[_request_id_key])


def get_safe_request_id() -> str | None:
    """
    safely accessible at anypoint in application lifecycle
    """
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx:
        return app_ctx.get(_request_id_key)
    return None


def get_user_id() -> str:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    return str(app_ctx[_user_id_key])


def get_impersonator_id() -> str | None:
    """
    Safely accessible at anypoint in application lifecycle
    """
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx:
        return app_ctx.get(_impersonator_id_key)
    return None


def get_safe_user_id() -> str | None:
    """
    Safely accessible at anypoint in application lifecycle
    """
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx:
        return app_ctx.get(_user_id_key)
    return None


def get_user_type() -> AppContextUserType:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    return AppContextUserType(app_ctx[_user_type_key])


def get_breadcrumb() -> str | None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    breadcrumb = app_ctx[_breadcrumb_key]
    return str(breadcrumb) if breadcrumb is not None else None


def get_event_id() -> str:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    return str(app_ctx[_event_id_key])


def get_event_type() -> str:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    return str(app_ctx[_event_type_key])


def get_event_context() -> Dict[str, Any] | None:
    global _app_context
    app_ctx = _app_context.get()
    if app_ctx is None:
        raise RuntimeError('Application context not initialized')
    event_context = app_ctx[_event_context_key]
    return dict(event_context) if event_context is not None else None
