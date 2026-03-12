from datetime import date, datetime
from typing import Optional

from pydantic import Field

from src.app.medals.constants import MEDAL_PK_ABBREV
from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


class MedalCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=MEDAL_PK_ABBREV))
    engineer_id: str
    customer_id: str
    medal_category: str  # ranking, milestone
    medal_type: str  # gold, silver, bronze, token_10m, etc.
    metric_type: str  # tokens, time
    period_type: str | None = None  # weekly, monthly (null for milestones)
    period_start: date | None = None  # null for milestones
    value: float


class MedalRead(BaseDomain):
    id: str
    engineer_id: str
    customer_id: str
    medal_category: str
    medal_type: str
    metric_type: str
    period_type: str | None
    period_start: date | None
    value: float
    created_at: datetime
