from datetime import date, datetime
from typing import Optional

from pydantic import Field

from src.app.records.constants import RECORD_PK_ABBREV
from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


class RecordCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=RECORD_PK_ABBREV))
    engineer_id: str
    customer_id: str
    record_type: str  # tokens, time
    record_period: str  # daily, weekly, monthly
    record_scope: str  # personal, company
    value: float
    previous_value: float | None = None
    record_date: date


class RecordRead(BaseDomain):
    id: str
    engineer_id: str
    customer_id: str
    record_type: str
    record_period: str
    record_scope: str
    value: float
    previous_value: float | None
    record_date: date
    created_at: datetime
