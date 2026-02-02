from datetime import datetime
from typing import Optional

from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType


class CustomerCreate(BaseDomain):
    name: str


class CustomerRead(CustomerCreate):
    id: NanoIdType
    created_at: datetime
    modified_at: Optional[datetime] = None


class CustomerUpdate(BaseDomain):
    name: Optional[str] = None
