import json
import sys
import time
from collections import UserDict
from typing import Any, Callable, Dict, Type

import ddtrace
import sentry_sdk
from dramatiq.errors import Retry
from dramatiq.message import Message
from dramatiq.middleware import Middleware
from loguru import logger
from sentry_sdk import Hub
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.utils import (
    AnnotatedValue,
    capture_internal_exceptions,
    event_from_exception,
)

from src import settings
from src.network.database.session import IsolatedSession
from src.network.queue.domains import JobStatusDomain, JobStatusEnum
from src.network.queue.models import JobStatus


class DramatiqTelemetryMiddleware(Middleware):
    def before_process_message(self, broker, message):
        logger.info(f'processing task_id: {message.message_id}, name: {message.actor_name}')
        message.options['telemetry_start_time'] = time.time()

    def after_process_message(self, broker, message, *, result=None, exception=None):
        start_time = message.options.get('telemetry_start_time', time.time())
        duration = time.time() - start_time

        logger.info(f'completed task_id: {message.message_id}, name: {message.actor_name}, in: {duration:.2f} seconds')


class Spans(UserDict):  # pragma: no cover
    """
    Custom dictionary that allows us to easily lookup and set message instances as
    keys, but actually the message_id's are used instead.
    """

    def __getitem__(self, message):
        return super().__getitem__(message.message_id)

    def __setitem__(self, message, span):
        return super().__setitem__(message.message_id, span)

    def __delitem__(self, message):
        return super().__delitem__(message.message_id)

    def __contains__(self, message):
        return super().__contains__(message.message_id)


class DatadogTracingMiddleware(Middleware):
    def __init__(self):
        self._logger = logger
        self.spans = Spans()

    def before_worker_boot(self, broker, worker):
        """
        Called before the worker process starts up.
        """
        self._logger.debug('before_worker_boot start')

        # Attach a pin to the broker
        pin = ddtrace.Pin(service='app-worker')
        pin.onto(broker)

    def before_enqueue(self, broker, message, delay):
        """Called before a message is enqueued.

        This hook can be called by either the app (producer) or the worker. If this is
        part of a worker span, we don't want to do anything because we expect more
        hooks to be called after. If this is not part of a worker span however, it is
        the first hook to be called for the app (producer) and a span should be created
        and attached.

        An example of this from the worker is::

            consume -> process -> retry -> enqueue -> post processing
        """
        self._logger.debug('before_enqueue start')

        span = self.spans.get(message)
        if span is not None:
            # If a span exists, this hook was called likely from another
            # middleware hook operating from within the worker. (ie: Retries)
            self._logger.debug('another span found')
            return

        # Retrieve the pin
        pin = ddtrace.Pin.get_from(broker)
        if pin is None:
            self._logger.warning('no pin found')
            return

        # Setup the span
        span = pin.tracer.trace(
            'dramatiq.send',
            service='app-worker',
            span_type='consumer',
            resource=message.actor_name,
        )
        self.spans[message] = span

    def after_enqueue(self, broker, message, delay):
        """Called after a message has been enqueued.

        This hook can be called by either the app (producer) or the worker. If this is
        part of a producer span, we want to finish the span here as we do not expect
        any processing hooks to be called.
        """
        self._logger.debug('after_enqueue start')

        span = self.spans.get(message)
        if span is None:
            self._logger.warning('no span found')
            return

        if span.span_type == 'worker':
            # If this is part of a worker span, we expect more hooks to be called.  Do
            # not finish the span here
            return

        span.finish()
        del self.spans[message]

    def before_process_message(self, broker, message):
        """Called before a message is processed.

        This is the first hook to run for the worker when processing a message. This
        hook should create and attach a worker span for subsequent hooks called after
        processing.
        """
        self._logger.debug('before_process_message start')

        # Retrieve the pin
        pin = ddtrace.Pin.get_from(broker)
        if pin is None:
            self._logger.warning('no pin found')
            return

        # Attach a worker span
        span = pin.tracer.trace(
            'dramatiq.run',
            service='app-worker',
            span_type='worker',
            resource=message.actor_name,
        )
        ddtrace.tracer.current_root_span().set_tags({'task_id': message.message_id})
        self.spans[message] = span

    def after_process_message(self, broker, message, *, result=None, exception=None):
        """Called after a message has been processed.

        This is the the last hook to be called within the try/catch block of processing.
        We want to set the exc_info for the trace here if it exists.

        Note::

            This is not the last hook to be called for a message. After processing is
            post-processing which will either `ack` or `nack` the message.
        """
        self._logger.debug('after_process_message start')

        span = self.spans.get(message)
        if span is None:
            self._logger.warning('no span found')
            return

        if exception is not None:
            span.set_exc_info(*sys.exc_info())

        ddtrace.tracer.current_root_span().set_tags({'task_id': message.message_id})
        # finish the span
        span.finish()
        del self.spans[message]


class SentryMiddleware(Middleware):
    """
    Dramatiq middleware that captures and sends worker
    exceptions to Sentry.
    """

    def __init__(self):
        if not settings.USE_MOCK_SENTRY_CLIENT:
            # Ignore dramatiq logging since these are handled in middleware
            ignore_logger('dramatiq.worker.WorkerThread')
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                ignore_errors=[],
                environment=settings.ENVIRONMENT,
                integrations=[],
            )

    @property
    def actor_options(self):
        return {'sentry_ignore_exceptions'}

    def before_process_message(self, broker, message):
        hub = Hub.current
        client = hub.client
        if client is None:
            return

        message._scope_manager = hub.push_scope()
        # This will manually be closed in after_process_message
        message._scope_manager.__enter__()

        with hub.configure_scope() as scope:
            scope.transaction = message.actor_name
            scope.set_tag('worker_message_id', message.message_id)
            scope.add_event_processor(_make_message_event_processor(message))

    def after_process_message(self, broker, message, *, result=None, exception=None):
        hub = Hub.current
        # If sentry is None just ignore
        client = hub.client
        if client is None:
            return

        actor = broker.get_actor(message.actor_name)
        # Known exception throws defined in dramatiq to ignore
        throws = message.options.get('throws') or actor.options.get('throws')
        ignore_exceptions: tuple[Type[Exception]] = actor.options.get('sentry_ignore_exceptions')
        try:
            if exception is not None:
                is_expected_exception = throws and isinstance(exception, throws)
                is_retry_exception = isinstance(exception, Retry)
                is_retryable_exception = getattr(exception, 'is_retryable', False)

                if ignore_exceptions and isinstance(exception, ignore_exceptions):
                    logger.info(f'not sending exception {exception} to sentry')
                elif is_retryable_exception:
                    logger.info(f'not sending retryable exception {exception} to sentry')
                elif not is_expected_exception and not is_retry_exception:
                    event, hint = event_from_exception(
                        exception,
                        # client_options=hub.client.options,
                        mechanism={'type': 'worker', 'handled': False},
                    )
                    logger.error(f'exception thrown processing {message.message_id}')
                    hub.capture_event(event, hint=hint)
        finally:
            message._scope_manager.__exit__(None, None, None)


def _make_message_event_processor(message: Message) -> Callable:
    def inner(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any]:
        with capture_internal_exceptions():
            DramatiqMessageExtractor(message).extract_into_event(event)

        return event

    return inner


class DramatiqMessageExtractor:
    def __init__(self, message: Message):
        self.message_data = dict(message.asdict())

    def content_length(self) -> int:
        return len(json.dumps(self.message_data))

    def extract_into_event(self, event: Dict[str, Any]):
        client = Hub.current.client
        if client is None:
            return

        content_length = self.content_length()
        contexts = event.setdefault('contexts', {})
        request_info = contexts.setdefault('worker', {})
        request_info['type'] = 'worker'
        bodies = client.options['request_bodies']
        if (
            bodies == 'never'
            or (bodies == 'small' and content_length > 10**3)
            or (bodies == 'medium' and content_length > 10**4)
        ):
            data = AnnotatedValue(
                '',
                {'rem': [['!config', 'x', 0, content_length]], 'len': content_length},
            )
        else:
            data = self.message_data

        request_info['data'] = data


class DramatiqJobStatusMiddleware(Middleware):
    """Middleware for tracking the status of tasks."""

    def __init__(self):
        pass

    def before_process_message(self, broker, message):
        self._update_status(message.message_id, JobStatusEnum.IN_PROGRESS)

    def after_process_message(self, broker, message, *, result=None, exception=None):
        if exception is None:
            self._update_status(job_id=message.message_id, status=JobStatusEnum.COMPLETED)
        else:
            self._update_status(job_id=message.message_id, status=JobStatusEnum.FAILED, message=str(exception))

    def after_skip_message(self, broker, message):
        self._update_status(job_id=message.message_id, status=JobStatusEnum.SKIPPED)

    def _update_status(self, job_id, status: JobStatusEnum, message: str = None):
        with IsolatedSession(commit_on_success=True):
            job_status = JobStatus.get_or_none(job_id=job_id)
            if job_status:
                JobStatus.update(id=job_status.id, status=status, message=message)
            else:
                job_status_domain = JobStatusDomain(job_id=job_id, status=status, message=message)
                JobStatus.create(job_status_domain)
