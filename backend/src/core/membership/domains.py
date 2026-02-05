from datetime import datetime
from typing import Optional

from pydantic import Field

from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType
from src.core.customer import CustomerRead
from src.core.membership.constants import MEMBERSHIP_PK_ABBREV
from src.core.user import UserRead


class MembershipCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=MEMBERSHIP_PK_ABBREV))
    customer_id: str
    user_id: str
    is_active: bool = False
    api_key: Optional[str] = None


class MembershipRead(MembershipCreate):
    id: NanoIdType
    created_at: datetime
    modified_at: Optional[datetime] = None


class MembershipUpdate(BaseDomain):
    is_active: Optional[bool] = None
    api_key: Optional[str] = None


class MembershipWithCustomer(MembershipRead):
    """Membership with associated customer information"""

    customer: CustomerRead | None = None


class MembershipWithUser(MembershipRead):
    """Membership with associated user information"""

    user: UserRead | None = None
    engineer_id: str | None = None
