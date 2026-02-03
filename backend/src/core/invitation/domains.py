from datetime import datetime
from typing import List, Optional

from pydantic import Field

from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType
from src.core.invitation.constants import INVITATION_PK_ABBREV, InvitationStatusEnum


class InvitationCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=INVITATION_PK_ABBREV))
    email: str
    customer_id: str
    invited_by_user_id: str
    token: str
    status: InvitationStatusEnum = InvitationStatusEnum.PENDING
    expires_at: datetime
    project_permissions: List[dict] = Field(default_factory=list)
    message: Optional[str] = None


class InvitationRead(BaseDomain):
    id: str
    email: str
    customer_id: str
    invited_by_user_id: str
    token: str
    status: InvitationStatusEnum
    expires_at: datetime
    project_permissions: List[dict]
    message: Optional[str]
    created_at: datetime
    modified_at: Optional[datetime]
    accepted_at: Optional[datetime]


class InvitationUpdate(BaseDomain):
    status: Optional[InvitationStatusEnum] = None
    accepted_at: Optional[datetime] = None


# API Request/Response Domains
class SendInvitationPayload(BaseDomain):
    email: str
    customer_id: str
    message: Optional[str] = None


class AcceptInvitationPayload(BaseDomain):
    token: str
    # Optional signup fields for new users
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None


class AcceptInvitationResponse(BaseDomain):
    """Response after accepting an invitation, includes auth tokens and API key"""

    customer_id: str
    access_token: str
    refresh_token: str
    api_key: str
