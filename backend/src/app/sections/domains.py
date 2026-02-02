from datetime import datetime
from typing import Optional

from pydantic import Field

from src.app.sections.constants import SECTION_PK_ABBREV
from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


class SectionCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=SECTION_PK_ABBREV))
    name: str
    project_id: str
    display_order: int = 0


class SectionRead(BaseDomain):
    id: str
    name: str
    project_id: str
    display_order: int
    created_at: datetime
    modified_at: Optional[datetime]


class SectionUpdate(BaseDomain):
    name: Optional[str] = None
    display_order: Optional[int] = None
