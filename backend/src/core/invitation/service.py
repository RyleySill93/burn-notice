import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from loguru import logger

from src import settings
from src.common.nanoid import NanoIdType
from src.core.customer import CustomerService
from src.core.invitation.constants import InvitationStatusEnum
from src.core.invitation.domains import (
    AcceptInvitationPayload,
    AcceptInvitationResponse,
    InvitationCreate,
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
from src.core.invitation.models import Invitation
from src.core.membership import MembershipService
from src.core.user import UserCreate, UserService
from src.platform.email.service import EmailService


class InvitationService:
    INVITATION_TOKEN_LENGTH = 64
    INVITATION_EXPIRY_DAYS = 7

    def __init__(
        self,
        email_service: EmailService,
        user_service: UserService,
        membership_service: MembershipService,
        customer_service: CustomerService,
    ):
        self.email_service = email_service
        self.user_service = user_service
        self.membership_service = membership_service
        self.customer_service = customer_service

    @classmethod
    def factory(cls) -> 'InvitationService':
        return cls(
            email_service=EmailService.factory(),
            user_service=UserService.factory(),
            membership_service=MembershipService.factory(),
            customer_service=CustomerService.factory(),
        )

    def _generate_token(self) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(self.INVITATION_TOKEN_LENGTH)

    def _build_invitation_url(self, token: str) -> str:
        """Build the invitation acceptance URL"""
        return f'{settings.FRONTEND_ORIGIN}/accept-invitation?token={token}'

    def send_invitation(
        self,
        payload: SendInvitationPayload,
        invited_by_user_id: NanoIdType,
    ) -> InvitationRead:
        """Send an invitation to join a team"""
        # Check if user is already a member
        existing_customer_ids = self.membership_service.list_membership_customers_for_user_by_email(payload.email)
        if payload.customer_id in existing_customer_ids:
            raise UserAlreadyMember(f'User {payload.email} is already a member of this team')

        # Check for existing pending invitation
        existing_invitation = Invitation.get_or_none(
            Invitation.email == payload.email,
            Invitation.customer_id == payload.customer_id,
            Invitation.status == InvitationStatusEnum.PENDING.value,
        )
        if existing_invitation:
            # Revoke old invitation and create new one
            Invitation.update(existing_invitation.id, status=InvitationStatusEnum.REVOKED.value)

        # Create new invitation
        token = self._generate_token()
        expires_at = datetime.utcnow() + timedelta(days=self.INVITATION_EXPIRY_DAYS)

        invitation_create = InvitationCreate(
            email=payload.email,
            customer_id=payload.customer_id,
            invited_by_user_id=invited_by_user_id,
            token=token,
            expires_at=expires_at,
            message=payload.message,
        )

        invitation = Invitation.create(invitation_create)
        logger.info(
            'Invitation created',
            invitation_id=invitation.id,
            email=payload.email,
            customer_id=payload.customer_id,
        )

        # Send invitation email
        self._send_invitation_email(invitation, invited_by_user_id)

        return invitation

    def _send_invitation_email(self, invitation: InvitationRead, invited_by_user_id: NanoIdType) -> None:
        """Send the invitation email"""
        inviter = self.user_service.get_user_for_id(invited_by_user_id)
        customer = self.customer_service.get_for_id(invitation.customer_id)
        invitation_url = self._build_invitation_url(invitation.token)

        inviter_name = inviter.full_name or inviter.email
        subject = f"You've been invited to join {customer.name}"

        message_section = ''
        if invitation.message:
            message_section = f'<p><strong>Message:</strong> {invitation.message}</p>'

        html_message = f"""
        <h2>You've been invited to join {customer.name}</h2>
        <p>{inviter_name} has invited you to join their team on {settings.COMPANY_NAME}.</p>
        {message_section}
        <p><a href="{invitation_url}">Click here to accept the invitation</a></p>
        <p>This invitation expires in {self.INVITATION_EXPIRY_DAYS} days.</p>
        """

        plain_message_parts = [
            f"You've been invited to join {customer.name}",
            '',
            f'{inviter_name} has invited you to join their team on {settings.COMPANY_NAME}.',
        ]
        if invitation.message:
            plain_message_parts.append(f'Message: {invitation.message}')
        plain_message_parts.extend(
            [
                '',
                f'Accept the invitation: {invitation_url}',
                '',
                f'This invitation expires in {self.INVITATION_EXPIRY_DAYS} days.',
            ]
        )
        plain_message = '\n'.join(plain_message_parts)

        self.email_service.send(
            subject=subject,
            recipients=[invitation.email],
            html_message=html_message,
            plain_message=plain_message,
        )
        logger.info('Invitation email sent', email=invitation.email)

    def accept_invitation(
        self,
        payload: AcceptInvitationPayload,
        ip_address: str = '',
    ) -> AcceptInvitationResponse:
        """Accept an invitation and join the team"""
        invitation = Invitation.get_or_none(Invitation.token == payload.token)
        if not invitation:
            raise InvitationNotFound('Invitation not found')

        if invitation.status == InvitationStatusEnum.ACCEPTED.value:
            raise InvitationAlreadyAccepted('This invitation has already been accepted')

        if invitation.status == InvitationStatusEnum.REVOKED.value:
            raise InvitationRevoked('This invitation has been revoked')

        if invitation.expires_at < datetime.utcnow():
            Invitation.update(invitation.id, status=InvitationStatusEnum.EXPIRED.value)
            raise InvitationExpired('This invitation has expired')

        # Get or create user
        user_create = UserCreate(
            email=invitation.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        user, is_new = self.user_service.get_or_create_user(user_create)

        # Set password if provided and user is new
        if is_new and payload.password:
            from src.core.authentication import AuthenticationService
            from src.core.user import UserUpdate

            hashed_password = AuthenticationService.hash_password(payload.password)
            self.user_service.update_user(user.id, UserUpdate(hashed_password=hashed_password))

        # Create membership (with auto-generated API key)
        membership = self.membership_service.create_customer_membership(
            user_id=user.id,
            customer_id=invitation.customer_id,
        )
        api_key = membership.api_key

        # Grant member access (READ permission on customer)
        from src.core.authorization.services.access_control_service import AccessControlService

        customer = self.customer_service.get_for_id(invitation.customer_id)
        access_control_service = AccessControlService.factory()
        access_control_service.grant_customer_member_access(
            membership_id=membership.id,
            customer_id=invitation.customer_id,
            customer_name=customer.name,
        )

        # TODO: Implement specific project permission granting using PermissionService/AccessPolicies
        # The project_permissions data is stored in the invitation but not yet processed

        # Update invitation status
        Invitation.update(
            invitation.id,
            status=InvitationStatusEnum.ACCEPTED.value,
            accepted_at=datetime.utcnow(),
        )

        logger.info(
            'Invitation accepted',
            invitation_id=invitation.id,
            user_id=user.id,
            customer_id=invitation.customer_id,
        )

        # Generate auth tokens for the user
        from src.core.authentication import AuthenticationService

        token = AuthenticationService.create_auth_token(user.id, ip_address)

        return AcceptInvitationResponse(
            customer_id=invitation.customer_id,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            api_key=api_key,
        )

    def list_invitations_for_customer(
        self,
        customer_id: NanoIdType,
        status: Optional[InvitationStatusEnum] = None,
    ) -> List[InvitationRead]:
        """List invitations for a customer"""
        if status:
            return Invitation.list(
                Invitation.customer_id == customer_id,
                Invitation.status == status.value,
            )
        return Invitation.list(Invitation.customer_id == customer_id)

    def revoke_invitation(self, invitation_id: NanoIdType) -> InvitationRead:
        """Revoke a pending invitation"""
        invitation = Invitation.get(id=invitation_id)
        if invitation.status != InvitationStatusEnum.PENDING.value:
            raise InvitationException(f'Cannot revoke invitation with status {invitation.status}')

        updated = Invitation.update(invitation_id, status=InvitationStatusEnum.REVOKED.value)
        logger.info('Invitation revoked', invitation_id=invitation_id)
        return updated

    def get_invitation_by_token(self, token: str) -> InvitationRead:
        """Get invitation details by token (for preview before accepting)"""
        invitation = Invitation.get_or_none(Invitation.token == token)
        if not invitation:
            raise InvitationNotFound('Invitation not found')
        return invitation

    def resend_invitation(self, invitation_id: NanoIdType) -> InvitationRead:
        """Resend an invitation email"""
        invitation = Invitation.get(id=invitation_id)
        if invitation.status != InvitationStatusEnum.PENDING.value:
            raise InvitationException(f'Cannot resend invitation with status {invitation.status}')

        # Extend expiry
        new_expires_at = datetime.utcnow() + timedelta(days=self.INVITATION_EXPIRY_DAYS)
        updated = Invitation.update(invitation_id, expires_at=new_expires_at)

        # Resend email
        self._send_invitation_email(updated, updated.invited_by_user_id)
        logger.info('Invitation resent', invitation_id=invitation_id)
        return updated
