from fastapi import params, status

from src.common.domain import BaseDomain
from src.common.exceptions import APIException
from src.common.nanoid import NanoIdType
from src.core.authentication.domains import AuthenticatedUser
from src.core.authentication.guards import AuthenticatedUserGuard
from src.core.authorization.constants import PermissionTypeEnum, ResourceTypeEnum
from src.core.authorization.domains import AuthorizedUser
from src.core.authorization.models import AccessPolicy, AccessRole
from src.core.authorization.services.permission_service import PermissionService


class _RouterGuard(params.Security):
    def __call__(self, *args, **kwargs):
        return self


def _authorize_staff_member(authn_user: AuthenticatedUser = AuthenticatedUserGuard()) -> AuthorizedUser:
    """
    Adds customer_id as a dependency requirement to be used downstream
    """
    authz_service = PermissionService.factory()
    auth_user = authz_service.get_authz_user_authn_user(authn_user=authn_user)
    is_staff = authz_service.is_staff_user_id(auth_user.id)
    if not is_staff:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Denied',
        )
    return auth_user


StaffUserGuard = _RouterGuard(dependency=_authorize_staff_member)


def _authorize_user(authn_user: AuthenticatedUser = AuthenticatedUserGuard()) -> AuthorizedUser:
    authz_service = PermissionService.factory()
    auth_user = authz_service.get_authz_user_authn_user(authn_user=authn_user)
    return auth_user


UserGuard = _RouterGuard(dependency=_authorize_user)


class UserCustomerGuardPayload(BaseDomain):
    customer_ids: list[NanoIdType]


# Entity access authorization is now replaced by customer access authorization
# Keeping this function for backward compatibility but it delegates to customer access
def _authorize_entity_access(
    customer_id: NanoIdType,
    authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_type: PermissionTypeEnum = PermissionTypeEnum.READ,
) -> AuthorizedUser:
    # Since entities are replaced with customers, this delegates to customer access
    return _authorize_customer_access(customer_id, authn_user, permission_type)


def _authorize_customer_access(
    customer_id: NanoIdType,
    authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_type: PermissionTypeEnum = PermissionTypeEnum.READ,
) -> AuthorizedUser:
    authz_service = PermissionService.factory()
    user = authz_service.get_authz_user_authn_user(authn_user=authn_user)

    has_permission = authz_service.check_permission(
        user_id=user.id,
        permission_type=permission_type,
        resource_type=ResourceTypeEnum.CUSTOMER,
        resource_id=customer_id,
    )

    if not has_permission:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Permission denied',
        )

    return user


# Create factory functions for entity and customer guards
def create_entity_authorization_guard(permission_type: PermissionTypeEnum):
    """Factory function that creates entity authorization guards for different permission types.
    Note: Entities are now replaced with customers, so this delegates to customer authorization."""

    def _authorize_entity(
        customer_id: NanoIdType,
        authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    ) -> AuthorizedUser:
        """Authorize access to an entity (now customer) using the RBAC permission system."""
        return _authorize_customer_access(customer_id, authn_user, permission_type)

    return _RouterGuard(dependency=_authorize_entity)


def create_customer_authorization_guard(permission_type: PermissionTypeEnum):
    """Factory function that creates customer authorization guards for different permission types."""

    def _authorize_customer(
        customer_id: NanoIdType,
        authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    ) -> AuthorizedUser:
        """Authorize access to a customer using the RBAC permission system."""
        return _authorize_customer_access(customer_id, authn_user, permission_type)

    return _RouterGuard(dependency=_authorize_customer)


# Create the actual guard objects
EntityReadGuard = create_entity_authorization_guard(PermissionTypeEnum.READ)
EntityEditGuard = create_entity_authorization_guard(PermissionTypeEnum.WRITE)
EntityAdminGuard = create_entity_authorization_guard(PermissionTypeEnum.ADMIN)
CustomerReadGuard = create_customer_authorization_guard(PermissionTypeEnum.READ)
CustomerEditGuard = create_customer_authorization_guard(PermissionTypeEnum.WRITE)
CustomerAdminGuard = create_customer_authorization_guard(PermissionTypeEnum.ADMIN)


def _authorize_access_policy_access(
    policy_id: NanoIdType,
    authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_type: PermissionTypeEnum = PermissionTypeEnum.ADMIN,
) -> AuthorizedUser:
    """
    Authorize admin access to an access policy using the RBAC permission system
    """
    [customer_id] = AccessPolicy.get_query(AccessPolicy.id == policy_id).with_entities(AccessPolicy.customer_id).one()

    authz_service = PermissionService.factory()
    user = authz_service.get_authz_user_authn_user(authn_user=authn_user)

    # If customer_id is None (global policy), only staff can access
    if customer_id is None:
        is_staff = authz_service.is_staff_user_id(user.id)
        if not is_staff:
            raise APIException(
                code=status.HTTP_403_FORBIDDEN,
                message='Permission denied',
            )
        return user

    # Check permission on the customer if available
    if customer_id is not None:
        has_permission = authz_service.check_permission(
            user_id=user.id,
            permission_type=permission_type,
            resource_type=ResourceTypeEnum.CUSTOMER,
            resource_id=customer_id,
        )
        if not has_permission:
            raise APIException(
                code=status.HTTP_403_FORBIDDEN,
                message='Permission denied',
            )

    return user


def _authorize_access_role_access(
    role_id: NanoIdType,
    authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    permission_type: PermissionTypeEnum = PermissionTypeEnum.ADMIN,
) -> AuthorizedUser:
    """
    Authorize admin access to an access role using the RBAC permission system
    """
    [customer_id] = AccessRole.get_query(AccessRole.id == role_id).with_entities(AccessRole.customer_id).one()

    authz_service = PermissionService.factory()
    user = authz_service.get_authz_user_authn_user(authn_user=authn_user)

    # If customer_id is None (global role), only staff can access
    if customer_id is None:
        is_staff = authz_service.is_staff_user_id(user.id)
        if not is_staff:
            raise APIException(
                code=status.HTTP_403_FORBIDDEN,
                message='Permission denied',
            )
        return user

    # Check permission on the customer if available
    if customer_id is not None:
        has_permission = authz_service.check_permission(
            user_id=user.id,
            permission_type=permission_type,
            resource_type=ResourceTypeEnum.CUSTOMER,
            resource_id=customer_id,
        )
        if not has_permission:
            raise APIException(
                code=status.HTTP_403_FORBIDDEN,
                message='Permission denied',
            )

    return user


# Access Policy guards
def create_access_policy_authorization_guard(permission_type: PermissionTypeEnum):
    """Factory function that creates access policy authorization guards for different permission types."""

    def _authorize_access_policy(
        policy_id: NanoIdType,
        authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    ) -> AuthorizedUser:
        """Authorize access to an access policy using the RBAC permission system."""
        return _authorize_access_policy_access(policy_id, authn_user, permission_type)

    return _RouterGuard(dependency=_authorize_access_policy)


# Access Role guards
def create_access_role_authorization_guard(permission_type: PermissionTypeEnum):
    """Factory function that creates access role authorization guards for different permission types."""

    def _authorize_access_role(
        role_id: NanoIdType,
        authn_user: AuthenticatedUser = AuthenticatedUserGuard(),
    ) -> AuthorizedUser:
        """Authorize access to an access role using the RBAC permission system."""
        return _authorize_access_role_access(role_id, authn_user, permission_type)

    return _RouterGuard(dependency=_authorize_access_role)


# Create the actual guard objects
AccessPolicyAdminGuard = create_access_policy_authorization_guard(PermissionTypeEnum.ADMIN)
AccessRoleAdminGuard = create_access_role_authorization_guard(PermissionTypeEnum.ADMIN)
