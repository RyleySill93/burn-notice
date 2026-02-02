import uuid

from src.common.domain import BaseDomain
from src.platform.event.constants import EventTypeEnum


class EventCreate(BaseDomain):
    id: uuid.UUID
    event_type: EventTypeEnum
    payload: dict
    payload_class: str


class EventRead(EventCreate):
    id: uuid.UUID
