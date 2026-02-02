from typing import Optional

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Query, status
from starlette.requests import Request

from src import settings
from src.common.domain import BaseDomain
from src.common.exceptions import APIException
from src.common.nanoid import NanoIdType
from src.common.request import get_user_ip_address_from_request
from src.core.authentication import (
    AuthenticatedUser,
    AuthenticatedUserGuard,
    AuthenticationService,
    AuthException,
    Token,
    oauth,
)
from src.core.authorization import AccessControlService, PermissionService
from src.core.authorization.domains import (
    AccessPolicyRead,
    AccessPolicyWithRolePayload,
    AccessRoleCreate,
    AccessRoleCreateWithPolicies,
    AccessRoleRead,
    AccessRoleSummary,
    CreateCustomerPayload,
    CustomerDefaultRoleUpdate,
    Me,
    MembershipAssignmentRead,
    MyLoginConfig,
    PolicyRoleAssignmentUpdate,
    RoleCreateWithPolicies,
    RoleMembershipAssignmentUpdate,
    RolePolicyAssignmentUpdate,
)
from src.core.authorization.guards import (
    AccessRoleAdminGuard,
    CustomerAdminGuard,
    StaffUserGuard,
    UserGuard,
)
from src.core.service import CoreService
from src.core.user import UserRead, UserService
from src.network.database.decorator import read_only_route

authorization_router = APIRouter()


@read_only_route
@authorization_router.get('/me', dependencies=[UserGuard()])
def get_me(
    user: AuthenticatedUser = UserGuard(),
    core_service: CoreService = Depends(CoreService.factory),
) -> Me:
    return core_service.get_me(user_id=user.id, impersonator_id=user.impersonator_id)


@authorization_router.post('/create-customer', dependencies=[AuthenticatedUserGuard()])
def create_customer(
    payload: CreateCustomerPayload,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    core_service: CoreService = Depends(CoreService.factory),
) -> Me:
    """
    Create a new customer for a user without any memberships.

    Creates a Customer with the given name, assigns the user to a Membership,
    and grants them admin access to the customer.
    """
    return core_service.create_customer_with_admin_membership(user_id=user.id, name=payload.name)


class AddStaffMembershipPayload(BaseDomain):
    first_name: str
    last_name: str
    email: str


@authorization_router.post('/add-staff-user', dependencies=[StaffUserGuard()])
def add_staff_user(
    add_membership_payload: AddStaffMembershipPayload,
    core_service: CoreService = Depends(CoreService.factory),
) -> None:
    return core_service.create_staff_user(
        email=add_membership_payload.email,
        first_name=add_membership_payload.first_name,
        last_name=add_membership_payload.last_name,
    )


@authorization_router.get('/my-login-config', dependencies=[])
def get_my_login_config(
    email: str,
    core_service: CoreService = Depends(CoreService.factory),
) -> MyLoginConfig:
    """
    Fetches required login details for a user email.
    If the email is invalid, it will return default login settings to
    disguise implementation details of our system.
    """

    try:
        check_deliverability = True
        if settings.IS_LOCAL or settings.IS_DEMO:
            check_deliverability = False
        validate_email(email, check_deliverability=check_deliverability)
    except EmailNotValidError:
        raise APIException(code=status.HTTP_400_BAD_REQUEST, message=f'Invalid email address: {email}')

    return core_service.get_my_login_config_for_email(email=email, raise_exceptions=False)


# Impersonate endpoints are here for StaffUserGuard
@authorization_router.post('/impersonate', response_model=Token, dependencies=[StaffUserGuard()])
def impersonate_user(
    request: Request,
    target_user_id: str,
    token: str = Depends(oauth),
    authentication_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token:
    user_ip = get_user_ip_address_from_request(request=request)
    try:
        return authentication_service.impersonate_user(
            access_token=token,
            target_user_id=target_user_id,
            ip_address=user_ip,
        )
    except AuthException as e:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message=str(e.message),
        )


@authorization_router.post('/cancel-impersonate', response_model=Token, dependencies=[AuthenticatedUserGuard()])
def cancel_impersonate_user(
    request: Request,
    token: str = Depends(oauth),
    authentication_service: AuthenticationService = Depends(AuthenticationService.factory),
) -> Token:
    user_ip = get_user_ip_address_from_request(request=request)
    try:
        return authentication_service.cancel_impersonate_user(
            access_token=token,
            ip_address=user_ip,
        )
    except AuthException as e:
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message=str(e.message),
        )


@authorization_router.get('/search-users-to-impersonate', dependencies=[StaffUserGuard()])
def search_users_to_impersonate(
    search: str,
    user_service: UserService = Depends(UserService.factory),
) -> list[UserRead]:
    return user_service.search_users(search=search)


# RBAC Management Routes


# Access Roles
@authorization_router.get('/list-customer-access-roles', dependencies=[CustomerAdminGuard()])
def list_customer_access_roles(
    customer_id: Optional[NanoIdType] = Query(None),
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[AccessRoleSummary]:
    return access_control_service.list_access_roles(customer_id=customer_id)


@authorization_router.get('/list-customer-access-roles-legacy', dependencies=[CustomerAdminGuard()])
def list_customer_access_roles_legacy(
    customer_id: NanoIdType = Query(...),
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[AccessRoleSummary]:
    """List access roles for a customer (legacy endpoint for backward compatibility)"""
    return access_control_service.list_access_roles(customer_id=customer_id)


@authorization_router.post('/create-customer-access-role', dependencies=[CustomerAdminGuard()])
def create_customer_access_role(
    customer_id: NanoIdType,  # used for perms
    role: AccessRoleCreateWithPolicies,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> AccessRoleRead:
    return access_control_service.create_access_role(role=role)


@authorization_router.post('/roles/with-policies', dependencies=[CustomerAdminGuard()])
def create_customer_access_role_with_policies(
    customer_id: NanoIdType,  # used in perms
    role_data: RoleCreateWithPolicies,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> AccessRoleRead:
    """
    Create a new access role with initial policy assignments.

    This endpoint allows creating a role and assigning it to policies in a single operation.
    """
    return access_control_service.create_role_with_policies(customer_id=customer_id, role_data=role_data)


@authorization_router.get('/get-customer-access-role', dependencies=[CustomerAdminGuard()])
def get_customer_access_role(
    customer_id: NanoIdType,
    role_id: NanoIdType,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> AccessRoleRead:
    """Get an access role by ID."""
    return access_control_service.get_customer_access_role(customer_id=customer_id, role_id=role_id)


@authorization_router.patch('/update-customer-access-role', dependencies=[CustomerAdminGuard()])
def update_customer_access_role(
    customer_id: NanoIdType,
    role_id: NanoIdType,
    role_update: AccessRoleCreate,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> AccessRoleRead:
    """Update an access role."""
    # TODO: Add permission check to ensure user can update this role
    return access_control_service.update_access_role(
        customer_id=customer_id,
        role_id=role_id,
        name=role_update.name,
        description=role_update.description,
    )


@authorization_router.delete('/delete-customer-access-role', dependencies=[CustomerAdminGuard()])
def delete_customer_access_role(
    customer_id: NanoIdType,
    role_id: NanoIdType,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> None:
    access_control_service.delete_access_role(role_id=role_id, customer_id=customer_id)


# Membership Assignments
@authorization_router.get('/assignments', dependencies=[AccessRoleAdminGuard(), CustomerAdminGuard])
def list_membership_assignments(
    customer_id: NanoIdType = None,
    role_id: NanoIdType = None,
    membership_id: NanoIdType = None,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[MembershipAssignmentRead]:
    """List all membership assignments, optionally filtered by membership or role."""
    return access_control_service.list_membership_assignments(membership_id=membership_id, role_id=role_id)


@authorization_router.get('/list-policies-for-customer-role', dependencies=[CustomerAdminGuard()])
def list_policies_for_customer_role(
    customer_id: NanoIdType,
    role_id: NanoIdType,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[AccessPolicyRead]:
    """
    List all policies assigned to a specific role.

    Args:
        role_id: The ID of the role to get policies for
        customer_id: The ID of the customer the role belongs to

    Returns:
        List of access policies assigned to the role
    """
    return access_control_service.get_policies_for_role(role_id=role_id, customer_id=customer_id)


# Access Policies
@authorization_router.get('/list-access-policies-for-customer', dependencies=[CustomerAdminGuard()])
def list_access_policies_for_customer(
    customer_id: NanoIdType,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[AccessPolicyRead]:
    return access_control_service.list_access_policies(customer_id=customer_id)


@authorization_router.get('/list-staff-memberships-for-customer', dependencies=[CustomerAdminGuard()])
def list_staff_memberships_for_customer(
    customer_id: Optional[NanoIdType] = None,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[NanoIdType]:
    """
    List membership IDs for users who are members of a customer via their staff role.

    This endpoint is used by the UI to filter out staff users from certain operations,
    such as role assignment dialogs, where staff users should be handled differently.

    Args:
        customer_id: Optional ID of the customer to filter by
        access_control_service: The access control service instance
        user: The authenticated user making the request

    Returns:
        A list of membership IDs belonging to staff users for the specified customer
    """
    return access_control_service.list_staff_memberships_for_customer(customer_id=customer_id)


@authorization_router.post('/create-customer-access-policy', dependencies=[CustomerAdminGuard()])
def create_customer_access_policy(
    customer_id: NanoIdType,
    policy: AccessPolicyWithRolePayload,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> AccessPolicyRead:
    return access_control_service.create_access_policy(policy=policy)


@authorization_router.post('/update-customer-policy-role-assignments', dependencies=[CustomerAdminGuard()])
def update_customer_policy_role_assignments(
    customer_id: NanoIdType,
    assignment_update: PolicyRoleAssignmentUpdate,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> dict:
    """Update role assignments for a policy."""
    access_control_service.update_policy_role_assignments(assignment_update=assignment_update)
    return {'message': 'Policy role assignments updated successfully'}


@authorization_router.post('/update-customer-role-policy-assignments', dependencies=[CustomerAdminGuard()])
def update_customer_role_policy_assignments(
    customer_id: NanoIdType,  # used in perms
    assignment_update: RolePolicyAssignmentUpdate,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> dict:
    """Update policy assignments for a role."""
    access_control_service.update_role_policy_assignments(assignment_update=assignment_update)
    return {'message': 'Role policy assignments updated successfully'}


@authorization_router.get('/get-customer-access-policy', dependencies=[CustomerAdminGuard()])
def get_customer_access_policy(
    customer_id: NanoIdType,
    policy_id: NanoIdType,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> AccessPolicyRead:
    return access_control_service.get_access_policy(customer_id=customer_id, policy_id=policy_id)


@authorization_router.patch('/update-customer-access-policy', dependencies=[CustomerAdminGuard()])
def update_customer_access_policy(
    customer_id: NanoIdType,
    policy_id: NanoIdType,
    policy_update: AccessPolicyWithRolePayload,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> AccessPolicyRead:
    return access_control_service.update_customer_access_policy(
        customer_id=customer_id, policy_id=policy_id, policy=policy_update
    )


@authorization_router.delete('/delete-customer-access-policy', dependencies=[CustomerAdminGuard()])
def delete_customer_access_policy(
    customer_id: NanoIdType,
    policy_id: NanoIdType,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> None:
    access_control_service.delete_access_policy(customer_id=customer_id, policy_id=policy_id)


@authorization_router.get('/list-roles-for-customer-policy', dependencies=[CustomerAdminGuard()])
def list_roles_for_customer_policy(
    customer_id: NanoIdType,
    policy_id: NanoIdType,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[AccessRoleRead]:
    """
    List all roles that have a specific policy assigned.

    Args:
        policy_id: The ID of the policy to get roles for
        customer_id: The ID of the customer the policy belongs to

    Returns:
        List of access roles that have the specified policy assigned
    """
    return access_control_service.get_roles_for_policy(policy_id=policy_id, customer_id=customer_id)


@authorization_router.post('/role-membership-assignments', dependencies=[AccessRoleAdminGuard()])
def update_role_membership_assignments(
    role_id: NanoIdType,
    assignment_update: RoleMembershipAssignmentUpdate,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> None:
    access_control_service.update_membership_assignments_for_role(
        role_id=role_id, membership_ids=assignment_update.membership_ids
    )


@authorization_router.get('/resources', dependencies=[CustomerAdminGuard()])
def list_resources_by_type(
    customer_id: NanoIdType,
    resource_type: str,
    permission_service: PermissionService = Depends(PermissionService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> list[dict]:
    """
    List all resources of a specific type for a customer.

    This endpoint returns resources that can be used in policy resource selectors.
    The response format includes id and name properties for each resource.
    """
    return permission_service.list_resources_by_type(resource_type=resource_type, customer_id=customer_id)


@authorization_router.get('/customer/{customer_id}/has-admin-access', dependencies=[UserGuard()])
def check_customer_admin_access(
    customer_id: NanoIdType,
    permission_service: PermissionService = Depends(PermissionService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> dict:
    """
    Check if the current user has admin access to a specific customer.

    Admin access is granted if the user is either a staff user or
    has a role with admin permissions for the customer.

    Args:
        customer_id: The ID of the customer to check access for

    Returns:
        A dictionary with a boolean 'has_admin_access' indicating if the user has admin access
    """
    has_admin = permission_service.has_customer_admin_access(
        user_id=user.id,
        customer_id=customer_id,
    )

    return {'has_admin_access': has_admin}


@authorization_router.patch('/update-customer-default-role', dependencies=[CustomerAdminGuard()])
def update_customer_default_role(
    customer_id: NanoIdType,
    update: CustomerDefaultRoleUpdate,
    access_control_service: AccessControlService = Depends(AccessControlService.factory),
    user: AuthenticatedUser = UserGuard(),
) -> dict:
    access_control_service.update_customer_default_role(customer_id=customer_id, update=update)
    return {'message': 'Default role updated successfully', 'role_id': update.role_id}
