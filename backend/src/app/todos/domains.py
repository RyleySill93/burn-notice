from datetime import datetime
from typing import Optional

from pydantic import Field

from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


class TodoCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev='todo'))
    title: str
    description: Optional[str] = None
    completed: bool = False


class TodoRead(BaseDomain):
    id: str
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime
    modified_at: Optional[datetime]


class TodoUpdate(BaseDomain):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
