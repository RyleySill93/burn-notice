from typing import TYPE_CHECKING, Any, Dict, List

from src.common.nanoid import NanoIdType

if TYPE_CHECKING:
    from src.core.authentication import AuthenticatedUser

from src.core.authorization.constants import (
    STAFF_ROLE_NAME,
    SUPER_STAFF_ROLE_NAME,
    PermissionEffectEnum,
    PermissionTypeEnum,
    ResourceSelectorTypeEnum,
    ResourceTypeEnum,
)
from src.core.authorization.domains import (
    AccessPolicyRead,
    AuthorizedUser,
)
from src.core.authorization.models import AccessPolicy, AccessRole, MembershipAssignment, PolicyRoleAssignment
from src.core.authorization.permission_handler import PermissionHandler
from src.core.membership import Membership, MembershipService
from src.core.user import UserService
from src.network.cache.cache import Cache


class PermissionService:
    """
    Core service responsible for managing user permissions and authorization across the system.

    The PermissionService implements a comprehensive Role-Based Access Control (RBAC) system
    with hierarchical permissions, explicit deny rules, and resource-specific access controls.
    Key features include:

    - Permission inheritance through resource hierarchy (Customer → Resources)
    - Permission type cascading (ADMIN→WRITE→READ)
    - Explicit DENY rules that override any ALLOW rules
    - Support for staff-level access that bypasses normal permission checks
    """

    # Cache settings
    CACHE_KEY_PREFIX = 'authz::permission'
    # Cache key format constants
    PERMISSION_CHECK_FORMAT = '{prefix}:{user_id}:{permission_type}:{resource_type}:{resource_id}'
    PERMISSION_CHECK_PATTERN = '{prefix}:{user_id}:*'
    PERMITTED_IDS_FORMAT = '{prefix}::ids::{user_id}:{permission_type}:{resource_type}'
    PERMITTED_IDS_PATTERN = '{prefix}::ids::{user_id}:*'
    CACHE_TTL = 60 * 60 * 24  # 24 hours

    def __init__(
        self,
        membership_service: MembershipService,
        user_service: UserService,
        permission_handlers: List[PermissionHandler],
        cache=None,
    ):
        """
        Initialize the PermissionService with required dependencies.

        Args:
            membership_service: Service for managing memberships
            user_service: Service for managing user identities
            permission_handlers: List of permission handlers for each resource type
            cache: Cache instance for storing permission check results
        """
        self.membership_service = membership_service or MembershipService.factory()
        self.user_service = user_service or UserService.factory()
        self.cache = cache or Cache

        # Build a lookup map from resource type to handler for quick access
        self._handler_map: Dict[ResourceTypeEnum, PermissionHandler] = {
            handler.resource_type: handler for handler in permission_handlers
        }

    def get_handler_for_resource_type(self, resource_type: ResourceTypeEnum) -> PermissionHandler:
        """
        Get the permission handler for a specific resource type.

        Args:
            resource_type: The resource type to get the handler for

        Returns:
            The PermissionHandler for that resource type

        Raises:
            ValueError: If no handler is registered for the resource type
        """
        handler = self._handler_map.get(resource_type)
        if not handler:
            raise ValueError(f'No permission handler registered for resource type: {resource_type}')
        return handler

    @classmethod
    def factory(cls) -> 'PermissionService':
        """
        Create an instance of PermissionService with default dependencies.

        Returns:
            An instance of PermissionService
        """
        # Import here to avoid circular imports
        from src.app.projects import ProjectPermissionHandler
        from src.core.customer.permission_handler import CustomerPermissionHandler

        permission_handlers = [
            CustomerPermissionHandler(),
            ProjectPermissionHandler(),
        ]

        return cls(
            membership_service=MembershipService.factory(),
            user_service=UserService.factory(),
            permission_handlers=permission_handlers,
            cache=Cache,
        )

    def get_authz_user_authn_user(self, authn_user: 'AuthenticatedUser') -> AuthorizedUser:
        """
        Convert an authenticated user to an authorized user with permission scopes.

        This method enriches a basic authenticated user with their permission scopes,
        creating a fully authorized user that can be used for permission checks.

        Args:
            authn_user: The authenticated user from the authentication service

        Returns:
            An AuthorizedUser object with permission scopes attached
        """
        user_id = authn_user.id
        user = self.user_service.get_user_for_id(user_id=user_id)

        return AuthorizedUser(
            id=user_id,
            email=user.email,
            scopes=None,
            impersonator_id=authn_user.impersonator_id,
        )

    def get_auth_user_from_id(self, user_id: NanoIdType, impersonator_id: NanoIdType | None = None) -> AuthorizedUser:
        """
        Create an authorized user directly from a user ID.

        This method is useful for server-side operations where you have a user ID
        but not a full authenticated user object.

        Args:
            user_id: The ID of the user to authorize
            impersonator_id: Optional ID of a user who is impersonating this user

        Returns:
            An AuthorizedUser object with permission scopes attached
        """
        user = self.user_service.get_user_for_id(user_id=user_id)
        return AuthorizedUser(
            id=user_id,
            email=user.email,
            scopes=None,
            impersonator_id=impersonator_id,
        )

    def is_super_staff_user_id(self, user_id: NanoIdType) -> bool:
        """
        Check if a user has staff admin privileges.

        In the new RBAC system, this checks whether any of the user's active memberships
        are assigned to the global Staff role. Inactive memberships do not grant staff privileges.

        Args:
            user_id: The ID of the user to check

        Returns:
            True if the user has staff privileges, False otherwise
        """
        # First, get the Staff role ID
        staff_role = AccessRole.get_or_none(AccessRole.name == SUPER_STAFF_ROLE_NAME)
        if not staff_role:
            # If staff role doesn't exist, no one is a staff user
            return False

        # Get all active memberships for this user
        memberships = self.membership_service.list_memberships_for_user(user_id=user_id)
        active_membership_ids = [m.id for m in memberships if m.is_active]

        if not active_membership_ids:
            return False

        # Check if any of the user's active memberships are assigned to the Staff role
        assignment = MembershipAssignment.list(
            (MembershipAssignment.access_role_id == staff_role.id)
            & (MembershipAssignment.membership_id.in_(active_membership_ids))
        )

        return bool(assignment) is True

    def is_staff_user_id(self, user_id: NanoIdType) -> bool:
        """
        Check if a user has staff admin privileges.

        In the new RBAC system, this checks whether any of the user's active memberships
        are assigned to the global Staff role. Inactive memberships do not grant staff privileges.

        Args:
            user_id: The ID of the user to check

        Returns:
            True if the user has staff privileges, False otherwise
        """
        # First, get the Staff role ID
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        if not staff_role:
            # If staff role doesn't exist, no one is a staff user
            return False

        # Get all active memberships for this user
        memberships = self.membership_service.list_memberships_for_user(user_id=user_id)
        active_membership_ids = [m.id for m in memberships if m.is_active]

        if not active_membership_ids:
            return False

        # Check if any of the user's active memberships are assigned to the Staff role
        assignment = MembershipAssignment.list(
            (MembershipAssignment.access_role_id == staff_role.id)
            & (MembershipAssignment.membership_id.in_(active_membership_ids))
        )

        return bool(assignment) is True

    def has_customer_admin_access(self, user_id: NanoIdType, customer_id: NanoIdType) -> bool:
        """
        Check if a user has admin access to a specific customer.

        A user has admin access if they are either a staff user or
        have a role with admin permissions for the customer.

        Args:
            user_id: The ID of the user to check
            customer_id: The ID of the customer to check access for

        Returns:
            True if the user has admin access to the customer, False otherwise
        """
        return self.check_permission(user_id, PermissionTypeEnum.ADMIN, ResourceTypeEnum.CUSTOMER, customer_id)

    def list_permitted_ids(
        self,
        user_id: NanoIdType,
        permission_type: PermissionTypeEnum,
        resource_type: ResourceTypeEnum,
    ) -> set[NanoIdType]:
        """
        Return the set of resource IDs that the user has the specified permission for.

        This is the "bulk permission check" method that efficiently determines which resources
        a user can access without having to call check_permission() individually for each resource.
        It's primarily used for UI filtering (showing only accessible customers in dropdowns) and
        API query optimization (pre-filtering result sets).

        ## How It Works (The Algorithm)

        This method implements a multi-stage filtering pipeline that mirrors the same permission
        logic as check_permission() but operates on sets of resources for efficiency:

        ### Stage 1: Cache Check & Rule Loading
        - Checks if results are already cached (24-hour TTL)
        - Loads all permission rules for the user through their memberships
        - Short-circuits with "everything" if user has STAFF role

        ### Stage 2: Permission Level Expansion
        Due to hierarchical permissions (ADMIN → WRITE → READ), when checking for READ access,
        we must also check WRITE and ADMIN rules since both grant READ capabilities:

        - READ permission: Check READ + WRITE + ADMIN rules
        - WRITE permission: Check WRITE + ADMIN rules
        - ADMIN permission: Check only ADMIN rules

        ### Stage 3: Per-Permission-Level Processing
        For each applicable permission level (e.g., READ, WRITE, ADMIN for a READ request):

        #### 3a. Wildcard DENY Check
        If ANY rule says "DENY * [resource_type]", immediately return empty set.
        This implements the "explicit DENY always wins" security principle.

        #### 3b. Candidate Resource Collection
        Build the initial set of "maybe accessible" resources using two methods:

        **Method A: Wildcard ALLOW**
        If there's a "ALLOW * [resource_type]" rule, start with ALL resources the user
        could possibly access through their memberships (their "universe").

        **Method B: Explicit + Hierarchical ALLOW**
        Otherwise, collect resources from:
        - Explicit rules: "ALLOW [specific_resource_id]"
        - Hierarchical rules: "ALLOW [customer_id]" grants access to all resources in that customer

        #### 3c. Permission Model Filtering
        Take the candidate resources and apply the full permission model to each one.
        This is the most complex part and mirrors check_permission() logic:

        For each candidate resource:
        1. **Explicit DENY at resource level**: If there's a DENY rule specifically for this
           resource, exclude it (DENY always wins)
        2. **Explicit ALLOW at resource level**: If there's an ALLOW rule specifically for
           this resource, include it (explicit beats hierarchical)
        3. **Hierarchical DENY check**: Check if any parent resource (customer) has
           a DENY rule that would block access to this resource
        4. **Hierarchical ALLOW**: If the resource was in candidates (meaning it was allowed
           hierarchically) and not denied at any level, include it

        ### Stage 4: Result Aggregation
        Combine results from all permission levels (READ + WRITE + ADMIN for a READ check)
        and cache the final set.

        ## Key Design Principles Implemented

        1. **Deny-by-default**: Resources are only included if explicitly or hierarchically allowed
        2. **DENY always wins**: Any DENY rule at any level excludes the resource
        3. **Hierarchical inheritance**: Customer permissions cascade to child resources
        4. **Specificity precedence**: Explicit resource rules override hierarchical rules
        5. **Permission level cascading**: Higher permissions (ADMIN) grant lower ones (READ)

        ## Performance Optimizations

        - **Caching**: Results cached for 24 hours per user/permission/resource_type combination
        - **Batch loading**: Loads all user rules once, then applies to entire resource set
        - **Efficient filtering**: Uses database IN queries and set operations rather than loops
        - **Early termination**: Wildcard DENY immediately returns empty set

        ## Example Scenarios

        **Scenario 1**: User has "WRITE customer_123" permission, requesting READ resources
        1. Expands to check WRITE + ADMIN rules for READ request
        2. Finds "ALLOW customer_123" WRITE rule
        3. Collects all resources in customer_123 as candidates
        4. Filters each resource: no explicit DENY rules, so all are permitted
        5. Returns all resource IDs in customer_123

        **Scenario 2**: User has "READ *" but "DENY customer_456", requesting READ customers
        1. Finds wildcard ALLOW, so candidates = all customers in user's universe
        2. Filters each customer: customer_456 has explicit DENY, so it's excluded
        3. Returns all customer IDs except customer_456

        **Scenario 3**: User has "ADMIN customer_789", requesting WRITE on customer
        1. Expands to check WRITE + ADMIN rules for WRITE request
        2. Finds "ALLOW customer_789" ADMIN rule
        3. Collects customer_789 as candidate
        4. Filters: no DENY rules, so customer_789 is permitted
        5. Returns customer_789
        """
        # Check cache first
        cache_key = self.PERMITTED_IDS_FORMAT.format(
            prefix=self.CACHE_KEY_PREFIX,
            user_id=user_id,
            permission_type=permission_type.value,
            resource_type=resource_type.value,
        )
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            if cached == '[]':
                return set()
            else:
                ids_str = cached.strip('[]').split(',')
                return set(id_str.strip(' \'"') for id_str in ids_str if id_str.strip())

        # Get all permission rules for this user
        memberships = self.membership_service.list_memberships_for_user(user_id)
        membership_ids = [member.id for member in memberships]

        # First check if user is a staff member - staff should have access to all resources
        if self.is_staff_user_id(user_id):
            permitted_ids = self._get_all_resource_ids_for_type(resource_type)
            self._set_to_cache(cache_key, str(list(permitted_ids)))
            return permitted_ids

        access_role_ids = self._get_access_role_ids_for_memberships(membership_ids)
        rules = self._get_rules_from_access_roles(access_role_ids)

        # Build the universe of resources based on memberships
        membership_customer_ids = [m.customer_id for m in memberships if m.customer_id]

        # Initialize result sets
        permitted_ids = set()

        # Determine which permission levels to check
        if permission_type == PermissionTypeEnum.READ:
            permission_types_to_check = [PermissionTypeEnum.READ, PermissionTypeEnum.WRITE, PermissionTypeEnum.ADMIN]
        elif permission_type == PermissionTypeEnum.WRITE:
            permission_types_to_check = [PermissionTypeEnum.WRITE, PermissionTypeEnum.ADMIN]
        else:  # ADMIN
            permission_types_to_check = [PermissionTypeEnum.ADMIN]

        # Process each permission level
        for perm_type in permission_types_to_check:
            # Extract rules for this permission type
            perm_rules = [r for r in rules if r.permission_type == perm_type]

            # Check for wildcard DENY first
            wildcard_deny_rule = next(
                (
                    rule
                    for rule in perm_rules
                    if rule.resource_type == resource_type
                    and rule.effect == PermissionEffectEnum.DENY
                    and rule.resource_selector.get('type') == ResourceSelectorTypeEnum.WILDCARD
                ),
                None,
            )
            if wildcard_deny_rule:
                self._set_to_cache(cache_key, '[]')
                return set()

            # Check for wildcard_except DENY (deny all except specified)
            wildcard_except_deny_rules = [
                rule
                for rule in perm_rules
                if rule.resource_type == resource_type
                and rule.effect == PermissionEffectEnum.DENY
                and rule.resource_selector.get('type') == ResourceSelectorTypeEnum.WILDCARD_EXCEPT
            ]
            if wildcard_except_deny_rules:
                # Get the universe, then exclude the allowed IDs from all deny rules
                universe = self._get_universe_for_resource_type(resource_type, set(membership_customer_ids))
                allowed_ids = set()
                for rule in wildcard_except_deny_rules:
                    excluded_ids = rule.resource_selector.get('excluded_ids', [])
                    allowed_ids.update(excluded_ids)
                # Only the excluded IDs are allowed (everything else is denied) FOR THIS PERMISSION LEVEL
                # Add to permitted_ids for this permission level and continue to check other permission levels
                permitted_ids.update(allowed_ids & universe)
                continue

            # Check for wildcard ALLOW
            has_wildcard_allow = any(
                rule.resource_type == resource_type
                and rule.effect == PermissionEffectEnum.ALLOW
                and rule.resource_selector.get('type') == ResourceSelectorTypeEnum.WILDCARD
                for rule in perm_rules
            )

            # Check for wildcard_except ALLOW (allow all except specified)
            wildcard_except_allow_rules = [
                rule
                for rule in perm_rules
                if rule.resource_type == resource_type
                and rule.effect == PermissionEffectEnum.ALLOW
                and rule.resource_selector.get('type') == ResourceSelectorTypeEnum.WILDCARD_EXCEPT
            ]

            # Get candidate resources
            if has_wildcard_allow or wildcard_except_allow_rules:
                # Start with full universe
                candidate_ids = self._get_universe_for_resource_type(resource_type, set(membership_customer_ids))
                # For wildcard_except ALLOW, remove the excluded IDs
                if wildcard_except_allow_rules and not has_wildcard_allow:
                    # Remove excluded IDs from all wildcard_except rules
                    for rule in wildcard_except_allow_rules:
                        excluded_ids = set(rule.resource_selector.get('excluded_ids', []))
                        candidate_ids -= excluded_ids
            else:
                # Collect explicitly allowed resources
                candidate_ids = set()
                for rule in perm_rules:
                    if rule.resource_type == resource_type and rule.effect == PermissionEffectEnum.ALLOW:
                        candidate_ids.update(self._extract_resource_ids_from_rule(rule))

                # Add hierarchically allowed resources
                candidate_ids.update(self._get_hierarchical_permissions(resource_type, perm_rules, perm_type))

            # Now filter candidates based on the full permission model
            # This is where we properly handle hierarchical DENY
            level_permitted_ids = self._filter_by_permission_model(candidate_ids, perm_rules, perm_type, resource_type)

            permitted_ids.update(level_permitted_ids)

        # Cache and return the result
        self._set_to_cache(cache_key, str(list(permitted_ids)))
        return permitted_ids

    def _filter_by_permission_model(
        self,
        candidate_ids: set[NanoIdType],
        rules: list,
        permission_type: PermissionTypeEnum,
        resource_type: ResourceTypeEnum,
    ) -> set[NanoIdType]:
        """
        Filter candidate resources based on the full permission model.

        Delegates to the appropriate permission handler.
        """
        handler = self.get_handler_for_resource_type(resource_type)
        return handler.filter_by_permission_model(candidate_ids, rules, permission_type)

    def _extract_resource_ids_from_rule(self, rule) -> set[NanoIdType]:
        selector_type = rule.resource_selector.get('type')

        if selector_type == ResourceSelectorTypeEnum.EXACT:
            resource_id = rule.resource_selector.get('id')
            return {resource_id} if resource_id else set()

        elif selector_type == ResourceSelectorTypeEnum.MULTIPLE:
            return set(rule.resource_selector.get('ids', []))

        elif selector_type == ResourceSelectorTypeEnum.WILDCARD:
            # Wildcard doesn't have specific IDs
            return set()

        elif selector_type == ResourceSelectorTypeEnum.WILDCARD_EXCEPT:
            # Wildcard_except is handled specially in list_permitted_ids
            # For explicit allow/deny tracking, we don't return the excluded IDs
            # because the logic is inverted (wildcard_except affects everything EXCEPT these)
            return set()

        return set()

    def _get_all_resource_ids_for_type(self, resource_type: ResourceTypeEnum) -> set[NanoIdType]:
        """
        Get all resource IDs of a given type - used for staff access.

        Delegates to the appropriate permission handler.
        """
        handler = self.get_handler_for_resource_type(resource_type)
        return handler.get_all_resource_ids()

    def _get_universe_for_resource_type(
        self, resource_type: ResourceTypeEnum, parent_resource_ids: set[NanoIdType]
    ) -> set[NanoIdType]:
        """
        Get the universe of resources accessible given parent resource IDs.

        Delegates to the appropriate permission handler.
        """
        handler = self.get_handler_for_resource_type(resource_type)
        return handler.get_universe(parent_resource_ids)

    def _get_hierarchical_permissions(
        self,
        resource_type: ResourceTypeEnum,
        rules: list,
        permission_type: PermissionTypeEnum,
        parent_resource_ids: set[NanoIdType] = None,
    ) -> set[NanoIdType]:
        """
        Get resource IDs through hierarchical permissions.

        Delegates to the appropriate permission handler.
        """
        handler = self.get_handler_for_resource_type(resource_type)
        return handler.get_hierarchical_resource_ids(rules, permission_type, parent_resource_ids)

    def check_permission(
        self,
        user_id: NanoIdType,
        permission_type: PermissionTypeEnum,
        resource_type: ResourceTypeEnum,
        resource_id: NanoIdType = None,
    ) -> bool:
        """
        Core permission verification method that implements our RBAC permission model.

        This method is the central authority for all authorization checks in the system,
        providing a consistent way to verify permissions across all resources. It implements
        several key permission design principles:

        1. Deny by default: Access is denied unless explicitly allowed by an ALLOW rule.
           This implements the principle of least privilege.

        2. Rule precedence: Explicit DENY rules always override any ALLOW rules,
           creating a strong security model where restrictions can be enforced
           regardless of other permissions.

        3. Specificity precedence: More specific rules override more general ones,
           allowing targeted permission adjustments without disrupting broader access.

        4. Admin implies write and read: Users with ADMIN access automatically have WRITE
           and READ access, creating a clear hierarchy of permission levels.

        5. Write implies read: Users with WRITE access automatically have READ access,
           simplifying permission management and matching intuitive user expectations.

        ### Resource and Feature Selector Interaction

        Short circuit if user has staff resource role - that grants all access.

        The check_permission method evaluates permissions at multiple levels:
        1. It applies the "ADMIN implies WRITE implies READ" principle for permission type
        2. It evaluates explicit DENY rules at the exact resource level
        3. It checks for explicit ALLOW rules at the exact resource level
        4. Finally, it evaluates hierarchical permissions up the resource tree

        This layered evaluation ensures that the most specific and relevant permissions
        are applied first, with broader permissions serving as fallbacks.

        Args:
            user_id: The ID of the user requesting access
            permission_type: The type of permission being requested (READ, WRITE, or ADMIN)
            resource_type: The type of resource being accessed (CUSTOMER or STAFF)
            resource_id: The ID of the specific resource being accessed

        Returns:
            True if the user has the requested permission, False otherwise
        """
        # Check cache for previously computed result
        cache_key = self._get_permission_cache_key(user_id, permission_type, resource_type, resource_id)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        # Admin implies write
        if permission_type == PermissionTypeEnum.WRITE:
            admin_permission = self.check_permission(user_id, PermissionTypeEnum.ADMIN, resource_type, resource_id)
            if admin_permission:
                return True

        # Write implies read
        if permission_type == PermissionTypeEnum.READ:
            write_permission = self.check_permission(user_id, PermissionTypeEnum.WRITE, resource_type, resource_id)
            if write_permission:
                return True

        # Get all permission sets assigned to this user
        memberships = self.membership_service.list_memberships_for_user(user_id)
        membership_ids = [member.id for member in memberships]
        access_role_ids = self._get_access_role_ids_for_memberships(membership_ids)
        rules = self._get_rules_from_access_roles(access_role_ids)
        staff_policy = [policy for policy in rules if policy.resource_type == ResourceTypeEnum.STAFF]
        if staff_policy:
            self._set_to_cache(cache_key, True)
            return True
        # Delegate to the handler for permission checking
        # The handler's has_hierarchical_permission handles deny/allow checks and hierarchical inheritance
        handler = self.get_handler_for_resource_type(resource_type)
        result = handler.has_hierarchical_permission(rules, permission_type, resource_id)
        self._set_to_cache(cache_key, result)
        return result

    def _get_access_role_ids_for_memberships(self, membership_ids: list[NanoIdType]) -> list[NanoIdType]:
        """
        Get all access role IDs assigned to the given memberships.

        This method retrieves all access roles that are assigned to any of the
        provided membership IDs, which is a key step in determining what permissions
        a user has through their memberships.

        Args:
            membership_ids: List of membership IDs to get access roles for

        Returns:
            List of access role IDs
        """
        if not membership_ids:
            return []

        # Query all membership assignments for the given membership IDs
        query_result = (
            MembershipAssignment.get_query()
            .filter(MembershipAssignment.membership_id.in_(membership_ids))
            .with_entities(MembershipAssignment.access_role_id)
            .all()
        )

        # Extract the access role IDs from the query result
        access_role_ids = [result[0] for result in query_result]

        return access_role_ids

    def _get_rules_from_access_roles(self, access_role_ids: list[NanoIdType]) -> list[AccessPolicyRead]:
        """
        Get all permission rules associated with the given access roles.

        This method retrieves all permission rules that are part of any of the
        provided access role IDs, which is essential for evaluating what actions
        a user is allowed to perform.

        Args:
            access_role_ids: List of access role IDs to get rules from

        Returns:
            List of AccessPolicy objects
        """
        if not access_role_ids:
            return []

        # Query policies through the PolicyRoleAssignment join table instead of direct FK

        rules_query = (
            AccessPolicy.get_query()
            .join(PolicyRoleAssignment, AccessPolicy.id == PolicyRoleAssignment.policy_id)
            .filter(PolicyRoleAssignment.role_id.in_(access_role_ids))
            .all()
        )

        return rules_query

    # ==================== Cache Methods ====================

    def _get_permission_cache_key(
        self,
        user_id: NanoIdType,
        permission_type: PermissionTypeEnum,
        resource_type: ResourceTypeEnum,
        resource_id: NanoIdType = None,
    ) -> str:
        """Get a standardized cache key for storing permission check results."""
        return self.PERMISSION_CHECK_FORMAT.format(
            prefix=self.CACHE_KEY_PREFIX,
            user_id=user_id,
            permission_type=permission_type.value,
            resource_type=resource_type.value,
            resource_id=resource_id or 'all',
        )

    def _get_from_cache(self, key: str) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            value = self.cache.get(key)
            # Convert string representations of booleans back to actual booleans
            if value == 'True':
                return True
            elif value == 'False':
                return False
            return value
        except Exception:
            return None

    def _set_to_cache(self, key: str, value: Any) -> None:
        """
        Set a value in the cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
        """
        try:
            # Convert boolean values to strings before storing in Redis
            if isinstance(value, bool):
                value = str(value)
            self.cache.setex(key, self.CACHE_TTL, value)
        except Exception:
            # Log error or handle exception as needed
            pass

    def invalidate_permission_cache(self, user_id: NanoIdType) -> None:
        """
        Invalidate cached permissions for a user.

        This should be called whenever a user's permissions change, such as when
        memberships or roles are updated. This method explicitly invalidates all
        permission cache patterns used by both list_permitted_ids and check_permission.
        """
        try:
            # Define patterns for both cache types
            patterns = [
                self.PERMISSION_CHECK_PATTERN.format(prefix=self.CACHE_KEY_PREFIX, user_id=user_id),
                self.PERMITTED_IDS_PATTERN.format(prefix=self.CACHE_KEY_PREFIX, user_id=user_id),
            ]

            # Delete all cache keys for each pattern
            for pattern in patterns:
                # Get all keys matching the pattern
                keys = self.cache.keys(pattern)

                # Delete all matching keys
                if keys:
                    self.cache.delete(*keys)
        except Exception:
            # Log error or handle exception as needed
            pass

    def invalidate_customer_member_user_cache(self, customer_id: NanoIdType) -> None:
        """
        Invalidate cached permissions for all users associated with a customer.

        This should be called whenever a customer-wide change occurs that might affect
        permissions for users within that customer, such as when permissions change
        or when access policies change at the customer level.
        """
        # Get all memberships for the customer
        memberships = self.membership_service.list_memberships_for_customer(customer_id=customer_id)

        # Get user IDs from memberships
        user_ids = {membership.user_id for membership in memberships}

        # Get staff role
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        if staff_role:
            # Find all memberships assigned to the staff role
            staff_assignments = MembershipAssignment.list(MembershipAssignment.access_role_id == staff_role.id)
            staff_membership_ids = {assignment.membership_id for assignment in staff_assignments}

            # Get the actual membership objects to get user IDs
            if staff_membership_ids:
                staff_memberships = Membership.list(Membership.id.in_(staff_membership_ids))
                staff_user_ids = {membership.user_id for membership in staff_memberships}

                # Add staff users to the set of users to invalidate
                user_ids.update(staff_user_ids)

        # Invalidate cache for each user
        for user_id in user_ids:
            self.invalidate_permission_cache(user_id)

    # ==================== Resource Query Methods ====================

    def list_resources_by_type(self, resource_type: str, customer_id: NanoIdType) -> list[dict]:
        """
        List all resources of a specific type for a customer.

        This method fetches resources that can be used in policy resource selectors.
        The response format includes id and name properties for each resource.

        Args:
            resource_type: The type of resources to fetch (from ResourceTypeEnum)
            customer_id: The customer ID to get resources for

        Returns:
            List of resources with id and name attributes
        """
        # Validate resource type
        if resource_type not in [r.value for r in ResourceTypeEnum]:
            raise ValueError(f'Invalid resource type: {resource_type}')

        # Special handling for STAFF resource type (no handler needed)
        if resource_type == ResourceTypeEnum.STAFF.value:
            return [{'id': 'staff', 'name': 'All Staff Members'}]

        # Convert string to enum and delegate to handler
        resource_type_enum = ResourceTypeEnum(resource_type)
        handler = self.get_handler_for_resource_type(resource_type_enum)
        return handler.list_resources_for_customer(customer_id)
