from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.model import BaseModel
from src.core.invitation.constants import INVITATION_PK_ABBREV, InvitationStatusEnum
from src.core.invitation.domains import InvitationCreate, InvitationRead

if TYPE_CHECKING:
    from src.core.customer import Customer
    from src.core.user import User


class Invitation(BaseModel[InvitationRead, InvitationCreate]):
    __pk_abbrev__ = INVITATION_PK_ABBREV
    __create_domain__ = InvitationCreate
    __read_domain__ = InvitationRead

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    invited_by_user_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=InvitationStatusEnum.PENDING.value)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    project_permissions: Mapped[List[dict]] = mapped_column(JSONB, default=list)
    message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    customer: Mapped['Customer'] = relationship('Customer')
    invited_by: Mapped['User'] = relationship('User')

    __table_args__ = (Index('ix_invitation_email_customer_status', 'email', 'customer_id', 'status'),)
