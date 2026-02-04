from datetime import datetime
from typing import Optional

from pydantic import Field

from src.app.engineers.constants import ENGINEER_PK_ABBREV
from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


class EngineerCreateRequest(BaseDomain):
    """Request payload for creating an engineer."""

    external_id: str
    display_name: str


class EngineerCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=ENGINEER_PK_ABBREV))
    customer_id: str  # Team/customer ID
    external_id: str  # e.g., "alice@company.com" or "alice-macbook"
    display_name: str


class EngineerRead(BaseDomain):
    id: str
    customer_id: str
    external_id: str
    display_name: str
    created_at: datetime
    modified_at: datetime | None = None
