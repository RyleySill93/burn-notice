from fastapi import Depends

from src.core.authentication.domains import AuthenticatedUser
from src.core.authentication.guards import authenticate_user
from src.core.membership.domains import MembershipRead
from src.core.membership.models import Membership


def get_current_membership(
    user: AuthenticatedUser = Depends(authenticate_user),
) -> MembershipRead:
    """Get the current user's active membership."""
    # Get the user's first active membership
    # In a multi-tenant app, you might get this from a header or session
    membership = Membership.get_or_none(user_id=user.id, is_active=True)
    if not membership:
        from src.common.exceptions import APIException
        from fastapi import status
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='No active membership found. Please join or create a team.',
        )
    return membership
