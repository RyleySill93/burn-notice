"""
Integration tests for the CustomerPermissionHandler.

These tests verify the customer-level permission handling logic including
universe determination, hierarchical permissions, and resource filtering.
"""

import pytest

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
from src.core.customer.permission_handler import CustomerPermissionHandler
from src.core.membership import Membership, MembershipCreate


@pytest.fixture
def handler():
    """Create a CustomerPermissionHandler instance."""
    return CustomerPermissionHandler()


@pytest.fixture
def customer(db):
    """Create a test customer."""
    return Customer.create(CustomerCreate(name='Test Customer'))


@pytest.fixture
def second_customer(db):
    """Create a second test customer."""
    return Customer.create(CustomerCreate(name='Second Customer'))


@pytest.fixture
def third_customer(db):
    """Create a third test customer."""
    return Customer.create(CustomerCreate(name='Third Customer'))


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


class TestCustomerGetUniverse:
    """Tests for get_universe method."""

    def test_get_universe_returns_parent_resource_ids(self, handler, customer, second_customer):
        """Universe should be the same as parent resource IDs for customers."""
        parent_ids = {customer.id, second_customer.id}

        result = handler.get_universe(parent_ids)

        assert result == parent_ids

    def test_get_universe_empty_returns_empty(self, handler):
        """Empty parent IDs should return empty universe."""
        result = handler.get_universe(set())

        assert result == set()

    def test_get_universe_none_returns_empty(self, handler):
        """None parent IDs should return empty universe."""
        result = handler.get_universe(None)

        assert result == set()


class TestCustomerGetAllResourceIds:
    """Tests for get_all_resource_ids method."""

    def test_get_all_resource_ids_returns_all_customers(self, handler, customer, second_customer, third_customer):
        """Should return all customer IDs in the system."""
        result = handler.get_all_resource_ids()

        assert customer.id in result
        assert second_customer.id in result
        assert third_customer.id in result


class TestCustomerGetHierarchicalResourceIds:
    """Tests for get_hierarchical_resource_ids method."""

    def test_get_hierarchical_resource_ids_extracts_from_allow_rules(self, handler, customer, second_customer):
        """Should extract customer IDs from ALLOW rules."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': second_customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert customer.id in result
        assert second_customer.id in result

    def test_get_hierarchical_resource_ids_ignores_deny_rules(self, handler, customer, second_customer):
        """Should not extract IDs from DENY rules."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': second_customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert customer.id in result
        assert second_customer.id not in result

    def test_get_hierarchical_resource_ids_ignores_other_resource_types(self, handler, customer):
        """Should ignore rules for other resource types."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.PROJECT,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert result == set()

    def test_get_hierarchical_resource_ids_multiple_selector(self, handler, customer, second_customer, third_customer):
        """Should extract multiple IDs from MULTIPLE selector."""
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.MULTIPLE, 'ids': [customer.id, second_customer.id]},
            ),
        ]

        result = handler.get_hierarchical_resource_ids(rules, PermissionTypeEnum.READ)

        assert customer.id in result
        assert second_customer.id in result
        assert third_customer.id not in result


class TestCustomerHasHierarchicalPermission:
    """Tests for _has_hierarchical_permission method (via has_hierarchical_permission)."""

    def test_has_hierarchical_permission_always_false_for_customer(self, handler, customer):
        """
        Customers are root level - no hierarchical inheritance from parents.

        Even with customer-level rules, the _has_hierarchical_permission
        method returns False because there's no parent to inherit from.
        The permission is granted by explicit rules, not hierarchy.
        """
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        # has_hierarchical_permission checks explicit rules first, then hierarchy
        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, customer.id)

        # Should be True because of explicit ALLOW, not hierarchy
        assert result is True

    def test_has_hierarchical_permission_no_rules_returns_false(self, handler, customer):
        """With no rules, permission should be denied."""
        rules = []

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, customer.id)

        assert result is False


class TestCustomerFilterByPermissionModel:
    """Tests for filter_by_permission_model method."""

    def test_filter_by_permission_model_explicit_allow_passes(self, handler, customer, second_customer):
        """Resources with explicit ALLOW should pass the filter."""
        candidate_ids = {customer.id, second_customer.id}
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        assert customer.id in result
        assert second_customer.id in result

    def test_filter_by_permission_model_explicit_deny_filtered(self, handler, customer, second_customer):
        """Resources with explicit DENY should be filtered out."""
        candidate_ids = {customer.id, second_customer.id}
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        assert customer.id not in result
        assert second_customer.id in result

    def test_filter_by_permission_model_deny_overrides_allow(self, handler, customer):
        """DENY should override ALLOW for the same resource."""
        candidate_ids = {customer.id}
        rules = [
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
            make_policy_read(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
            ),
        ]

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        assert customer.id not in result


class TestCustomerListResourcesForCustomer:
    """Tests for list_resources_for_customer method."""

    def test_list_resources_for_customer_returns_self(self, handler, customer):
        """For customers, this returns the customer itself."""
        result = handler.list_resources_for_customer(customer.id)

        assert len(result) == 1
        assert result[0]['id'] == customer.id
        assert result[0]['name'] == customer.name


class TestCustomerResourceType:
    """Tests for resource_type property."""

    def test_resource_type_is_customer(self, handler):
        """Handler should report CUSTOMER as its resource type."""
        assert handler.resource_type == ResourceTypeEnum.CUSTOMER


class TestCustomerIntegrationWithPermissions:
    """
    Integration tests that verify CustomerPermissionHandler works correctly
    with actual database records for permissions.
    """

    def test_full_permission_flow_with_membership(self, db, handler, non_staff_user, customer, second_customer):
        """
        Test the full permission checking flow with real memberships and roles.
        """
        # Create membership for user
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create a role with READ permission to customer
        role = AccessRole.create(AccessRoleCreate(name='Test Role', description='Test role'))

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

        # Now test the handler with the actual policy
        rules = [policy]

        # Should have permission to customer
        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, customer.id) is True

        # Should NOT have permission to second_customer
        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, second_customer.id) is False

    def test_deny_rule_blocks_access(self, db, handler, non_staff_user, customer):
        """Test that DENY rules properly block access."""
        # Create membership for user
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create a role with conflicting permissions
        role = AccessRole.create(AccessRoleCreate(name='Conflicting Role', description='Has both allow and deny'))

        # Create ALLOW policy
        allow_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Allow Customer Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Create DENY policy
        deny_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Deny Customer Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link both policies to role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=role.id, policy_id=allow_policy.id))
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=role.id, policy_id=deny_policy.id))

        # Assign role to membership
        MembershipAssignment.create(MembershipAssignmentCreate(membership_id=membership.id, access_role_id=role.id))

        # Test with both policies - DENY should win
        rules = [allow_policy, deny_policy]

        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, customer.id) is False
