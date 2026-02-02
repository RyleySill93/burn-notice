"""
Integration tests for the ProjectPermissionHandler.

These tests verify the project-level permission handling logic including
hierarchical permission inheritance from customers, universe determination,
and resource filtering.
"""

import pytest

from src.app.projects import Project, ProjectCreate, ProjectPermissionHandler
from src.core.authorization import (
    AccessPolicy,
    AccessPolicyCreate,
    AccessRole,
    AccessRoleCreate,
    MembershipAssignment,
    MembershipAssignmentCreate,
    PermissionEffectEnum,
    PermissionTypeEnum,
    PolicyRoleAssignment,
    PolicyRoleAssignmentCreate,
    ResourceSelectorTypeEnum,
    ResourceTypeEnum,
)
from src.core.customer import Customer, CustomerCreate
from src.core.membership import Membership, MembershipCreate


@pytest.fixture
def handler():
    """Create a ProjectPermissionHandler instance."""
    return ProjectPermissionHandler()


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


def make_policy_read(
    permission_type: PermissionTypeEnum,
    resource_type: ResourceTypeEnum,
    effect: PermissionEffectEnum,
    selector: dict,
    customer_id: str = None,
):
    """Helper to create an AccessPolicyRead-like object for testing."""
    from src.core.authorization.domains import AccessPolicyRead

    return AccessPolicyRead(
        id='test_policy',
        name='Test Policy',
        permission_type=permission_type,
        resource_type=resource_type,
        resource_selector=selector,
        effect=effect,
        customer_id=customer_id,
    )


class TestProjectGetUniverse:
    """Tests for get_universe method."""

    def test_get_universe_returns_projects_for_customers(self, handler, customer, project, second_project):
        """Universe should include all projects belonging to the given customer IDs."""
        parent_customer_ids = {customer.id}

        result = handler.get_universe(parent_customer_ids)

        assert project.id in result
        assert second_project.id in result

    def test_get_universe_empty_customer_ids_returns_empty(self, handler):
        """Empty customer IDs should return empty universe."""
        result = handler.get_universe(set())

        assert result == set()

    def test_get_universe_multiple_customers_returns_all_projects(
        self, handler, customer, second_customer, project, second_project, project_in_second_customer
    ):
        """Universe should include projects from all specified customers."""
        parent_customer_ids = {customer.id, second_customer.id}

        result = handler.get_universe(parent_customer_ids)

        assert project.id in result
        assert second_project.id in result
        assert project_in_second_customer.id in result


class TestProjectGetHierarchicalResourceIds:
    """Tests for get_hierarchical_resource_ids method."""

    def test_get_hierarchical_resource_ids_from_project_rules(self, handler, project, second_project):
        """Should extract project IDs directly from project-level ALLOW rules."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.PROJECT,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': project.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert project.id in result
        assert second_project.id not in result

    def test_get_hierarchical_resource_ids_from_customer_rules(
        self, handler, customer, project, second_project, project_in_second_customer
    ):
        """Should include all projects when customer-level READ rule exists."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert project.id in result
        assert second_project.id in result
        assert project_in_second_customer.id not in result

    def test_get_hierarchical_resource_ids_customer_admin_implies_project_read(
        self, handler, customer, project, second_project
    ):
        """Customer ADMIN permission should grant READ access to projects."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.ADMIN,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert project.id in result
        assert second_project.id in result

    def test_get_hierarchical_resource_ids_customer_write_implies_project_read(
        self, handler, customer, project, second_project
    ):
        """Customer WRITE permission should grant READ access to projects."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.WRITE,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert project.id in result
        assert second_project.id in result

    def test_get_hierarchical_resource_ids_write_request_checks_admin(self, handler, customer, project):
        """When requesting WRITE, should check WRITE and ADMIN customer rules."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.ADMIN,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.WRITE)

        assert project.id in result

    def test_get_hierarchical_resource_ids_admin_request_only_checks_admin(self, handler, customer, project):
        """When requesting ADMIN, should only check ADMIN customer rules."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.WRITE,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.ADMIN)

        # WRITE doesn't imply ADMIN, so the project shouldn't be included
        assert project.id not in result


class TestProjectHasHierarchicalPermission:
    """Tests for _has_hierarchical_permission method (via has_hierarchical_permission)."""

    def test_has_hierarchical_permission_via_customer_allow(self, handler, customer, project):
        """Permission should be granted via customer-level ALLOW rule."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project.id)

        assert result is True

    def test_has_hierarchical_permission_no_customer_rule(self, handler, customer, project):
        """Without any matching rules, permission should be denied."""
        rules = []

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project.id)

        assert result is False

    def test_has_hierarchical_permission_different_customer(
        self, handler, customer, second_customer, project_in_second_customer
    ):
        """Permission for one customer shouldn't grant access to another's projects."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project_in_second_customer.id)

        assert result is False

    def test_has_hierarchical_permission_project_not_found(self, handler, customer):
        """Should return False for non-existent project."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, 'nonexistent_project_id')

        assert result is False

    def test_has_hierarchical_permission_wildcard_customer_allows(
        self, handler, customer, project, project_in_second_customer
    ):
        """Wildcard customer rule should grant access to all projects."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.WILDCARD},
            ),
        ]

        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project.id) is True
        assert (
            handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project_in_second_customer.id) is True
        )


class TestProjectFilterByPermissionModel:
    """Tests for filter_by_permission_model method."""

    def test_filter_by_permission_model_explicit_project_deny(self, handler, project, second_project):
        """Explicit project DENY should filter out the denied project."""
        candidate_ids = {project.id, second_project.id}
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.PROJECT,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': project.id},
            ),
        ]

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        assert project.id not in result
        assert second_project.id in result

    def test_filter_by_permission_model_inherited_from_customer(self, handler, project, second_project):
        """Candidates from customer inheritance should pass if not explicitly denied."""
        candidate_ids = {project.id, second_project.id}
        rules = []  # No project-level rules

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        # Without explicit deny, candidates pass through
        assert project.id in result
        assert second_project.id in result


class TestProjectListResourcesForCustomer:
    """Tests for list_resources_for_customer method."""

    def test_list_resources_for_customer_returns_projects(self, handler, customer, project, second_project):
        """Should return all projects for the given customer."""
        result = handler.list_resources_for_customer(customer.id)

        project_ids = [r['id'] for r in result]
        assert project.id in project_ids
        assert second_project.id in project_ids

    def test_list_resources_for_customer_only_that_customer(
        self, handler, customer, project, project_in_second_customer
    ):
        """Should only return projects for the specified customer."""
        result = handler.list_resources_for_customer(customer.id)

        project_ids = [r['id'] for r in result]
        assert project.id in project_ids
        assert project_in_second_customer.id not in project_ids


class TestProjectResourceType:
    """Tests for resource_type property."""

    def test_resource_type_is_project(self, handler):
        """Handler should report PROJECT as its resource type."""
        assert handler.resource_type == ResourceTypeEnum.PROJECT


class TestProjectIntegrationWithPermissions:
    """
    Integration tests that verify ProjectPermissionHandler works correctly
    with actual database records for permissions.
    """

    def test_full_permission_flow_with_customer_level_access(
        self, db, handler, non_staff_user, customer, project, second_project, project_in_second_customer
    ):
        """
        Test that customer-level READ permission grants access to all projects in that customer.
        """
        # Create membership for user
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create a role with READ permission to customer
        role = AccessRole.create(AccessRoleCreate(name='Customer Reader', description='Read customer'))

        # Create policy granting READ to customer
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Read Customer Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link policy to role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=role.id, policy_id=policy.id))

        # Assign role to membership
        MembershipAssignment.create(MembershipAssignmentCreate(membership_id=membership.id, access_role_id=role.id))

        # Test the handler with the actual policy
        rules = [policy]

        # Should have permission to projects in the customer
        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project.id) is True
        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, second_project.id) is True

        # Should NOT have permission to projects in other customers
        assert (
            handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project_in_second_customer.id) is False
        )

    def test_project_deny_overrides_customer_allow(
        self, db, handler, non_staff_user, customer, project, second_project
    ):
        """Test that project-level DENY overrides customer-level ALLOW."""
        # Create membership for user
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create a role
        role = AccessRole.create(AccessRoleCreate(name='Mixed Access', description='Has both allow and deny'))

        # Create ALLOW policy for customer
        allow_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Allow Customer Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Create DENY policy for specific project
        deny_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Deny Project Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.PROJECT,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': project.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link both policies to role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=role.id, policy_id=allow_policy.id))
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=role.id, policy_id=deny_policy.id))

        # Assign role to membership
        MembershipAssignment.create(MembershipAssignmentCreate(membership_id=membership.id, access_role_id=role.id))

        # Test with both policies - project DENY should override customer ALLOW
        rules = [allow_policy, deny_policy]

        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project.id) is False
        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, second_project.id) is True

    def test_project_specific_allow(self, db, handler, non_staff_user, customer, project, second_project):
        """Test that project-specific ALLOW grants access to just that project."""
        # Create membership for user
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create a role
        role = AccessRole.create(AccessRoleCreate(name='Project Specific', description='Access to one project'))

        # Create ALLOW policy for specific project only (no customer access)
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Allow Project Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.PROJECT,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': project.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link policy to role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=role.id, policy_id=policy.id))

        # Assign role to membership
        MembershipAssignment.create(MembershipAssignmentCreate(membership_id=membership.id, access_role_id=role.id))

        # Test with just the project policy
        rules = [policy]

        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, project.id) is True
        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, second_project.id) is False
