from src.common.exceptions import InternalException


class SubscriberNotFound(InternalException): ...


class NoSubscribersRegistered(InternalException): ...


class EventBusNotInitialized(InternalException): ...
