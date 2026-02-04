from fastapi import APIRouter, Depends

from src.app.engineers.domains import EngineerCreateRequest, EngineerRead
from src.app.engineers.service import EngineerService
from src.core.authentication.dependencies import get_current_membership
from src.core.authentication.domains import AuthenticatedUser
from src.core.authentication.guards import authenticate_user
from src.core.membership.domains import MembershipRead
from src.core.user import UserService

router = APIRouter()


@router.post('', response_model=EngineerRead)
def create_or_update_engineer(
    request: EngineerCreateRequest,
    membership: MembershipRead = Depends(get_current_membership),
) -> EngineerRead:
    """Register or update an engineer for the current team."""
    return EngineerService.get_or_create(
        customer_id=membership.customer_id,
        external_id=request.external_id,
        display_name=request.display_name,
    )


@router.get('', response_model=list[EngineerRead])
def list_engineers(
    membership: MembershipRead = Depends(get_current_membership),
) -> list[EngineerRead]:
    """List all engineers for the current team."""
    return EngineerService.list_by_customer(membership.customer_id)


@router.get('/me', response_model=EngineerRead | None)
def get_my_engineer(
    user: AuthenticatedUser = Depends(authenticate_user),
    membership: MembershipRead = Depends(get_current_membership),
    user_service: UserService = Depends(UserService.factory),
) -> EngineerRead | None:
    """Get the engineer record for the current user (by email)."""
    user_record = user_service.get_user_for_id(user.id)
    if not user_record.email:
        return None
    return EngineerService.get_by_external_id(membership.customer_id, user_record.email)


@router.get('/{external_id}', response_model=EngineerRead | None)
def get_engineer(
    external_id: str,
    membership: MembershipRead = Depends(get_current_membership),
) -> EngineerRead | None:
    """Get an engineer by external ID."""
    return EngineerService.get_by_external_id(membership.customer_id, external_id)
