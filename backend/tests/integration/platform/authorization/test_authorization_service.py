import pytest

from src.core.authorization import (
    STAFF_ROLE_NAME,
    AccessControlService,
    AccessPolicy,
    AccessPolicyCreate,
    AccessRole,
    AccessRoleCreate,
    AuthorizationService,
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
def customer(db):
    """Create a test customer"""
    return Customer.create(CustomerCreate(name='Test Customer'))


@pytest.fixture
def second_customer(db):
    """Create a second test customer"""
    return Customer.create(CustomerCreate(name='Second Customer'))


class TestSystemAccessSets:
    """
    Tests for system-defined permission sets that implement the core access control patterns.

    These tests validate the migration from the legacy authorization scopes to the new RBAC system,
    ensuring that predefined roles like staff admin and customer admin work correctly
    with the simplified permission model. Each test validates a specific access pattern:

    - Staff admins: Full system access across all customers
    - Customer admins: Full access within a specific customer
    """

    def test_staff_admin_access(self, db, customer, second_customer, staff_user):
        """
        Test that staff admins have full access to all resources through the RBAC system.

        This test verifies that users with staff admin permissions can:
        - Access all customers
        - Access resources across multiple customers
        """
        # Create a membership for the staff user
        membership = Membership.create(MembershipCreate(user_id=staff_user.id, customer_id=customer.id, is_active=True))

        # Create staff admin permission set
        staff_admin_set = AccessRole.create(
            AccessRoleCreate(name='StaffAdmin', description='Full system access for staff')
        )

        # Grant ADMIN access to customer for staff admin
        staff_admin_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Staff Admin Policy',
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=staff_admin_set.id, policy_id=staff_admin_policy.id)
        )

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=staff_admin_set.id)
        )

        auth_service = AuthorizationService.factory()

        # Staff should have write access to the customer
        assert (
            auth_service.check_permission(
                user_id=staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # We need to explicitly grant access to the second customer
        other_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Staff Admin Other Customer Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': second_customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=staff_admin_set.id, policy_id=other_policy.id))

        # Staff should have access to other customer
        assert (
            auth_service.check_permission(
                user_id=staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=second_customer.id,
            )
            is True
        )

    def test_customer_admin_access(self, db, customer, second_customer, non_staff_user):
        """
        Test that customer admins have full access to their customer but not others.

        This test verifies that users with customer admin permissions can:
        - Access the customer they have permissions for
        - Cannot access resources in other customers
        """
        # Create membership to customer
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create customer admin permission set
        customer_admin_set = AccessRole.create(
            AccessRoleCreate(
                name='CustomerAdmin',
                description='Admin for customer',
            )
        )

        # Add permission rule for customer access
        customer_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Admin Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=customer_admin_set.id, policy_id=customer_policy.id)
        )

        # Assign permission set to user's membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=customer_admin_set.id)
        )

        auth_service = AuthorizationService.factory()

        # User should have access to the assigned customer
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # User should NOT have access to other customer
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=second_customer.id,
            )
            is False
        )


class TestAuthorizationServiceCore:
    """
    Core test cases for the permissions system covering standard authorization patterns.

    These tests validate the fundamental principles of the authorization service:
    - Direct resource permissions: Explicit permissions to specific resources
    - Permission precedence: DENY permissions override ALLOW permissions
    - Multiple permission sets: Combining permissions from different assigned sets
    - Role patterns: Predefined permission patterns like read-only auditor access
    """

    def test_basic_permission_checks(self, customer, second_customer, non_staff_user):
        """
        Test direct resource permissions.

        This test verifies the most basic permission check functionality:
        - Users can access resources they have explicit permissions for
        - Users cannot access resources they don't have permissions for
        - Permission rules with exact resource selectors correctly limit access to specific resources
        """
        # Create a membership for the user
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create customer admin permission set
        customer_admin_set = AccessRole.create(
            AccessRoleCreate(name='CustomerAdmin', description='Admin for specific customer')
        )

        # Add permission rule for direct customer access
        customer_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Write Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=customer_admin_set.id, policy_id=customer_policy.id)
        )

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=customer_admin_set.id)
        )

        # Test permission check
        auth_service = AuthorizationService.factory()
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # User should not have access to the second customer
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=second_customer.id,
            )
            is False
        )

    def test_permission_precedence(self, db, customer, non_staff_user):
        """
        Test that DENY permissions override ALLOW permissions.

        This test verifies the permission precedence rules:
        - Explicit DENY rules override any ALLOW rules, even from the same permission set
        """
        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create permission set with conflicting rules
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='ConflictingRules',
                description='Set with both allow and deny rules',
            )
        )

        # Grant permissions to the customer
        customer_allow_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Write Allow Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=customer_allow_policy.id)
        )

        # Add rule to explicitly deny access to the same customer
        customer_deny_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Write Deny Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=customer_deny_policy.id)
        )

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        # Test permission check - DENY should override ALLOW
        auth_service = AuthorizationService.factory()
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is False
        )

    def test_multiple_permission_sets(self, db, customer, non_staff_user):
        """
        Test permission resolution with multiple assigned permission sets.

        This test verifies that when a user has multiple permission sets:
        - The user gets the union of all permissions (most permissive access)
        - READ permissions from one set and WRITE permissions from another are both applied
        - The system evaluates all assigned permission sets during access checks
        """
        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create read-only permission set
        readonly_set = AccessRole.create(AccessRoleCreate(name='ReadOnly', description='Read access to customer'))

        # Grant read access to the customer
        readonly_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Read Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=readonly_set.id, policy_id=readonly_policy.id))

        # Create customer-specific write permission set
        write_set = AccessRole.create(
            AccessRoleCreate(
                name='CustomerWrite',
                description='Write access to specific customer',
            )
        )

        # Add rule for write access to specific customer
        write_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Write Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=write_set.id, policy_id=write_policy.id))

        # Assign both permission sets to the membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=readonly_set.id)
        )

        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=write_set.id)
        )

        # Test permission checks
        auth_service = AuthorizationService.factory()

        # User should have read access to customer
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # User should have write access to the customer
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

    def test_auditor_role_pattern(self, db, customer, non_staff_user):
        """
        Test the auditor role permission pattern.

        This test verifies the common auditor role pattern where:
        - Users have READ access to all resources in a customer
        - Users are explicitly denied WRITE access to all resources
        - The combination creates a true read-only role
        """
        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create auditor permission set
        auditor_set = AccessRole.create(
            AccessRoleCreate(name='Auditor', description='Read-only access for audit purposes')
        )

        # Grant read access to the customer
        read_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Auditor Read Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the read policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=auditor_set.id, policy_id=read_policy.id))

        # Add explicit deny for write operations on customer
        write_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Auditor Write Deny Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the write policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=auditor_set.id, policy_id=write_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=auditor_set.id)
        )

        # Test permission checks
        auth_service = AuthorizationService.factory()

        # User should have read access to customer
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # User should not have write access to customer
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is False
        )


class TestResourceSelectors:
    """
    Tests for the different types of resource selectors and their behavior.

    Resource selectors are a key component of the permission system, allowing rules to target:
    - Exact resources: Target a specific resource by ID
    - Multiple resources: Target a defined set of resources by their IDs
    - Wildcard: Target all resources of a type

    These tests verify that each selector type correctly identifies the intended resources
    and that permissions are applied only to the targeted resources.
    """

    def test_exact_resource_selector(self, db, customer, second_customer, non_staff_user):
        """
        Test exact resource selector for precise targeting.

        This test verifies that:
        - The exact resource selector correctly targets a single specific resource
        - Permissions only apply to the exact resource specified in the selector
        - Other resources of the same type remain inaccessible
        """
        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create permission set with exact selectors
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='ExactCustomerSelector',
                description='Access to one specific customer',
            )
        )

        # Add rule for access to exactly customer1
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Exact Customer Selector Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # Verify write access to customer1
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Verify NO write access to customer2
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=second_customer.id,
            )
            is False
        )

    def test_multiple_resource_selector(self, db, non_staff_user):
        """
        Test multiple resource selector for targeting specific resources.

        This test verifies that:
        - The multiple resource selector correctly targets a defined set of resources
        - Permissions apply to all resources included in the selector's ID list
        - Resources not included in the selector remain inaccessible
        """
        # Create multiple customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))
        customer3 = Customer.create(CustomerCreate(name='Customer 3'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set with multiple selectors
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='MultipleCustomerSelector',
                description='Access to specific set of customers',
            )
        )

        # Add rule for access to customer1 and customer2 but not customer3
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Multiple Customer Selector Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.MULTIPLE, 'ids': [customer1.id, customer2.id]},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # Verify write access to customer1
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer1.id,
            )
            is True
        )

        # Verify write access to customer2
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer2.id,
            )
            is True
        )

        # Verify NO write access to customer3
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer3.id,
            )
            is False
        )

    def test_wildcard_resource_selector(self, db, customer, non_staff_user):
        """
        Test wildcard resource selector for targeting all resources of a type.

        This test verifies that:
        - The wildcard resource selector correctly targets all resources of a type
        - Permissions apply to all existing resources of that type
        - Permissions apply to resources created after the permission was granted
        - The wildcard selector provides an efficient way to grant broad access
        """
        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create initial customers
        customer1 = Customer.create(CustomerCreate(name='Test Wildcard Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Test Wildcard Customer 2'))

        # Create permission set with wildcard resource selector for all customers
        permission_set = AccessRole.create(AccessRoleCreate(name='Wildcard Customer Permission'))

        # Create permission rule with wildcard resource selector
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Wildcard Customer Policy',
                permission_type=PermissionTypeEnum.READ.value,
                resource_type=ResourceTypeEnum.CUSTOMER.value,
                resource_selector={
                    'type': ResourceSelectorTypeEnum.WILDCARD.value,
                },
                effect=PermissionEffectEnum.ALLOW.value,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        # Get permission service
        auth_service = AuthorizationService.factory()

        # Verify permissions for existing customers
        assert auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer1.id
        )
        assert auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer2.id
        )

        # Create a new customer after permissions are assigned
        customer3 = Customer.create(CustomerCreate(name='Test Wildcard Customer 3'))

        # Verify permissions apply to newly created customer
        assert auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer3.id
        )

        # Verify WRITE permission is not granted (only READ was specified)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.WRITE, ResourceTypeEnum.CUSTOMER, customer1.id
        )


class TestMultiLevelPermissions:
    """
    Tests for complex scenarios with multiple permission sets and overlapping rules.

    These tests verify the permission resolution logic correctly handles complex combinations:
    - Union of permissions: Users with multiple permission sets get the combined permissions
    - Conflict resolution: How the system resolves conflicting rules across permission sets
    - Permission type separation: READ and WRITE permissions are properly separated
    - Specificity precedence: More specific resource selectors take precedence over general ones

    These scenarios validate the system's ability to handle real-world permission complexity
    where users may have multiple roles with different access levels.
    """

    def test_combined_permission_sets(self, db, non_staff_user):
        """
        Test a user with multiple permission sets gets the union of permissions.

        This test verifies that when a user has multiple permission sets:
        - The user gets the union of all permissions (most permissive access)
        - Different permission types (READ/WRITE) from different sets are correctly combined
        - The system evaluates all assigned permission sets during access checks
        """
        # Create multiple customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))
        customer3 = Customer.create(CustomerCreate(name='Customer 3'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create first permission set - read access to customer1
        permission_set1 = AccessRole.create(AccessRoleCreate(name='ReadSet', description='Read access to customer 1'))

        policy1 = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer 1 Read Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer1.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set1.id, policy_id=policy1.id))

        # Create second permission set - write access to customer2
        permission_set2 = AccessRole.create(AccessRoleCreate(name='WriteSet', description='Write access to customer 2'))

        policy2 = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer 2 Write Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer2.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set2.id, policy_id=policy2.id))

        # Assign both permission sets to the membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set1.id)
        )

        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set2.id)
        )

        auth_service = AuthorizationService.factory()

        # Verify read access to customer1 (from first permission set)
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer1.id,
            )
            is True
        )

        # Verify write access to customer2 (from second permission set)
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer2.id,
            )
            is True
        )

        # Verify NO write access to customer1
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer1.id,
            )
            is False
        )

        # Verify READ access to customer2 (write implies read in our implementation)
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer2.id,
            )
            is True
        )

        # Verify NO access to customer3 (neither read nor write)
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer3.id,
            )
            is False
        )

        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer3.id,
            )
            is False
        )

    def test_conflicting_permission_resolution(self, db, customer, non_staff_user):
        """
        Test resolution when multiple permission sets have conflicting rules.

        This test verifies that:
        - When permission sets conflict, DENY always overrides ALLOW
        - This precedence applies even when the DENY and ALLOW are in different permission sets
        - The system correctly identifies and resolves conflicts across all assigned sets
        """
        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create first permission set with ALLOW
        allow_set = AccessRole.create(AccessRoleCreate(name='AllowSet', description='Allow access to customer'))

        allow_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Allow Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=allow_set.id, policy_id=allow_policy.id))

        # Create second permission set with DENY
        deny_set = AccessRole.create(AccessRoleCreate(name='DenySet', description='Deny access to customer'))

        deny_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Deny Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=deny_set.id, policy_id=deny_policy.id))

        # Assign both sets to the membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=allow_set.id)
        )

        MembershipAssignment.create(MembershipAssignmentCreate(membership_id=membership.id, access_role_id=deny_set.id))

        auth_service = AuthorizationService.factory()

        # Verify DENY overrides ALLOW
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is False
        )

    def test_read_vs_write_separation(self, db, customer, non_staff_user):
        """
        Test that read and write permissions are properly separated.

        This test verifies that:
        - READ and WRITE permissions are evaluated independently
        - A user can have READ access without WRITE access
        - WRITE access automatically implies READ access (write implies read)
        - DENY rules can be applied to specific permission types
        """
        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create permission set with read but not write
        permission_set = AccessRole.create(AccessRoleCreate(name='ReadOnlySet', description='Read-only access'))

        # Allow read on customer
        read_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Read Allow Policy',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the read policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=read_policy.id))

        # Explicitly deny write on customer
        write_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Write Deny Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the write policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=write_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # Verify read is allowed
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Verify write is denied
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is False
        )


class TestAdminPermissions:
    """
    Tests for the ADMIN permission type and its relationship with READ and WRITE permissions.

    These tests verify that the ADMIN permission type correctly implements the permission hierarchy:
    - ADMIN permission implies WRITE permission
    - WRITE permission implies READ permission
    - ADMIN permission can restrict sensitive operations that WRITE cannot perform

    The tests validate both direct permissions and the ADMIN permission type.
    """

    def test_admin_implies_write_and_read(self, customer, non_staff_user):
        """
        Test that ADMIN permission implies both WRITE and READ permissions.

        This test verifies that:
        - A user with ADMIN permission automatically has WRITE access
        - A user with ADMIN permission automatically has READ access
        - The permission implication works at the customer level
        """
        # Create membership to customer
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create permission set with ADMIN access to customer
        admin_role = AccessRole.create(
            AccessRoleCreate(
                name='AdminRole',
                description='Role with ADMIN permissions',
            )
        )

        # Add ADMIN permission for customer
        admin_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Admin Policy',
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=admin_role.id, policy_id=admin_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=admin_role.id)
        )

        auth_service = AuthorizationService.factory()

        # Test ADMIN permission directly
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Test that ADMIN implies WRITE
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Test that ADMIN implies READ
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

    def test_write_does_not_imply_admin(self, customer, non_staff_user):
        """
        Test that WRITE permission does not imply ADMIN permission.

        This test verifies that:
        - A user with WRITE permission does not automatically have ADMIN access
        - The permission hierarchy is strictly one-way (ADMIN → WRITE → READ)
        - WRITE permissions can be granted without granting ADMIN capabilities
        """
        # Create membership to customer
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create permission set with WRITE permission
        permission_set = AccessRole.create(
            AccessRoleCreate(name='WriteRole', description='Role with WRITE permissions')
        )

        # Add WRITE permission for customer
        write_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Write Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=write_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # Test WRITE permission directly
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Test that WRITE implies READ
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Test that WRITE does NOT imply ADMIN
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is False
        )

    def test_admin_deny_overrides_write_allow(self, customer, non_staff_user):
        """
        Test that ADMIN DENY overrides WRITE ALLOW for the same resource.

        This test verifies that:
        - Explicit DENY for ADMIN permission prevents ADMIN access
        - WRITE and READ permissions are still available when ADMIN is denied
        - The permission type specificity is respected in permission resolution
        """
        # Create membership to customer
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create permission set with mixed permissions
        permission_set = AccessRole.create(
            AccessRoleCreate(name='MixedPermissions', description='Role with mixed permission types')
        )

        # Add WRITE permission for customer (ALLOW)
        write_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Write Allow Policy',
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=write_policy.id))

        # Add ADMIN permission for customer (DENY)
        admin_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Admin Deny Policy',
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=admin_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # Test ADMIN permission is denied
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is False
        )

        # Test WRITE permission is still allowed
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Test READ permission is still allowed (implied by WRITE)
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

    def test_staff_admin_has_admin_permissions(self, customer, staff_user):
        """
        Test that staff admin users have ADMIN permissions to all resources.

        This test verifies that:
        - Staff admin users are granted ADMIN permission type to customers
        - Staff admins can perform all operations including those requiring ADMIN permission
        """
        # Create a membership for the staff user
        membership = Membership.create(MembershipCreate(user_id=staff_user.id, customer_id=customer.id, is_active=True))

        # Create staff admin permission set
        staff_admin_set = AccessRole.create(
            AccessRoleCreate(name='StaffAdmin', description='Full system access for staff')
        )

        # Grant ADMIN access to customer for staff admin
        staff_admin_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Staff Admin Policy',
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=staff_admin_set.id, policy_id=staff_admin_policy.id)
        )

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=staff_admin_set.id)
        )

        auth_service = AuthorizationService.factory()

        # Staff should have ADMIN access to customer
        assert (
            auth_service.check_permission(
                user_id=staff_user.id,
                permission_type=PermissionTypeEnum.ADMIN,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Staff should have WRITE access to customer (implied by ADMIN)
        assert (
            auth_service.check_permission(
                user_id=staff_user.id,
                permission_type=PermissionTypeEnum.WRITE,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )

        # Staff should have READ access to customer (implied by ADMIN)
        assert (
            auth_service.check_permission(
                user_id=staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer.id,
            )
            is True
        )


class TestListPermittedIds:
    """
    Tests for the AuthorizationService.list_permitted_ids method.

    This method returns a set of resource IDs that a user has the specified permission for,
    which is critical for implementing resource-based permissions and filtering collections
    of resources to only those a user is permitted to access.
    """

    def test_staff_access_returns_all_customers(self, staff_user, customer):
        """
        Test that staff users receive access to all customers they have permissions for.
        """
        # Create an active membership for the staff user
        Membership.create(MembershipCreate(user_id=staff_user.id, customer_id=customer.id, is_active=True))

        # Grant staff admin access to the user (now that they have a membership)
        AccessControlService.factory().grant_staff_admin_access(staff_user.id)
        auth_service = AuthorizationService.factory()

        # Verify the staff role exists
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        assert staff_role is not None

        # Get all active memberships for this user
        auth_service.membership_service.list_memberships_for_user(user_id=staff_user.id)

        # Check permissions
        auth_service.invalidate_permission_cache(user_id=staff_user.id)

        # Verify staff user has access to all customers
        permitted_ids = auth_service.list_permitted_ids(
            user_id=staff_user.id,
            permission_type=PermissionTypeEnum.READ,
            resource_type=ResourceTypeEnum.CUSTOMER,
        )
        all_customers = Customer.list()

        assert len(permitted_ids) == len(all_customers)
        # Also verify staff status directly
        assert auth_service.is_staff_user_id(staff_user.id) == True

    def test_specific_allow_permissions(self, non_staff_user):
        """
        Test that users receive access only to specifically allowed resources.
        """
        # Create three customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set with access to just customers 1 and 2
        permission_set = AccessRole.create(
            AccessRoleCreate(name='SpecificCustomersRole', description='Access to specific customers')
        )

        # Add permission for customer1
        customer1_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer 1 Access',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer1.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=customer1_policy.id)
        )

        # Add permission for customer2
        customer2_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer 2 Access',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer2.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=customer2_policy.id)
        )

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        # Check permitted IDs
        auth_service = AuthorizationService.factory()

        permitted_ids = auth_service.list_permitted_ids(
            user_id=non_staff_user.id,
            permission_type=PermissionTypeEnum.READ,
            resource_type=ResourceTypeEnum.CUSTOMER,
        )

        # Should have access to exactly customers 1 and 2
        assert customer1.id in permitted_ids
        assert customer2.id in permitted_ids
        assert None not in permitted_ids
        assert len(permitted_ids) == 2

    def test_only_deny_permissions(self, non_staff_user):
        """
        Test that when only deny permissions exist (with no allow permissions),
        access is denied to all resources (deny by default).

        This implements the security principle of least privilege where access
        must be explicitly granted and is denied by default.
        """
        # Create two customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set with only deny for customer1
        permission_set = AccessRole.create(AccessRoleCreate(name='OnlyDeniesRole', description='Only deny permissions'))

        # Add deny for customer1
        deny_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer 1 Deny',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer1.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=deny_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        # Check permitted IDs
        auth_service = AuthorizationService.factory()

        permitted_ids = auth_service.list_permitted_ids(
            user_id=non_staff_user.id,
            permission_type=PermissionTypeEnum.READ,
            resource_type=ResourceTypeEnum.CUSTOMER,
        )

        # With only DENY rules and no ALLOW rules, no resources should be accessible
        # This follows the principle of least privilege (deny by default)
        assert len(permitted_ids) == 0
        assert customer1.id not in permitted_ids
        assert customer2.id not in permitted_ids
        assert None not in permitted_ids

    def test_deny_wildcard_blocks_all_access(self, non_staff_user):
        """
        Test that a deny wildcard blocks all access, regardless of any allow rules.
        """
        # Create a customer
        customer = Customer.create(CustomerCreate(name='Test Customer'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create permission set with allow for specific customer but deny wildcard
        permission_set = AccessRole.create(AccessRoleCreate(name='DenyWildcardRole', description='Deny wildcard role'))

        # Add allow for customer
        allow_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Customer Allow',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=allow_policy.id))

        # Add deny wildcard
        deny_wildcard_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='All Customers Deny',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(
            PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=deny_wildcard_policy.id)
        )

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        # Check permitted IDs
        auth_service = AuthorizationService.factory()

        permitted_ids = auth_service.list_permitted_ids(
            user_id=non_staff_user.id,
            permission_type=PermissionTypeEnum.READ,
            resource_type=ResourceTypeEnum.CUSTOMER,
        )

        # Should have no access to any customers
        assert len(permitted_ids) == 0
        assert customer.id not in permitted_ids
        assert None not in permitted_ids

    def test_no_permissions_returns_empty_set(self, non_staff_user):
        """
        Test that when no permissions exist for a resource, an empty set is returned.
        """
        # Create membership
        customer = Customer.create(CustomerCreate(name='Test Customer'))
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer.id, is_active=True)
        )

        # Create a different customer that the user DOES have access to
        other_customer = Customer.create(CustomerCreate(name='Other Customer'))

        # Create permission set with permission for a DIFFERENT customer
        permission_set = AccessRole.create(
            AccessRoleCreate(name='LimitedRole', description='Access to other customer only')
        )

        # Add permission for the OTHER customer (not the one we'll check)
        other_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Other Customer Access',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': other_customer.id},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=other_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        # Check permitted IDs - but we're looking for WRITE permission which wasn't granted
        auth_service = AuthorizationService.factory()

        permitted_ids = auth_service.list_permitted_ids(
            user_id=non_staff_user.id,
            permission_type=PermissionTypeEnum.WRITE,  # Looking for WRITE, but only READ was granted
            resource_type=ResourceTypeEnum.CUSTOMER,
        )

        # Should have no access to customers for WRITE permission
        assert len(permitted_ids) == 0
        assert customer.id not in permitted_ids


class TestStaffUserIdentification:
    """
    Tests for identifying staff users through the is_staff_user_id method.

    This tests the core functionality that determines whether a user has staff privileges
    based on their membership assignments and roles.
    """

    def test_staff_user_id_positive(self, staff_user, customer):
        """
        Test that a user with the staff role is correctly identified as a staff user.
        """
        # Create a membership for the staff user
        Membership.create(MembershipCreate(user_id=staff_user.id, customer_id=customer.id, is_active=True))

        # Grant staff admin access to the user
        AccessControlService.factory().grant_staff_admin_access(staff_user.id)
        auth_service = AuthorizationService.factory()

        # Verify the staff role exists
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        assert staff_role is not None

        # Clear cache to ensure fresh check
        auth_service.invalidate_permission_cache(user_id=staff_user.id)

        # Verify the user is identified as staff
        assert auth_service.is_staff_user_id(staff_user.id) == True

    def test_non_staff_user_id_negative(self, non_staff_user):
        """
        Test that a user without the staff role is not identified as a staff user.
        """
        auth_service = AuthorizationService.factory()

        # Verify the user is not identified as staff
        assert auth_service.is_staff_user_id(non_staff_user.id) == False

    def test_is_staff_user_id_with_inactive_membership(self, staff_user, customer):
        """
        Test that a user with an inactive staff membership is not identified as a staff user.
        """
        # Create an INACTIVE membership for the staff user
        membership = Membership.create(
            MembershipCreate(user_id=staff_user.id, customer_id=customer.id, is_active=False)
        )

        # Create the staff role
        staff_role = AccessRole.get_or_create(
            name=STAFF_ROLE_NAME,
            defaults={'description': 'Staff admin role'},
        )[0]

        # Assign the staff role to the INACTIVE membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=staff_role.id)
        )

        auth_service = AuthorizationService.factory()

        # Clear cache to ensure fresh check
        auth_service.invalidate_permission_cache(user_id=staff_user.id)

        # Verify the user is NOT identified as staff (inactive membership)
        assert auth_service.is_staff_user_id(staff_user.id) == False

    def test_is_staff_user_id_with_no_staff_role(self, staff_user, customer, db):
        """
        Test the behavior when the staff role doesn't exist in the system.
        """
        # Ensure there's no staff role in the database
        staff_role = AccessRole.get_or_none(AccessRole.name == STAFF_ROLE_NAME)
        if staff_role:
            # Remove all assignments first
            MembershipAssignment.delete(MembershipAssignment.access_role_id == staff_role.id)
            PolicyRoleAssignment.delete(PolicyRoleAssignment.role_id == staff_role.id)
            # Then delete the role
            AccessRole.delete(AccessRole.id == staff_role.id)
            db.commit()

        # Create a membership for the user
        Membership.create(MembershipCreate(user_id=staff_user.id, customer_id=customer.id, is_active=True))

        auth_service = AuthorizationService.factory()

        # Clear cache to ensure fresh check
        auth_service.invalidate_permission_cache(user_id=staff_user.id)

        # Verify the user is NOT identified as staff (no staff role exists)
        assert auth_service.is_staff_user_id(staff_user.id) == False


class TestWildcardExceptPermissions:
    """
    Tests for the wildcard_except resource selector which grants broad permissions
    with specific exclusions.

    This selector allows permissions to all resources of a type EXCEPT for
    specifically excluded resources, useful for scenarios like:
    - Grant access to all customers except archived ones
    - Allow viewing all resources except sensitive ones
    """

    def test_wildcard_except_allow_single_exclusion(self, db, non_staff_user):
        """
        Test that wildcard_except ALLOW grants access to all customers except one excluded customer.

        This tests the basic wildcard_except functionality with a single exclusion.
        """
        # Create multiple customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))
        customer3 = Customer.create(CustomerCreate(name='Customer 3'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set with wildcard_except ALLOW
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='WildcardExceptAllow',
                description='Access all customers except one',
            )
        )

        # Add wildcard_except ALLOW permission - all customers except customer2
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='All Customers Except One',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': [customer2.id]},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # User should have access to customer1
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer1.id,
            )
            is True
        )

        # User should NOT have access to customer2 (excluded)
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer2.id,
            )
            is False
        )

        # User should have access to customer3
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer3.id,
            )
            is True
        )

        # Create a new customer after permission assignment
        customer4 = Customer.create(CustomerCreate(name='Customer 4'))

        # User should have access to newly created customer4
        assert (
            auth_service.check_permission(
                user_id=non_staff_user.id,
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_id=customer4.id,
            )
            is True
        )

    def test_wildcard_except_allow_multiple_exclusions(self, db, non_staff_user):
        """
        Test wildcard_except ALLOW with multiple excluded customers.
        """
        # Create multiple customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))
        customer3 = Customer.create(CustomerCreate(name='Customer 3'))
        customer4 = Customer.create(CustomerCreate(name='Customer 4'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='WildcardExceptMultiple',
                description='Access all customers except some',
            )
        )

        # Add wildcard_except ALLOW permission - exclude customer2 and customer3
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='All Customers Except Two',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={
                    'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT,
                    'excluded_ids': [customer2.id, customer3.id],
                },
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # User should have access to customer1
        assert auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer1.id
        )

        # User should NOT have access to customer2 (excluded)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer2.id
        )

        # User should NOT have access to customer3 (excluded)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer3.id
        )

        # User should have access to customer4
        assert auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer4.id
        )

    def test_wildcard_except_deny_single_exclusion(self, db, non_staff_user):
        """
        Test wildcard_except DENY blocks all customers except the excluded one.

        With wildcard_except DENY, the user is denied access to all resources
        EXCEPT the ones in the exclusion list.
        """
        # Create multiple customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))
        customer3 = Customer.create(CustomerCreate(name='Customer 3'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='WildcardExceptDeny',
                description='Deny all customers except one',
            )
        )

        # First add a wildcard ALLOW so the user has base permissions
        allow_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Base Allow All',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the allow policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=allow_policy.id))

        # Add wildcard_except DENY permission - deny all except customer2
        deny_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Deny All Customers Except One',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': [customer2.id]},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the deny policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=deny_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # User should NOT have access to customer1 (denied by wildcard_except)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer1.id
        )

        # User SHOULD have access to customer2 (excluded from the deny)
        assert auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer2.id
        )

        # User should NOT have access to customer3 (denied by wildcard_except)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer3.id
        )

    def test_wildcard_except_deny_requires_allow_rule(self, db, non_staff_user):
        """
        Test that wildcard_except DENY alone doesn't grant access - you need an ALLOW rule.

        This verifies the principle of least privilege - denying access to most resources
        doesn't automatically grant access to the excluded ones.
        """
        # Create customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set with ONLY a wildcard_except DENY (no ALLOW)
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='OnlyWildcardExceptDeny',
                description='Only deny, no allow',
            )
        )

        # Add ONLY wildcard_except DENY permission
        policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Deny Most Customers',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': [customer2.id]},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # User should NOT have access to customer1 (no ALLOW rule)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer1.id
        )

        # User should NOT have access to customer2 either (no ALLOW rule, even though excluded from DENY)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer2.id
        )

    def test_wildcard_except_overrides(self, db, non_staff_user):
        """
        Test interaction between wildcard_except and other permission rules.

        Tests that specific DENY rules can override wildcard_except ALLOW.
        """
        # Create customers
        customer1 = Customer.create(CustomerCreate(name='Customer 1'))
        customer2 = Customer.create(CustomerCreate(name='Customer 2'))
        customer3 = Customer.create(CustomerCreate(name='Customer 3'))

        # Create membership
        membership = Membership.create(
            MembershipCreate(user_id=non_staff_user.id, customer_id=customer1.id, is_active=True)
        )

        # Create permission set
        permission_set = AccessRole.create(
            AccessRoleCreate(
                name='ComplexWildcardExcept',
                description='Complex wildcard_except scenarios',
            )
        )

        # Add wildcard_except ALLOW - all customers except customer2
        allow_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Allow Most Customers',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': [customer2.id]},
                effect=PermissionEffectEnum.ALLOW,
            )
        )

        # Link the allow policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=allow_policy.id))

        # Add specific DENY for customer3 (should override the wildcard_except ALLOW)
        deny_policy = AccessPolicy.create(
            AccessPolicyCreate(
                name='Deny Customer 3',
                permission_type=PermissionTypeEnum.READ,
                resource_type=ResourceTypeEnum.CUSTOMER,
                resource_selector={'type': ResourceSelectorTypeEnum.EXACT, 'id': customer3.id},
                effect=PermissionEffectEnum.DENY,
            )
        )

        # Link the deny policy to the role
        PolicyRoleAssignment.create(PolicyRoleAssignmentCreate(role_id=permission_set.id, policy_id=deny_policy.id))

        # Assign permission set to membership
        MembershipAssignment.create(
            MembershipAssignmentCreate(membership_id=membership.id, access_role_id=permission_set.id)
        )

        auth_service = AuthorizationService.factory()

        # User should have access to customer1 (allowed by wildcard_except)
        assert auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer1.id
        )

        # User should NOT have access to customer2 (excluded from wildcard_except ALLOW)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer2.id
        )

        # User should NOT have access to customer3 (specific DENY overrides wildcard_except ALLOW)
        assert not auth_service.check_permission(
            non_staff_user.id, PermissionTypeEnum.READ, ResourceTypeEnum.CUSTOMER, customer3.id
        )
