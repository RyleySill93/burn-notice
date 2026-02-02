import abc
import uuid
from collections import defaultdict
from typing import DefaultDict, List

from loguru import logger

from src.common.utils import import_dotted_path_string
from src.platform.event.domains import EventCreate
from src.platform.event.event import ALL_EVENTS, BaseEvent
from src.platform.event.exceptions import (
    NoSubscribersRegistered,
    SubscriberNotFound,
)
from src.platform.event.subscriber import BaseSubscriber


class BaseEventDAO(abc.ABC):
    def get(self, event_id: str):
        raise NotImplementedError

    def append(self, event: BaseEvent):
        raise NotImplementedError

    def remove(self, event: BaseEvent):
        raise NotImplementedError


from .models import Event


class SQLAlchemyEventDao(BaseEventDAO):
    def get(self, id: uuid.UUID) -> BaseEvent:
        app_event = Event.get(id=id)
        return BaseEvent.get_concrete_event_from_model(app_event)

    def append(self, event: BaseEvent) -> BaseEvent:
        data = event.serialize()
        event_create = EventCreate(**data)
        app_event = Event.create(event_create)
        return BaseEvent.get_concrete_event_from_model(app_event)

    def remove(self, event: BaseEvent) -> None:
        Event.delete(Event.id == event.id)


class EventBus:
    """
    Handles all events.
        - Visits all subscriber with events
    """

    def __init__(self, subscriber_registry: List[str]):
        self.event_dao = SQLAlchemyEventDao()

        self._subscriber_registry: DefaultDict[str, List[BaseSubscriber]] = self._register_subscribers(
            subscriber_registry
        )

    @classmethod
    def initialize(cls, subscriber_registry: List[str]):
        global EB
        EB = cls(subscriber_registry)

    def _register_subscribers(self, subscriber_registry: List[str]) -> DefaultDict[str, List[BaseSubscriber]]:
        subscriber_registry_map = defaultdict(list)
        for subscriber_path in subscriber_registry:
            try:
                subscriber_class = import_dotted_path_string(subscriber_path)
            except ModuleNotFoundError:
                raise SubscriberNotFound(message=f'No subscriber at: {subscriber_path}')

            subscriber = subscriber_class.build()
            for event_class in subscriber.FOR_EVENTS:
                if event_class == ALL_EVENTS:
                    subscriber_registry_map[ALL_EVENTS].append(subscriber)
                else:
                    subscriber_registry_map[event_class.__name__].append(subscriber)

            logger.info(f'subscriber registered: {subscriber}')

        return subscriber_registry_map

    def publish(self, event: BaseEvent):
        if len(self._subscriber_registry) == 0:
            raise NoSubscribersRegistered(message='No subscribers registered to EventBus!')

        self._publish_event(event)

    def _publish_event(self, event: BaseEvent):
        logger.info(f'publishing event: {event}')
        if event.STORE_EVENT:
            self._store_event(event)

        self._run_subscriber(event)

    def _run_subscriber(self, event):
        run_subscribers = set()
        all_event_subscribers = self._subscriber_registry[ALL_EVENTS]
        subscribers = self._subscriber_registry[event.__class__.__name__]
        for subscriber in [*subscribers, *all_event_subscribers]:
            if subscriber.__class__.__name__ in run_subscribers:
                logger.info(f'subscriber: {subscriber.__class__.__name__} already ran')

            logger.info(f'running subscriber: {subscriber.__class__.__name__}')
            subscriber.run(event)
            run_subscribers.add(subscriber.__class__.__name__)

    def _store_event(self, event: BaseEvent):
        self.event_dao.append(event)

    def _remove_event(self, event: BaseEvent):
        self.event_dao.remove(event)


# This is set when initialized
EB = None
