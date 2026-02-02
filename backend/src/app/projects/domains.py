from datetime import datetime
from typing import Optional

from pydantic import Field

from src.app.projects.constants import PROJECT_PK_ABBREV
from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


class ProjectCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=PROJECT_PK_ABBREV))
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    customer_id: str
    user_id: Optional[str] = None  # Creator reference


class ProjectRead(BaseDomain):
    id: str
    name: str
    description: Optional[str]
    color: Optional[str]
    customer_id: str
    user_id: Optional[str]
    created_at: datetime
    modified_at: Optional[datetime]


class ProjectUpdate(BaseDomain):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
