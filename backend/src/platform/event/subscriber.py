import abc
from typing import List

from .event import BaseEvent


class BaseSubscriber(abc.ABC):
    """
    Meant to take actions when events happen.
    """

    FOR_EVENTS: List[BaseEvent] = NotImplemented

    def __str__(self):
        return self.__class__.__name__

    @abc.abstractmethod
    def run(self, event: BaseEvent): ...

    @classmethod
    def build(cls, *args, **kwargs):
        return cls()
