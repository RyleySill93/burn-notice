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
    medal_category: str  # ranking, milestone, action
    medal_type: str  # gold, silver, bronze, token_10m, purple_heart, etc.
    metric_type: str  # tokens, time
    period_type: str | None = None  # weekly, monthly (null for milestones/action)
    period_start: date | None = None  # null for milestones/action
    value: float
    citation: str | None = None  # text citation for action medals
    awarded_by_user_id: str | None = None  # user who awarded action medals


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
    citation: str | None
    awarded_by_user_id: str | None
    created_at: datetime
