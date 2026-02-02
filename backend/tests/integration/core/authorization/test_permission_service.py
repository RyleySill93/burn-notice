"""
Integration tests for the PermissionService.

These tests verify the core permission checking logic including check_permission,
list_permitted_ids, permission type hierarchy, deny overrides allow, wildcard
selectors, and staff access.
"""

from unittest.mock import MagicMock

import pytest

from src.app.projects import Project, ProjectCreate, ProjectPermissionHandler
from src.core.authorization import (
    STAFF_ROLE_NAME,
    AccessPolicy,
    AccessPolicyCreate,
    AccessRole,
    AccessRoleCreate,
    MembershipAssignment,
    MembershipAssignmentCreate,
    PermissionEffectEnum,
    PermissionService,
    PermissionTypeEnum,
    PolicyRoleAssignment,
    PolicyRoleAssignmentCreate,
    ResourceSelectorTypeEnum,
    ResourceTypeEnum,
)
from src.core.authorization.services import AccessControlService
from src.core.customer import Customer, CustomerCreate
from src.core.customer.permission_handler import CustomerPermissionHandler
from src.core.membership import Membership, MembershipCreate


@pytest.fixture
def permission_service():
    """Create a PermissionService instance with mocked cache."""
    mock_cache = MagicMock()
    mock_cache.get.return_value = None  # No cache hits by default

    service = PermissionService(
        membership_service=None,
        user_service=None,
        permission_handlers=[CustomerPermissionHandler(), ProjectPermissionHandler()],
        cache=mock_cache,
    )
    return service


@pytest.fixture
def staff_user_with_access(db, staff_user):
    """
    Create a staff user with a proper membership and staff role assignment.

    This fixture builds on the base staff_user fixture and adds the membership
    and role assignment needed for the user to actually have staff access.
    """
    # Create a system customer for staff
    staff_customer = Customer.get_or_none(Customer.name == 'Staff System Customer')
    if not staff_customer:
        staff_customer = Customer.create(CustomerCreate(name='Staff System Customer'))

    # Create membership
    Membership.create(MembershipCreate(user_id=staff_user.id, customer_id=staff_customer.id, is_active=True))

    # Grant staff admin access
    AccessControlService.factory().grant_staff_admin_access(staff_user.id)

    return staff_user


@pytest.fixture
def customer(db):
    """Create a test customer."""
    return Customer.create(CustomerCreate(name='Test Customer'))


@pytest.fixture
def second_customer(db):
    """Create a second test customer."""
    return Customer.create(CustomerCreate(name='Second Customer'))


@pytest.fixture
def project(db, customer):
    """Create a test project in the first customer."""
    return Project.create(ProjectCreate(name='Test Project', customer_id=customer.id))


@pytest.fixture
def second_project(db, customer):
    """Create a second project in the first customer."""
    return Project.create(ProjectCreate(name='Second Project', customer_id=customer.id))


@pytest.fixture
def project_in_second_customer(db, second_customer):
    """Create a project in the second customer."""
    return Project.create(ProjectCreate(name='Project in Second Customer', customer_id=second_customer.id))


@pytest.fixture
def setup_user_with_permissions(db, non_staff_user, customer):
    """Factory fixture to set up a user with specific permissions."""

    def _setup(policies: list[AccessPolicyCreate], customer_id: str = None):
        effective_customer_id = customer_id or customer.id

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=effective_customer_id, is_active=True)
        )

        # Create role
        role = AccessRole.create(AccessRoleCreate(name='TestRole', description='Test role for testing'))

        # Create policies and link to role
        for policy_create in policies:
            policy = AccessPolicy.create(policy_create)
            PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=role.id, policy_id=policy.id))

        # Assign role to membership
        MembershipAssignment.create(MembershipAssignmentCreate(membership_id=membership.id, access_role_id=role.id))

        return membership, role

    return _setup


class TestCheckPermissionBasic:
    """Basic tests for check_permission method."""

    def test_check_permission_no_rules_returns_false(self, db, non_staff_user, customer):
        """Without any permission rules, access should be denied."""
        # Create membership without any roles
        Membership.create(MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True))

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is False

    def test_check_permission_exact_allow_returns_true(self, db, non_staff_user, customer, setup_user_with_permissions):
        """With an exact ALLOW rule, access should be granted."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is True

    def test_check_permission_exact_deny_returns_false(self, db, non_staff_user, customer, setup_user_with_permissions):
        """With an exact DENY rule, access should be denied."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Deny Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.DENY,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is False

    def test_check_permission_different_resource_returns_false(
        self, db, non_staff_user, customer, second_customer, setup_user_with_permissions
    ):
        """Permission for one resource shouldn't grant access to another."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, second_customer.id
        )

        assert result is False


class TestPermissionTypeHierarchy:
    """Tests for permission type hierarchy (ADMIN -> WRITE -> READ)."""

    def test_admin_implies_write(self, db, non_staff_user, customer, setup_user_with_permissions):
        """ADMIN permission should imply WRITE access."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Admin Customer',
                    permission_type=PermissionTypeEnum.ADMIN,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.WRITE, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is True

    def test_admin_implies_read(self, db, non_staff_user, customer, setup_user_with_permissions):
        """ADMIN permission should imply READ access."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Admin Customer',
                    permission_type=PermissionTypeEnum.ADMIN,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is True

    def test_write_implies_read(self, db, non_staff_user, customer, setup_user_with_permissions):
        """WRITE permission should imply READ access."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Write Customer',
                    permission_type=PermissionTypeEnum.WRITE,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is True

    def test_write_does_not_imply_admin(self, db, non_staff_user, customer, setup_user_with_permissions):
        """WRITE permission should NOT imply ADMIN access."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Write Customer',
                    permission_type=PermissionTypeEnum.WRITE,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.ADMIN, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is False

    def test_read_does_not_imply_write(self, db, non_staff_user, customer, setup_user_with_permissions):
        """READ permission should NOT imply WRITE access."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.WRITE, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is False


class TestDenyOverridesAllow:
    """Tests for DENY override behavior."""

    def test_explicit_deny_overrides_explicit_allow_same_role(
        self, db, non_staff_user, customer, setup_user_with_permissions
    ):
        """Explicit DENY should override explicit ALLOW in the same role."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                ),
                AccessPolicyCreate(
                    name='Deny Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.DENY,
                ),
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is False

    def test_wildcard_deny_overrides_explicit_allow(self, db, non_staff_user, customer, setup_user_with_permissions):
        """Wildcard DENY should override explicit ALLOW."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                ),
                AccessPolicyCreate(
                    name='Deny All Customers',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                    effect=PermissionEffectEnum.DENY,
                ),
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is False

    def test_explicit_deny_overrides_wildcard_allow(self, db, non_staff_user, customer, setup_user_with_permissions):
        """Explicit DENY should override wildcard ALLOW."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow All Customers',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                    effect=PermissionEffectEnum.ALLOW,
                ),
                AccessPolicyCreate(
                    name='Deny Specific Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.DENY,
                ),
            ]
        )

        service = PermissionService.factory()
        result = service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id
        )

        assert result is False


class TestWildcardSelectors:
    """Tests for wildcard selector behavior."""

    def test_wildcard_allow_grants_access_to_all_resources(
        self, db, non_staff_user, customer, second_customer, setup_user_with_permissions
    ):
        """Wildcard ALLOW should grant access to all resources of that type."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow All Customers',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()

        assert (
            service.check_permission(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id)
            is True
        )
        assert (
            service.check_permission(
                non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, second_customer.id
            )
            is True
        )

    def test_wildcard_except_allow_excludes_specified(
        self, db, non_staff_user, customer, second_customer, setup_user_with_permissions
    ):
        """WILDCARD_EXCEPT ALLOW should exclude specified resources."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow All Except One',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': [customer.id]},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()

        assert (
            service.check_permission(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id)
            is False
        )
        assert (
            service.check_permission(
                non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, second_customer.id
            )
            is True
        )

    def test_multiple_selector_grants_specific_resources(
        self, db, non_staff_user, customer, second_customer, setup_user_with_permissions
    ):
        """MULTIPLE selector should grant access to only specified resources."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow Multiple Customers',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={
                        'type': ResourceSelectorTypeEnum.MULTIPLE,
                        'ids': [customer.id],  # Only includes first customer
                    },
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()

        assert (
            service.check_permission(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer.id)
            is True
        )
        assert (
            service.check_permission(
                non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, second_customer.id
            )
            is False
        )


class TestStaffAccess:
    """Tests for staff user access."""

    def test_is_staff_user_id_with_staff_role(self, db, staff_user_with_access):
        """User with Staff role should be identified as staff."""
        service = PermissionService.factory()
        result = service.is_staff_user_id(staff_user_with_access.id)

        assert result is True

    def test_is_staff_user_id_without_staff_role(self, db, non_staff_user, customer):
        """User without Staff role should not be identified as staff."""
        # Create a membership for the user
        Membership.create(MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True))

        service = PermissionService.factory()
        result = service.is_staff_user_id(non_staff_user.id)

        assert result is False

    def test_is_staff_user_id_with_inactive_membership(self, db, non_staff_user, customer):
        """Staff role through inactive membership should not grant staff access."""
        # Create inactive membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=False)
        )

        # Get or create Staff role
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        if not staff_role:
            staff_role = AccessRole.create(AccessRoleCreate(name=STAFF_ROLE_NAME, description='Staff'))

        # Assign staff role to inactive membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=staff_role.id)
        )

        service = PermissionService.factory()
        result = service.is_staff_user_id(non_staff_user.id)

        assert result is False


class TestListPermittedIdsBasic:
    """Basic tests for list_permitted_ids method."""

    def test_list_permitted_ids_no_permissions_returns_empty(self, db, non_staff_user, customer):
        """Without any permissions, should return empty set."""
        Membership.create(MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True))

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER)

        assert result == set()

    def test_list_permitted_ids_exact_allow_returns_single_id(
        self, db, non_staff_user, customer, setup_user_with_permissions
    ):
        """With exact ALLOW, should return only that ID."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER)

        assert customer.id in result

    def test_list_permitted_ids_wildcard_allow_returns_all_accessible(
        self, db, non_staff_user, customer, second_customer, setup_user_with_permissions
    ):
        """With wildcard ALLOW, should return all accessible resources."""
        # Create memberships for both customers
        Membership.create(MembershipCreate(user_id=non_staff_user.id, customer_id=second_customer.id, is_active=True))

        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow All Customers',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER)

        assert customer.id in result

    def test_list_permitted_ids_staff_returns_all(self, db, staff_user_with_access, customer, second_customer):
        """Staff user should get all resources."""
        service = PermissionService.factory()
        result = service.list_permitted_ids(
            staff_user_with_access.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER
        )

        assert customer.id in result
        assert second_customer.id in result


class TestListPermittedIdsWithDeny:
    """Tests for list_permitted_ids with DENY rules."""

    def test_list_permitted_ids_wildcard_deny_returns_empty(
        self, db, non_staff_user, customer, setup_user_with_permissions
    ):
        """With wildcard DENY, should return empty set."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Deny All Customers',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                    effect=PermissionEffectEnum.DENY,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER)

        assert result == set()

    def test_list_permitted_ids_wildcard_allow_with_exact_deny(
        self, db, non_staff_user, customer, second_customer, setup_user_with_permissions
    ):
        """Wildcard ALLOW with specific DENY should exclude the denied resource."""
        # Create membership for second customer too
        Membership.create(MembershipCreate(user_id=non_staff_user.id, customer_id=second_customer.id, is_active=True))

        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Allow All Customers',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                    effect=PermissionEffectEnum.ALLOW,
                ),
                AccessPolicyCreate(
                    name='Deny First Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.DENY,
                ),
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER)

        assert customer.id not in result
        assert second_customer.id in result


class TestListPermittedIdsHierarchy:
    """Tests for list_permitted_ids with permission type hierarchy."""

    def test_list_permitted_ids_read_includes_write_permissions(
        self, db, non_staff_user, customer, setup_user_with_permissions
    ):
        """READ request should include resources with WRITE permission."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Write Customer',
                    permission_type=PermissionTypeEnum.WRITE,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER)

        assert customer.id in result

    def test_list_permitted_ids_read_includes_admin_permissions(
        self, db, non_staff_user, customer, setup_user_with_permissions
    ):
        """READ request should include resources with ADMIN permission."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Admin Customer',
                    permission_type=PermissionTypeEnum.ADMIN,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER)

        assert customer.id in result


class TestListPermittedIdsProjects:
    """Tests for list_permitted_ids with hierarchical project permissions."""

    def test_list_permitted_ids_projects_via_customer_permission(
        self,
        db,
        non_staff_user,
        customer,
        project,
        second_project,
        project_in_second_customer,
        setup_user_with_permissions,
    ):
        """Customer READ should grant READ to all projects in that customer."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.PROJECT)

        assert project.id in result
        assert second_project.id in result
        assert project_in_second_customer.id not in result

    def test_list_permitted_ids_projects_specific_project_deny(
        self, db, non_staff_user, customer, project, second_project, setup_user_with_permissions
    ):
        """Project-specific DENY should exclude that project even with customer permission."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                ),
                AccessPolicyCreate(
                    name='Deny Project',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.PROJECT,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': project.id},
                    effect=PermissionEffectEnum.DENY,
                ),
            ]
        )

        service = PermissionService.factory()
        result = service.list_permitted_ids(non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.PROJECT)

        assert project.id not in result
        assert second_project.id in result


class TestHasCustomerAdminAccess:
    """Tests for has_customer_admin_access method."""

    def test_has_customer_admin_access_with_admin(self, db, non_staff_user, customer, setup_user_with_permissions):
        """User with ADMIN permission should have admin access."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Admin Customer',
                    permission_type=PermissionTypeEnum.ADMIN,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.has_customer_admin_access(non_staff_user.id, customer.id)

        assert result is True

    def test_has_customer_admin_access_with_read_only(self, db, non_staff_user, customer, setup_user_with_permissions):
        """User with only READ permission should NOT have admin access."""
        setup_user_with_permissions(
            [
                AccessPolicyCreate(
                    name='Read Customer',
                    permission_type=PermissionTypeEnum.READ,
                    resource_type=ResourceTypeEnum.CUSTOMER,
                    resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                    effect=PermissionEffectEnum.ALLOW,
                )
            ]
        )

        service = PermissionService.factory()
        result = service.has_customer_admin_access(non_staff_user.id, customer.id)

        assert result is False


class TestGetHandlerForResourceType:
    """Tests for get_handler_for_resource_type method."""

    def test_get_handler_for_customer(self, permission_service):
        """Should return CustomerPermissionHandler for CUSTOMER type."""
        handler = permission_service.get_handler_for_resource_type(ResourceTypeEnum.CUSTOMER)

        assert isinstance(handler, CustomerPermissionHandler)

    def test_get_handler_for_project(self, permission_service):
        """Should return ProjectPermissionHandler for PROJECT type."""
        handler = permission_service.get_handler_for_resource_type(ResourceTypeEnum.PROJECT)

        assert isinstance(handler, ProjectPermissionHandler)

    def test_get_handler_for_unknown_raises(self, permission_service):
        """Should raise ValueError for unknown resource type."""
        with pytest.raises(ValueError, match='No permission handler registered'):
            permission_service.get_handler_for_resource_type(ResourceTypeEnum.STAFF)


class TestListResourcesByType:
    """Tests for list_resources_by_type method."""

    def test_list_resources_by_type_customers(self, db, customer, second_customer):
        """Should list all customers."""
        service = PermissionService.factory()
        result = service.list_resources_by_type(ResourceTypeEnum.CUSTOMER.value, customer.id)

        # For customers, returns the customer itself
        assert len(result) == 1
        assert result[0]['id'] == customer.id

    def test_list_resources_by_type_projects(self, db, customer, project, second_project):
        """Should list all projects for the customer."""
        service = PermissionService.factory()
        result = service.list_resources_by_type(ResourceTypeEnum.PROJECT.value, customer.id)

        project_ids = [r['id'] for r in result]
        assert project.id in project_ids
        assert second_project.id in project_ids

    def test_list_resources_by_type_staff(self, db, customer):
        """Should return special staff entry."""
        service = PermissionService.factory()
        result = service.list_resources_by_type(ResourceTypeEnum.STAFF.value, customer.id)

        assert len(result) == 1
        assert result[0]['id'] == 'staff'

    def test_list_resources_by_type_invalid_raises(self, db, customer):
        """Should raise ValueError for invalid resource type."""
        service = PermissionService.factory()

        with pytest.raises(ValueError, match='Invalid resource type'):
            service.list_resources_by_type('invalid_type', customer.id)
