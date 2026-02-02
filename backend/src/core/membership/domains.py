from datetime import datetime
from typing import Optional

from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType
from src.core.customer import CustomerRead
from src.core.user import UserRead


class MembershipCreate(BaseDomain):
    customer_id: str
    user_id: str
    is_active: bool = False


class MembershipRead(MembershipCreate):
    id: NanoIdType
    created_at: datetime
    modified_at: Optional[datetime] = None


class MembershipUpdate(BaseDomain):
    is_active: Optional[bool] = None


class MembershipWithCustomer(MembershipRead):
    """Membership with associated customer information"""

    customer: CustomerRead | None = None


class MembershipWithUser(MembershipRead):
    """Membership with associated user information"""

    user: UserRead | None = None
