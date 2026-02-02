from sqlalchemy import Column, Index, String
from sqlalchemy.dialects.postgresql import JSON, UUID

from src.common.model import BaseModel
from src.platform.event.domains import EventCreate, EventRead


class Event(BaseModel[EventRead, EventCreate]):
    id = Column(UUID(as_uuid=True), primary_key=True)
    event_type = Column(String(length=100), index=True)
    payload = Column(JSON)
    payload_class = Column(String(length=100), nullable=True)
    txn_id = Column(UUID(as_uuid=True))

    # Adding the custom index name
    __table_args__ = (Index('idx_event_event_type', 'event_type'),)
