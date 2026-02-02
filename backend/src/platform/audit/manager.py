import json
import uuid

from sqlalchemy import text

from src.common import context as _context
from src.network.database.session import db
from src.platform.event.constants import EventTypeEnum


class AppAuditEvent:
    """
    Use to create a nested audit event
    Example:
    with AppAuditEvent(
        event_type=EventTypeEnum.TASK_PACKAGE_COMPLETED,
    ):
        ...

    """

    def __init__(
        self,
        event_type: EventTypeEnum | None = None,
        event_id: uuid.UUID | None = None,
        breadcrumb: str | None = None,
        event_context: dict | None = None,
    ):
        # Previous context values
        self._previous_breadcrumb = _context.get_breadcrumb()
        self._previous_event_id = _context.get_event_id()
        self._previous_event_type = _context.get_event_type()
        self._previous_event_context = _context.get_event_context()

        # Ensure event_type is a valid member of EventTypeEnum or default to .UNKNOWN
        if event_type and event_type not in EventTypeEnum.__members__.values():
            raise ValueError(f'Unrecognized event type: {event_type}')
        elif event_type is not None:
            event_type = str(event_type)

        # Current context values
        # Always set a new event id if one wasn't provided
        self.event_id = event_id or str(uuid.uuid4())
        # Propagate current if unavailable
        self.event_type = event_type or self._previous_event_type
        self.breadcrumb = breadcrumb or self._previous_breadcrumb
        self.event_context = json.dumps(event_context) if event_context is not None else self._previous_event_context

    def __enter__(self) -> 'AppAuditEvent':
        # Set current context values
        _context.set_event_type(self.event_type)
        _context.set_event_id(self.event_id)
        _context.set_breadcrumb(self.breadcrumb)
        _context.set_event_context(self.event_context)

        if self.event_id:
            query = text('SET LOCAL auditcontext.event_id = :event_id')
            db.session.execute(query, {'event_id': self.event_id})
        if self.event_type:
            query = text('SET LOCAL auditcontext.event_type = :event_type')
            db.session.execute(query, {'event_type': self.event_type})
        if self.breadcrumb:
            query = text('SET LOCAL auditcontext.breadcrumb = :breadcrumb')
            db.session.execute(query, {'breadcrumb': self.breadcrumb})
        if self.event_context:
            query = text('SET LOCAL auditcontext.event_context = :event_context')
            db.session.execute(query, {'event_context': self.event_context})

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reset context to previous values
        _context.set_event_type(self._previous_event_type)
        _context.set_event_id(self._previous_event_id)
        _context.set_breadcrumb(self._previous_breadcrumb)
        _context.set_event_context(self._previous_event_context)

        if self._previous_event_id:
            query = text('SET LOCAL auditcontext.event_id = :event_id')
            db.session.execute(query, {'event_id': self._previous_event_id})
        if self._previous_event_type:
            query = text('SET LOCAL auditcontext.event_type = :event_type')
            db.session.execute(query, {'event_type': self._previous_event_type})
        if self._previous_breadcrumb:
            query = text('SET LOCAL auditcontext.breadcrumb = :breadcrumb')
            db.session.execute(query, {'breadcrumb': self._previous_breadcrumb})
        if self._previous_event_context:
            query = text('SET LOCAL auditcontext.event_context = :event_context')
            db.session.execute(query, {'event_context': self._previous_event_context})

        return False
