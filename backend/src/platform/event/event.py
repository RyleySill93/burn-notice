import datetime
import uuid
from typing import Generic, Optional, TypeVar

from src.platform.event.exceptions import EventBusNotInitialized
from src.platform.event.payload import _PAYLOAD_TYPE_REGISTRY, BaseEventPayload

# Used to register subscribers to all events
ALL_EVENTS = '*'

_EVENT_TYPES_REGISTRY = {}


class BaseEventMeta(type):
    """
    Metaclass to register event classes and create version to schema map
    """

    def __new__(mcs, name, bases, attrs):
        klass = super().__new__(mcs, name, bases, attrs)

        if klass.EVENT_TYPE != NotImplemented:
            _EVENT_TYPES_REGISTRY[klass.EVENT_TYPE.value] = klass
            _PAYLOAD_TYPE_REGISTRY[klass.EVENT_TYPE.value] = klass.PAYLOAD_CLASS

        return klass


TPayload = TypeVar('TPayload', bound=BaseEventPayload)


class BaseEvent(Generic[TPayload], metaclass=BaseEventMeta):
    """
    id: unique event id
    event_type: name of the class containing event data
    payload: serialized event data, e.g. JSON
    created: timestamp at which the event happened
    _txn id: grouping of events happening in the same txn
    """

    PAYLOAD_CLASS = NotImplemented
    EVENT_TYPE = NotImplemented
    # If you dont want to store an event in the DB, set this to False
    STORE_EVENT: bool = False

    __slots__ = [
        'id',
        '_payload',
        '_txn_id',
        'created_at',
    ]

    def __str__(self):
        return f'<{self.event_type}> id: {self.id}'

    def __repr__(self):
        return str(self)

    def __init__(
        self,
        id: uuid.UUID,
        payload: TPayload,
        created_at: Optional[datetime.datetime] = None,
    ):
        self.id = id
        self._payload = payload

        # Event meta
        self.created_at = created_at or datetime.datetime.now()

        # Set later
        self._txn_id = None

    @property
    def payload(self) -> TPayload:
        return self._payload

    @property
    def event_type(self) -> TPayload:
        return self.EVENT_TYPE

    @classmethod
    def new(
        cls,
        payload: TPayload,
    ):
        return cls(
            id=uuid.uuid4(),
            payload=payload,
        )

    def publish(self):
        from src.platform.event.bus import EB

        if EB is None:
            raise EventBusNotInitialized('EventBus.initialize never called')

        EB.publish(self)
        # @TODO Process after transaction commits
        # transaction.on_commit(lambda: EP.process(self))

    @classmethod
    def get_concrete_event_from_model(cls, event) -> 'BaseEvent':
        """
        Returns the correct concrete event given model object
        """
        klass = _EVENT_TYPES_REGISTRY[event.event_type]
        payload_class = _PAYLOAD_TYPE_REGISTRY[event.event_type]
        payload = payload_class(**event.payload)

        return klass(
            id=event.id,
            payload=payload,
            created_at=event.created_at,
        )

    @classmethod
    def get_concrete_event_from_dict(cls, event) -> 'BaseEvent':
        """
        Returns the correct concrete event given raw event data as a dict
        """
        klass = _EVENT_TYPES_REGISTRY[event['event_type']]
        payload_class = _PAYLOAD_TYPE_REGISTRY[event['event_type']]
        payload = payload_class(**event['payload'])

        return klass(
            id=event['id'],
            payload=payload,
            created_at=event['created_at'],
        )

    def serialize(self) -> dict:
        return {
            'id': str(self.id),
            'event_type': self.event_type,
            'payload': self.payload.serialize(),
            'created_at': self.created_at.isoformat(),
        }
