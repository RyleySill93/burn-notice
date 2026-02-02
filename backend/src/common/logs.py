import dataclasses
import json
import logging
import sys
from typing import Any

from loguru import logger

from src import settings
from src.common import context


def _format_traceback_as_dicts(
    exception: Any,
    locals_max_string: int = 80,
    max_frames: int = 2,
) -> list[dict[str, Any]]:
    """
    Return a list of exception stack dictionaries for *exception*.
    """
    if locals_max_string < 0:
        raise ValueError(f'"locals_max_string" must be >= 0: {locals_max_string}')

    if isinstance(exception, BaseException):
        exc_info = (type(exception), exception, exception.__traceback__)

    elif isinstance(exception, tuple):
        exc_info = exception  # type: ignore

    elif exception:
        exc_info = sys.exc_info()

    else:
        return []

    from rich.traceback import Traceback

    trace = Traceback.extract(*exc_info, show_locals=False, locals_max_string=locals_max_string)

    for stack in trace.stacks:
        if len(stack.frames) <= max_frames:
            continue  # No need to modify stacks with a number of frames within the limit

        # Modify the stack to include only the last max_frames frames
        stack.frames[:] = stack.frames[-max_frames:]

    stack_dicts = [dataclasses.asdict(stack) for stack in trace.stacks]
    return stack_dicts


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentation.
    This handler intercepts all log requests and
    passes them to loguru.
    For more info see:
    https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        """
        Propagates logs to loguru.
        """
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def deployed_log_formatter(record: dict[str, Any]) -> str:
    """
    Formats a machine readable log
    """
    if record['exception'] is not None:
        exc = record['exception']
        record['exception'] = None
        # Format with mini traceback
        # error_formatted = _format_traceback_as_dicts(exc)
        # Simple format
        error_formatted = {
            'exception_type': str(type(exc).__name__),
            'message': str(exc),
            'traceback': '',
        }
        record['extra']['error'] = error_formatted

    # Inject important information into extra to trim log size
    record['extra']['timestamp'] = record['time'].strftime('%Y-%m-%dT%H:%M:%S,%f')
    record['extra']['message'] = record['message']
    record['extra']['level'] = record['level'].name
    if settings.TELEMETRY_ENABLED:
        from ddtrace import config, tracer

        # get correlation ids from current tracer context
        span = tracer.current_span()
        trace_id, span_id = (str((1 << 64) - 1 & span.trace_id), span.span_id) if span else (None, None)

        # add ids to structlog event dictionary
        record['extra']['dd.trace_id'] = str(trace_id or 0)
        record['extra']['dd.span_id'] = str(span_id or 0)

        # add the env, service, and version configured for the tracer
        record['extra']['dd.env'] = config.env or ''
        record['extra']['dd.service'] = config.service or ''
        record['extra']['dd.version'] = config.version or 'test'

    # This is set in logging context, but some loggers are above it
    request_id = record['extra'].get('request_id', None)
    if not request_id:
        request_id = context.get_safe_request_id() or ''
    record['extra']['request_id'] = request_id
    record['extra']['user_id'] = context.get_safe_user_id() or ''
    record['extra']['impersonator_id'] = context.get_impersonator_id() or ''

    record['extra']['serialized'] = json.dumps(record['extra'])
    log_format = '{extra[serialized]}\n'
    return log_format


def local_log_formatter(record: dict[str, Any]) -> str:
    """
    Formats a log record for local development console
    """
    # This is set in logging context, but some loggers are above it
    duration = record['extra'].get('duration', None)
    if duration is None:
        level = record['level'].no
        if level == logging.DEBUG:
            icon = '🔬'
        elif level == logging.WARNING:
            icon = '⚠️'
        elif level == logging.ERROR:
            icon = '💣💥'
        elif level == logging.CRITICAL:
            icon = '🚨'
        else:
            icon = '✏️'

        log_format = (
            '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> '
            f'| {icon} '
            ' <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> '
            '- <level>{message}</level>\n'
        )
    else:
        level = record['level'].no
        if level == logging.WARNING:
            meta = '⚠️'
        elif level == logging.ERROR:
            meta = '💣💥'
        elif level == logging.CRITICAL:
            meta = '🚨🚨🚨'
        else:
            # Otherwise show duration of endpoint
            meta = f'⏱️ {duration}s'

        log_format = (
            '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> '
            f'| <magenta>{meta}</magenta> '
            '- <level>{message}</level>\n'
        )

    if record['exception'] is not None:
        if settings.DEBUG:
            from rich.console import Console
            from rich.traceback import Traceback

            console = Console()

            # The record['exception'] is already a tuple of (type, value, traceback)
            exc_info = record['exception']

            try:
                # Create a new Traceback with desired parameters
                rich_tb = Traceback.from_exception(
                    exc_type=exc_info[0],
                    exc_value=exc_info[1],
                    traceback=exc_info[2],
                    show_locals=True,
                    locals_max_length=5,  # Limit container size
                    locals_max_string=25,  # Limit string length
                    locals_hide_dunder=True,
                    locals_hide_sunder=False,
                    max_frames=10,
                )
                console.print(rich_tb)
            except Exception as e:
                # Fall back to standard formatting if Rich fails
                print(f'Error using Rich traceback: {e}')
                console.print_exception(max_frames=10, show_locals=False)
        else:
            logger.error(record['exception'])
    return log_format


def configure_logging():
    # Intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(settings.LOG_LEVEL)

    # Remove every other logger's handlers
    # and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    if settings.IS_DEPLOYED_ENV:
        log_formatter = deployed_log_formatter
    else:
        log_formatter = local_log_formatter

    serialize = False
    backtrace = False
    diagnose = False
    logger.remove()
    logger.add(
        sys.stdout,
        serialize=serialize,
        backtrace=backtrace,
        diagnose=diagnose,
        level=settings.LOG_LEVEL,
        format=log_formatter,
    )
    # This logger only duplicates since we have middleware we are appending context too
    logging.getLogger('uvicorn.access').propagate = False
    logger.info(f'logging level: {settings.LOG_LEVEL}')

    # Alternative that just targets uvicorn
    # loggers = (
    #     logging.getLogger(name)
    #     for name in logging.root.manager.loggerDict
    #     if name.startswith("uvicorn.")
    # )
    # for uvicorn_logger in loggers:
    #     uvicorn_logger.handlers = []
    #
    # # change handler for default uvicorn logger
    # intercept_handler = InterceptHandler()
    # logging.getLogger("uvicorn").handlers = [intercept_handler]
    # logging.getLogger("uvicorn.access").handlers = [intercept_handler]
