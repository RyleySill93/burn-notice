from typing import TYPE_CHECKING, Optional

from src.common.nanoid import NanoIdType
from src.core.authorization.constants import (
    STAFF_ROLE_NAME,
    PermissionEffectEnum,
    PermissionTypeEnum,
    ResourceSelectorTypeEnum,
    ResourceTypeEnum,
)
from src.core.authorization.domains import (
    AccessPolicyCreate,
    AccessPolicyRead,
    AccessPolicyWithRolePayload,
    AccessRoleCreate,
    AccessRoleCreateWithPolicies,
    AccessRoleRead,
    AccessRoleSummary,
    CustomerDefaultRoleUpdate,
    MembershipAssignmentCreate,
    MembershipAssignmentRead,
    PolicyRoleAssignmentCreate,
    PolicyRoleAssignmentUpdate,
    RoleCreateWithPolicies,
    RolePolicyAssignmentUpdate,
)
from src.core.authorization.models import AccessPolicy, AccessRole, MembershipAssignment, PolicyRoleAssignment
from src.core.membership import Membership, MembershipService

if TYPE_CHECKING:
    from src.core.authorization.services.permission_service import PermissionService


class AccessControlService:
    """
    Service for managing RBAC (Role-Based Access Control) resources.

    This service handles CRUD operations for:
    - Access Roles
    - Access Policies
    - Membership Assignments (role-to-membership mappings)
    - Policy-Role Assignments

    For permission evaluation (checking if a user has access), use PermissionService.
    """

    def __init__(
        self,
        membership_service: MembershipService,
        permission_service: Optional['PermissionService'] = None,
    ):
        """
        Initialize the AccessControlService.

        Args:
            membership_service: Service for managing memberships
            permission_service: Service for permission evaluation and cache invalidation
        """
        self.membership_service = membership_service
        self._permission_service = permission_service

    @property
    def permission_service(self) -> 'PermissionService':
        """Lazy load permission service to avoid circular imports"""
        if self._permission_service is None:
            from src.core.authorization.services.permission_service import PermissionService

            self._permission_service = PermissionService.factory()
        return self._permission_service

    @classmethod
    def factory(cls) -> 'AccessControlService':
        """Create an instance of AccessControlService with default dependencies."""
        return cls(
            membership_service=MembershipService.factory(),
            permission_service=None,  # Lazy loaded
        )

    # ==================== Role Management ====================

    def list_access_roles(self, customer_id: Optional[NanoIdType] = None) -> list[AccessRoleSummary]:
        """
        List all access roles, optionally filtered by customer.

        Args:
            customer_id: Optional customer ID to filter roles by

        Returns:
            List of access role summaries with assignment counts
        """
        if customer_id:
            roles = AccessRole.list(AccessRole.customer_id == customer_id)
        else:
            roles = AccessRole.list()

        role_summaries = []
        for role in roles:
            # Get membership assignment count
            membership_count = MembershipAssignment.count(MembershipAssignment.access_role_id == role.id)

            # Get policy assignment count
            policy_count = PolicyRoleAssignment.count(PolicyRoleAssignment.role_id == role.id)

            role_summaries.append(
                AccessRoleSummary(
                    id=role.id,
                    name=role.name,
                    description=role.description,
                    customer_id=role.customer_id,
                    is_default=role.is_default,
                    membership_count=membership_count,
                    policy_count=policy_count,
                )
            )

        return role_summaries

    def create_access_role(self, role: AccessRoleCreateWithPolicies) -> AccessRoleRead:
        """
        Create a new access role.

        Args:
            role: The role creation data

        Returns:
            The created access role
        """
        access_role = AccessRole.create(AccessRoleCreate(**role.model_dump(exclude={'policies'})))
        return access_role

    def create_role_with_policies(self, customer_id: NanoIdType, role_data: RoleCreateWithPolicies) -> AccessRoleRead:
        """
        Create a new role with associated policies in a single operation.

        Args:
            customer_id: The customer ID the role belongs to
            role_data: Role creation data including policies

        Returns:
            The created access role
        """
        # Create the role
        role = AccessRole.create(
            AccessRoleCreate(
                name=role_data.name,
                description=role_data.description,
                customer_id=customer_id,
            )
        )

        # Create policies and assignments
        for policy_data in role_data.policies:
            policy = AccessPolicy.create(
                AccessPolicyCreate(
                    permission_type=policy_data.permission_type,
                    resource_type=policy_data.resource_type,
                    resource_selector=policy_data.resource_selector,
                    effect=policy_data.effect,
                    customer_id=customer_id,
                )
            )
            PolicyRoleAssignment.create(
                PolicyRoleAssignmentCreate(
                    policy_id=policy.id,
                    role_id=role.id,
                )
            )

        return role

    def get_customer_access_role(self, customer_id: NanoIdType, role_id: NanoIdType) -> AccessRoleRead:
        """Get an access role by ID for a specific customer."""
        return AccessRole.get((AccessRole.id == role_id) & (AccessRole.customer_id == customer_id))

    def update_access_role(
        self, customer_id: NanoIdType, role_id: NanoIdType, name: str, description: str
    ) -> AccessRoleRead:
        """Update an access role's name and description."""
        return AccessRole.update(id=role_id, name=name, description=description)

    def delete_access_role(self, role_id: NanoIdType, customer_id: NanoIdType | None = None) -> None:
        """
        Delete an access role and all associated assignments.

        Args:
            role_id: The ID of the role to delete
            customer_id: Optional customer ID for validation
        """
        # Get users who will be affected for cache invalidation
        affected_user_ids = set()
        membership_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == role_id)
        for assignment in membership_assignments:
            membership = Membership.get_or_none(id=assignment.membership_id)
            if membership and membership.user_id:
                affected_user_ids.add(membership.user_id)

        # Delete policy assignments first
        PolicyRoleAssignment.delete(PolicyRoleAssignment.role_id == role_id)

        # Delete membership assignments
        MembershipAssignment.delete(MembershipAssignment.access_role_id == role_id)

        # Delete the role itself
        if customer_id:
            AccessRole.delete((AccessRole.id == role_id) & (AccessRole.customer_id == customer_id))
        else:
            AccessRole.delete(id=role_id)

        # Invalidate caches for affected users
        for user_id in affected_user_ids:
            self.permission_service.invalidate_permission_cache(user_id)

    def get_or_create_customer_admin_role(self, customer_id: NanoIdType, customer_name: str) -> AccessRoleRead:
        """
        Get or create a customer admin role for a specific customer.

        Args:
            customer_id: The customer ID
            customer_name: The customer name (used in role description)

        Returns:
            The customer admin role
        """
        customer_admin_role = AccessRole.get_or_none(
            (AccessRole.name == 'Admin') & (AccessRole.customer_id == customer_id)
        )

        if not customer_admin_role:
            customer_admin_role = AccessRole.create(
                AccessRoleCreate(
                    name='Admin',
                    description=f'Administrative access to {customer_name} customer',
                    customer_id=customer_id,
                )
            )

            # Create customer admin policy
            policy = AccessPolicy.create(
                AccessPolicyCreate(
                    name=f'Admin - {customer_name}',
                    permission_type=PermissionTypeEnum.ADMIN,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer_id},
                    effect=PermissionEffectEnum.ALLOW,
                    customer_id=customer_id,
                )
            )

            # Link policy to role
            PolicyRoleAssignment.create(
                PolicyRoleAssignmentCreate(
                    policy_id=policy.id,
                    role_id=customer_admin_role.id,
                )
            )

        return customer_admin_role

    def get_or_create_customer_member_role(self, customer_id: NanoIdType, customer_name: str) -> AccessRoleRead:
        """
        Get or create a member role for a specific customer.

        This role grants READ access to the customer, allowing members to see
        projects and other resources within the customer through hierarchical
        permission inheritance.

        Args:
            customer_id: The customer ID
            customer_name: The customer name (used in role description)

        Returns:
            The customer member role
        """
        customer_member_role = AccessRole.get_or_none(
            (AccessRole.name == 'Member') & (AccessRole.customer_id == customer_id)
        )

        if not customer_member_role:
            customer_member_role = AccessRole.create(
                AccessRoleCreate(
                    name='Member',
                    description=f'Member access to {customer_name}',
                    customer_id=customer_id,
                )
            )

            # Create customer read policy
            policy = AccessPolicy.create(
                AccessPolicyCreate(
                    name=f'Member Read - {customer_name}',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer_id},
                    effect=PermissionEffectEnum.ALLOW,
                    customer_id=customer_id,
                )
            )

            # Link policy to role
            PolicyRoleAssignment.create(
                PolicyRoleAssignmentCreate(
                    policy_id=policy.id,
                    role_id=customer_member_role.id,
                )
            )

        return customer_member_role

    def grant_customer_member_access(
        self, membership_id: NanoIdType, customer_id: NanoIdType, customer_name: str
    ) -> None:
        """
        Grant customer member (READ) access to a membership.

        Args:
            membership_id: The membership ID to grant member access to
            customer_id: The customer ID
            customer_name: The customer name
        """
        customer_member_role = self.get_or_create_customer_member_role(customer_id, customer_name)
        self.assign_role_to_membership(membership_id=membership_id, role_id=customer_member_role.id)

    def get_customer_default(self, customer_id: NanoIdType) -> AccessRoleRead:
        """Get the default role for a customer."""
        return AccessRole.get((AccessRole.customer_id == customer_id) & (AccessRole.is_default == True))

    def update_customer_default_role(self, customer_id: NanoIdType, update: CustomerDefaultRoleUpdate) -> None:
        """
        Update which role is the default for a customer.

        Args:
            customer_id: The customer ID
            update: Contains the new default role ID
        """
        # First, unset the current default
        current_default = AccessRole.get_or_none(
            (AccessRole.customer_id == customer_id) & (AccessRole.is_default == True)
        )
        if current_default:
            AccessRole.update(id=current_default.id, is_default=False)

        # Set the new default
        AccessRole.update(id=update.role_id, is_default=True)

    # ==================== Policy Management ====================

    def list_access_policies(
        self,
        customer_id: NanoIdType,
        role_id: Optional[NanoIdType] = None,
        resource_type: Optional[ResourceTypeEnum] = None,
    ) -> list[AccessPolicyRead]:
        """
        List access policies with optional filters.

        Args:
            customer_id: The customer ID to filter by
            role_id: Optional role ID to filter policies assigned to
            resource_type: Optional resource type filter

        Returns:
            List of access policies matching the filters
        """
        filters = [AccessPolicy.customer_id == customer_id]

        if resource_type:
            filters.append(AccessPolicy.resource_type == resource_type)

        policies = AccessPolicy.list(*filters)

        if role_id:
            # Filter to only policies assigned to this role
            policy_role_assignments = PolicyRoleAssignment.list(PolicyRoleAssignment.role_id == role_id)
            assigned_policy_ids = {pra.policy_id for pra in policy_role_assignments}
            policies = [p for p in policies if p.id in assigned_policy_ids]

        return policies

    def create_access_policy(self, policy: AccessPolicyWithRolePayload) -> AccessPolicyRead:
        """
        Create a new access policy and optionally assign it to a role.

        Args:
            policy: The policy creation data including optional role_id

        Returns:
            The created access policy
        """
        access_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name=policy.name,
                permission_type=policy.permission_type,
                resource_type=policy.resource_type,
                resource_selector=policy.resource_selector,
                effect=policy.effect,
                customer_id=policy.customer_id,
            )
        )

        if policy.role_id:
            PolicyRoleAssignment.create(
                PolicyRoleAssignmentCreate(
                    policy_id=access_policy.id,
                    role_id=policy.role_id,
                )
            )

        return access_policy

    def get_access_policy(self, customer_id: NanoIdType, policy_id: NanoIdType) -> AccessPolicyRead:
        """Get an access policy by ID for a specific customer."""
        return AccessPolicy.get((AccessPolicy.id == policy_id) & (AccessPolicy.customer_id == customer_id))

    def update_customer_access_policy(
        self, customer_id: NanoIdType, policy_id: NanoIdType, policy: AccessPolicyWithRolePayload
    ) -> AccessPolicyRead:
        """Update an access policy."""
        return AccessPolicy.update(
            id=policy_id,
            permission_type=policy.permission_type,
            resource_type=policy.resource_type,
            resource_selector=policy.resource_selector,
            effect=policy.effect,
        )

    def delete_access_policy(self, customer_id: NanoIdType, policy_id: NanoIdType) -> None:
        """Delete an access policy and its role assignments."""
        PolicyRoleAssignment.delete(PolicyRoleAssignment.policy_id == policy_id)
        AccessPolicy.delete((AccessPolicy.id == policy_id) & (AccessPolicy.customer_id == customer_id))

    def get_policies_for_role(self, role_id: NanoIdType, customer_id: NanoIdType) -> list[AccessPolicyRead]:
        """
        Get all policies assigned to a specific role.

        Args:
            role_id: The ID of the role to get policies for
            customer_id: The ID of the customer the role belongs to

        Returns:
            List of access policies assigned to the role
        """
        role = AccessRole.get_or_none(id=role_id, customer_id=customer_id)
        if not role:
            return []

        # Get all policy assignments for this role
        policy_assignments = PolicyRoleAssignment.list(PolicyRoleAssignment.role_id == role_id)
        policy_ids = [pa.policy_id for pa in policy_assignments]

        if not policy_ids:
            return []

        # Get the policies
        policies = AccessPolicy.list(AccessPolicy.id.in_(policy_ids))
        return policies

    def get_roles_for_policy(self, policy_id: NanoIdType, customer_id: NanoIdType) -> list[AccessRoleRead]:
        """
        Get all roles that have a specific policy assigned.

        Args:
            policy_id: The ID of the policy to get roles for
            customer_id: The ID of the customer the policy belongs to

        Returns:
            List of access roles that have this policy assigned
        """
        policy = AccessPolicy.get_or_none(id=policy_id, customer_id=customer_id)
        if not policy:
            return []

        # Get all role assignments for this policy
        role_assignments = PolicyRoleAssignment.list(PolicyRoleAssignment.policy_id == policy_id)
        role_ids = [ra.role_id for ra in role_assignments]

        if not role_ids:
            return []

        # Get the roles
        roles = AccessRole.list(AccessRole.id.in_(role_ids))
        return roles

    # ==================== Assignment Management ====================

    def assign_access_role_to_membership(self, access_role_id: NanoIdType, membership_id: NanoIdType) -> None:
        """
        Assign an access role to a membership.

        Args:
            access_role_id: The ID of the access role to assign
            membership_id: The ID of the membership to assign the role to
        """
        existing = MembershipAssignment.list(
            (MembershipAssignment.membership_id == membership_id)
            & (MembershipAssignment.access_role_id == access_role_id)
        )
        if not existing:
            MembershipAssignment.create(
                MembershipAssignmentCreate(access_role_id=access_role_id, membership_id=membership_id)
            )

            # Invalidate cache for the user
            membership = Membership.get(id=membership_id)
            if membership and membership.user_id:
                self.permission_service.invalidate_permission_cache(membership.user_id)

    def assign_role_to_membership(self, membership_id: NanoIdType, role_id: NanoIdType) -> MembershipAssignmentRead:
        """
        Assign a role to a membership, returning the assignment.

        Args:
            membership_id: The membership ID
            role_id: The role ID to assign

        Returns:
            The membership assignment (existing or newly created)
        """
        existing_assignment = MembershipAssignment.get_or_none(
            (MembershipAssignment.membership_id == membership_id) & (MembershipAssignment.access_role_id == role_id)
        )

        if not existing_assignment:
            existing_assignment = MembershipAssignment.create(
                MembershipAssignmentCreate(membership_id=membership_id, access_role_id=role_id)
            )
            membership = self.membership_service.get_membership_for_id(membership_id)
            if membership and membership.user_id:
                self.permission_service.invalidate_permission_cache(membership.user_id)

        return existing_assignment

    def grant_customer_admin_access(
        self, membership_id: NanoIdType, customer_id: NanoIdType, customer_name: str
    ) -> None:
        """
        Grant customer admin access to a membership.

        Args:
            membership_id: The membership ID to grant admin access to
            customer_id: The customer ID
            customer_name: The customer name
        """
        customer_admin_role = self.get_or_create_customer_admin_role(customer_id, customer_name)
        self.assign_role_to_membership(membership_id=membership_id, role_id=customer_admin_role.id)

    def grant_staff_admin_access(self, user_id: NanoIdType) -> None:
        """
        Grant the staff role to a user across all their memberships.

        Args:
            user_id: The user ID to grant staff access to
        """
        memberships = self.membership_service.list_memberships_for_user(user_id)
        if not memberships:
            return

        staff_admin_role = AccessRole.get(AccessRole.name == STAFF_ROLE_NAME)

        for membership in memberships:
            self.assign_access_role_to_membership(access_role_id=staff_admin_role.id, membership_id=membership.id)

    def assign_customer_to_customer_admin_set(self, access_role_id: NanoIdType, customer_id: NanoIdType) -> None:
        """
        Add customer admin permissions for a specific customer to an access role.

        Args:
            access_role_id: The ID of the access role to add the permission to
            customer_id: The customer ID to grant admin access to
        """
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name=f'Customer Admin - {customer_id}',
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer_id},
                effect=PermissionEffectEnum.ALLOW,
                customer_id=customer_id,
            )
        )

        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(
                policy_id=policy.id,
                role_id=access_role_id,
            )
        )

    def assign_customer_to_auditor_set(self, access_role_id: NanoIdType, customer_id: NanoIdType) -> None:
        """
        Add auditor (read-only) permissions for a specific customer to an access role.

        Args:
            access_role_id: The ID of the access role to add the permission to
            customer_id: The customer ID to grant read access to
        """
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name=f'Customer Auditor - {customer_id}',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer_id},
                effect=PermissionEffectEnum.ALLOW,
                customer_id=customer_id,
            )
        )
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(
                policy_id=policy.id,
                role_id=access_role_id,
            )
        )

    def update_role_policy_assignments(self, assignment_update: RolePolicyAssignmentUpdate) -> None:
        """
        Update which policies are assigned to a role.

        Args:
            assignment_update: Contains role_id, customer_id, and list of policy_ids
        """
        role_id = assignment_update.role_id
        policy_ids = assignment_update.policy_ids

        # Get current assignments
        current_assignments = PolicyRoleAssignment.list(PolicyRoleAssignment.role_id == role_id)
        current_policy_ids = {a.policy_id for a in current_assignments}

        # Determine what to add and remove
        new_policy_ids = set(policy_ids)
        to_add = new_policy_ids - current_policy_ids
        to_remove = current_policy_ids - new_policy_ids

        # Remove old assignments
        for policy_id in to_remove:
            PolicyRoleAssignment.delete(
                (PolicyRoleAssignment.role_id == role_id) & (PolicyRoleAssignment.policy_id == policy_id)
            )

        # Add new assignments
        for policy_id in to_add:
            PolicyRoleAssignment.create(
                PolicyRoleAssignmentCreate(
                    policy_id=policy_id,
                    role_id=role_id,
                )
            )

        # Invalidate caches for affected users
        membership_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == role_id)
        for assignment in membership_assignments:
            membership = Membership.get_or_none(id=assignment.membership_id)
            if membership and membership.user_id:
                self.permission_service.invalidate_permission_cache(membership.user_id)

    def update_policy_role_assignments(self, assignment_update: PolicyRoleAssignmentUpdate) -> None:
        """
        Update which roles have a specific policy assigned.

        Args:
            assignment_update: Contains policy_id, customer_id, and list of role_ids
        """
        policy_id = assignment_update.policy_id
        role_ids = assignment_update.role_ids

        # Get current assignments
        current_assignments = PolicyRoleAssignment.list(PolicyRoleAssignment.policy_id == policy_id)
        current_role_ids = {a.role_id for a in current_assignments}

        # Determine what to add and remove
        new_role_ids = set(role_ids)
        to_add = new_role_ids - current_role_ids
        to_remove = current_role_ids - new_role_ids

        # Collect affected user IDs before changes
        affected_user_ids = set()

        # Remove old assignments
        for role_id in to_remove:
            membership_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == role_id)
            for assignment in membership_assignments:
                membership = Membership.get_or_none(id=assignment.membership_id)
                if membership and membership.user_id:
                    affected_user_ids.add(membership.user_id)

            PolicyRoleAssignment.delete(
                (PolicyRoleAssignment.policy_id == policy_id) & (PolicyRoleAssignment.role_id == role_id)
            )

        # Add new assignments
        for role_id in to_add:
            PolicyRoleAssignment.create(
                PolicyRoleAssignmentCreate(
                    policy_id=policy_id,
                    role_id=role_id,
                )
            )

            membership_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == role_id)
            for assignment in membership_assignments:
                membership = Membership.get_or_none(id=assignment.membership_id)
                if membership and membership.user_id:
                    affected_user_ids.add(membership.user_id)

        # Invalidate caches for all affected users
        for user_id in affected_user_ids:
            self.permission_service.invalidate_permission_cache(user_id)

    def update_policy_role_assignments_for_role(self, role_id: NanoIdType, policy_ids: list[NanoIdType]) -> None:
        """
        Update the policy assignments for a role (replace all with new list).

        Args:
            role_id: The role ID to update
            policy_ids: The new list of policy IDs to assign
        """
        # Get current policy assignments
        current_assignments = PolicyRoleAssignment.list(PolicyRoleAssignment.role_id == role_id)
        current_policy_ids = {a.policy_id for a in current_assignments}

        new_policy_ids = set(policy_ids)
        to_add = new_policy_ids - current_policy_ids
        to_remove = current_policy_ids - new_policy_ids

        # Remove old
        for policy_id in to_remove:
            PolicyRoleAssignment.delete(
                (PolicyRoleAssignment.role_id == role_id) & (PolicyRoleAssignment.policy_id == policy_id)
            )

        # Add new
        for policy_id in to_add:
            PolicyRoleAssignment.create(
                PolicyRoleAssignmentCreate(
                    policy_id=policy_id,
                    role_id=role_id,
                )
            )

        # Invalidate caches
        membership_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == role_id)
        for assignment in membership_assignments:
            membership = Membership.get_or_none(id=assignment.membership_id)
            if membership and membership.user_id:
                self.permission_service.invalidate_permission_cache(membership.user_id)

    def update_membership_assignments_for_role(self, role_id: NanoIdType, membership_ids: list[NanoIdType]) -> None:
        """
        Update which memberships have a role assigned (replace all with new list).

        Args:
            role_id: The role ID
            membership_ids: The new list of membership IDs to assign the role to
        """
        # Get current assignments
        current_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == role_id)
        current_membership_ids = {a.membership_id for a in current_assignments}

        new_membership_ids = set(membership_ids)
        to_add = new_membership_ids - current_membership_ids
        to_remove = current_membership_ids - new_membership_ids

        affected_user_ids = set()

        # Remove old assignments
        for membership_id in to_remove:
            membership = Membership.get_or_none(id=membership_id)
            if membership and membership.user_id:
                affected_user_ids.add(membership.user_id)

            MembershipAssignment.delete(
                (MembershipAssignment.access_role_id == role_id) & (MembershipAssignment.membership_id == membership_id)
            )

        # Add new assignments
        for membership_id in to_add:
            MembershipAssignment.create(
                MembershipAssignmentCreate(
                    access_role_id=role_id,
                    membership_id=membership_id,
                )
            )

            membership = Membership.get_or_none(id=membership_id)
            if membership and membership.user_id:
                affected_user_ids.add(membership.user_id)

        # Invalidate caches
        for user_id in affected_user_ids:
            self.permission_service.invalidate_permission_cache(user_id)

    def delete_membership_assignment(self, assignment_id: NanoIdType) -> None:
        """
        Delete a membership assignment.

        Args:
            assignment_id: The ID of the assignment to delete
        """
        assignment = MembershipAssignment.get_or_none(id=assignment_id)
        if assignment:
            membership = Membership.get_or_none(id=assignment.membership_id)
            user_id = membership.user_id if membership else None

            MembershipAssignment.delete(id=assignment_id)

            if user_id:
                self.permission_service.invalidate_permission_cache(user_id)

    def list_membership_assignments(
        self,
        customer_id: Optional[NanoIdType] = None,
        role_id: Optional[NanoIdType] = None,
        membership_id: Optional[NanoIdType] = None,
    ) -> list[MembershipAssignmentRead]:
        """
        List membership assignments with optional filters.

        Args:
            customer_id: Optional customer ID filter
            role_id: Optional role ID filter
            membership_id: Optional membership ID filter

        Returns:
            List of membership assignments matching the filters
        """
        filters = []

        if role_id:
            filters.append(MembershipAssignment.access_role_id == role_id)

        if membership_id:
            filters.append(MembershipAssignment.membership_id == membership_id)

        if filters:
            assignments = MembershipAssignment.list(*filters)
        else:
            assignments = MembershipAssignment.list()

        # If customer_id filter, we need to filter by memberships belonging to that customer
        if customer_id:
            customer_memberships = Membership.list(Membership.customer_id == customer_id)
            customer_membership_ids = {m.id for m in customer_memberships}
            assignments = [a for a in assignments if a.membership_id in customer_membership_ids]

        return assignments

    def get_membership_assignment_by_filter(self, filter_obj=None):
        """Get a membership assignment by filter."""
        if filter_obj:
            return MembershipAssignment.get_or_none(filter_obj)
        return None

    def list_staff_memberships_for_customer(self, customer_id: Optional[NanoIdType] = None) -> list[NanoIdType]:
        """
        List all staff membership IDs for a customer.

        Args:
            customer_id: Optional customer ID to filter by

        Returns:
            List of membership IDs that have staff role assigned
        """
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        if not staff_role:
            return []

        staff_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == staff_role.id)
        staff_membership_ids = [a.membership_id for a in staff_assignments]

        if customer_id:
            # Filter to memberships for this customer
            customer_memberships = Membership.list(
                (Membership.customer_id == customer_id) & (Membership.id.in_(staff_membership_ids))
            )
            return [m.id for m in customer_memberships]

        return staff_membership_ids
