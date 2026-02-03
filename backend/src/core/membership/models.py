from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.common.model import BaseModel
from src.core.membership.constants import MEMBERSHIP_PK_ABBREV
from src.core.membership.domains import MembershipCreate, MembershipRead


class Membership(BaseModel[MembershipRead, MembershipCreate]):
    customer_id: Mapped[str] = mapped_column(ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)

    __pk_abbrev__ = MEMBERSHIP_PK_ABBREV
    __read_domain__ = MembershipRead
    __create_domain__ = MembershipCreate
    __system_audit__ = True

    __table_args__ = (
        # a user cannot be related to the same customer twice
        UniqueConstraint('customer_id', 'user_id'),
    )
