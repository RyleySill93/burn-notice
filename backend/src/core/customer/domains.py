from datetime import datetime
from typing import Optional

from pydantic import Field

from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType
from src.core.customer.constants import CUSTOMER_PK_ABBREV


class CustomerCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=CUSTOMER_PK_ABBREV))
    name: str


class CustomerRead(CustomerCreate):
    id: NanoIdType
    created_at: datetime
    modified_at: Optional[datetime] = None


class CustomerUpdate(BaseDomain):
    name: Optional[str] = None
