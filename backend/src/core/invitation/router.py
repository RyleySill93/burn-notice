from typing import List, Optional

from fastapi import APIRouter, Depends, Request, status

from src.common.exceptions import APIException
from src.common.nanoid import NanoIdType
from src.common.request import get_user_ip_address_from_request
from src.core.authentication.domains import AuthenticatedUser
from src.core.authentication.guards import AuthenticatedUserGuard
from src.core.invitation.constants import InvitationStatusEnum
from src.core.invitation.domains import (
    AcceptInvitationPayload,
    AcceptInvitationResponse,
    InvitationRead,
    SendInvitationPayload,
)
from src.core.invitation.exceptions import (
    InvitationAlreadyAccepted,
    InvitationException,
    InvitationExpired,
    InvitationNotFound,
    InvitationRevoked,
    UserAlreadyMember,
)
from src.core.invitation.service import InvitationService
from src.core.membership import MembershipService, MembershipWithUser

router = APIRouter()


@router.post('/send-invitation')
def send_invitation(
    payload: SendInvitationPayload,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    invitation_service: InvitationService = Depends(InvitationService.factory),
) -> InvitationRead:
    """Send an invitation to join a team"""
    # TODO: Add permission check - user must have admin access on the customer
    try:
        return invitation_service.send_invitation(
            payload=payload,
            invited_by_user_id=user.id,
        )
    except UserAlreadyMember as e:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e.message))


@router.post('/accept-invitation')
def accept_invitation(
    request: Request,
    payload: AcceptInvitationPayload,
    invitation_service: InvitationService = Depends(InvitationService.factory),
) -> AcceptInvitationResponse:
    """Accept an invitation (no auth required - uses token)"""
    ip_address = get_user_ip_address_from_request(request)
    try:
        return invitation_service.accept_invitation(payload=payload, ip_address=ip_address)
    except InvitationNotFound as e:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message=str(e.message))
    except InvitationExpired as e:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e.message))
    except InvitationAlreadyAccepted as e:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e.message))
    except InvitationRevoked as e:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e.message))


@router.get('/get-invitation-by-token')
def get_invitation_by_token(
    token: str,
    invitation_service: InvitationService = Depends(InvitationService.factory),
) -> InvitationRead:
    """Get invitation details by token (for preview before accepting)"""
    try:
        return invitation_service.get_invitation_by_token(token=token)
    except InvitationNotFound as e:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message=str(e.message))


@router.get('/list-invitations')
def list_invitations(
    customer_id: NanoIdType,
    status_filter: Optional[InvitationStatusEnum] = None,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    invitation_service: InvitationService = Depends(InvitationService.factory),
) -> List[InvitationRead]:
    """List invitations for a customer"""
    # TODO: Add permission check - user must have admin access on the customer
    return invitation_service.list_invitations_for_customer(
        customer_id=customer_id,
        status=status_filter,
    )


@router.post('/revoke-invitation/{invitation_id}')
def revoke_invitation(
    invitation_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    invitation_service: InvitationService = Depends(InvitationService.factory),
) -> InvitationRead:
    """Revoke a pending invitation"""
    # TODO: Add permission check - user must have admin access on the customer
    try:
        return invitation_service.revoke_invitation(invitation_id=invitation_id)
    except InvitationException as e:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e.message))


@router.post('/resend-invitation/{invitation_id}')
def resend_invitation(
    invitation_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    invitation_service: InvitationService = Depends(InvitationService.factory),
) -> InvitationRead:
    """Resend an invitation email"""
    # TODO: Add permission check - user must have admin access on the customer
    try:
        return invitation_service.resend_invitation(invitation_id=invitation_id)
    except InvitationException as e:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=str(e.message))


@router.get('/list-team-members')
def list_team_members(
    customer_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    membership_service: MembershipService = Depends(MembershipService.factory),
) -> List[MembershipWithUser]:
    """List all team members for a customer"""
    # TODO: Add permission check - user must have access to the customer
    return membership_service.list_memberships_with_users_for_customer(customer_id=customer_id)


@router.delete('/remove-team-member/{membership_id}')
def remove_team_member(
    membership_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    membership_service: MembershipService = Depends(MembershipService.factory),
) -> None:
    """Remove a team member from a customer"""
    # TODO: Add permission check - user must have admin access on the customer
    membership = membership_service.get_membership_for_id_or_none(membership_id)
    if not membership:
        raise APIException(code=status.HTTP_404_NOT_FOUND, message='Membership not found')

    # Prevent users from removing themselves
    if membership.user_id == user.id:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message='You cannot remove yourself from the team')

    membership_service.delete_membership(membership_id=membership_id)
