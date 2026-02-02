from typing import Optional, Set

from fastapi import Request

from src.common import context
from src.common.nanoid import NanoIdType
from src.core.authorization.constants import PermissionTypeEnum, ResourceTypeEnum
from src.core.authorization.services.permission_service import PermissionService


class PermissionContext:
    """
    A context object that provides access to permission information for the current user.

    This class delegates permission checks to the PermissionService, which handles
    caching at its level.
    """

    def __init__(self):
        """
        Initialize a new permission context.

        The user ID is retrieved from the global context when needed rather than stored.
        """
        self._service = PermissionService.factory()

    @property
    def user_id(self) -> Optional[NanoIdType]:
        """
        Get the current user ID from the global context.

        This ensures we're always using the most up-to-date user ID and
        not duplicating storage.

        Returns:
            The current user ID or None if not authenticated
        """
        return context.get_safe_user_id()

    def get_permitted_ids(
        self, resource_type: ResourceTypeEnum, permission_type: PermissionTypeEnum
    ) -> Set[NanoIdType]:
        """
        Get the set of resource IDs the user is permitted to access.

        Args:
            resource_type: The type of resource to check
            permission_type: The type of permission to check

        Returns:
            A set of resource IDs the user is permitted to access. If None is returned,
            means full acccess
        """
        # If no user_id (not authenticated), return empty set
        if self.user_id is None:
            return set()

        # Delegate to the authorization service which handles caching
        return self._service.list_permitted_ids(self.user_id, permission_type, resource_type)


async def get_permission_context(request: Request) -> PermissionContext:
    """
    FastAPI dependency that provides access to the permission context.

    This dependency creates a PermissionContext for the current user if one doesn't
    already exist on the request, and returns it. This allows efficient reuse of the
    context within a single request.

    Important: This dependency does NOT enforce authentication itself. It will work for
    both authenticated and unauthenticated requests. For unauthenticated requests,
    it will return a context with empty permissions.

    Args:
        request: The FastAPI request object

    Returns:
        A PermissionContext instance for the current user (or empty context if not authenticated)
    """
    if not hasattr(request.state, 'permission_context'):
        # Create a fresh permission context that will access the user ID from the global context
        ctx = PermissionContext()
        request.state.permission_context = ctx
    return request.state.permission_context
