from datetime import datetime
from typing import Optional

from pydantic import Field

from src.app.tasks.constants import TASK_PK_ABBREV
from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


class TaskCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=TASK_PK_ABBREV))
    title: str
    description: Optional[str] = None
    project_id: str
    section_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    display_order: int = 0


class TaskRead(BaseDomain):
    id: str
    title: str
    description: Optional[str]
    project_id: str
    section_id: Optional[str]
    parent_task_id: Optional[str]
    completed_at: Optional[datetime]
    display_order: int
    created_at: datetime
    modified_at: Optional[datetime]


class TaskUpdate(BaseDomain):
    title: Optional[str] = None
    description: Optional[str] = None
    section_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    display_order: Optional[int] = None
