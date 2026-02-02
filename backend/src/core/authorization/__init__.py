from src.core.authorization.constants import (
    ACCESS_POLICY_PK_ABBREV,
    ACCESS_ROLE_PK_ABBREV,
    MEMBERSHIP_ASSIGNMENT_PK_ABBREV,
    POLICY_ROLE_ASSIGNMENT_PK_ABBREV,
    STAFF_ROLE_NAME,
    PermissionEffectEnum,
    PermissionTypeEnum,
    ResourceSelectorTypeEnum,
    ResourceTypeEnum,
)
from src.core.authorization.dependencies import get_permission_context
from src.core.authorization.domains import (
    AccessPolicyCreate,
    AccessPolicyRead,
    AccessPolicyWithRolePayload,
    AccessRoleCreate,
    AccessRoleCreateWithPolicies,
    AccessRoleRead,
    AccessRoleSummary,
    CreateCustomerPayload,
    CustomerDefaultRoleUpdate,
    Me,
    MembershipAssignmentCreate,
    MembershipAssignmentRead,
    MyLoginConfig,
    PolicyRoleAssignmentCreate,
    PolicyRoleAssignmentUpdate,
    RoleCreateWithPolicies,
    RoleMembershipAssignmentUpdate,
    RolePolicyAssignmentUpdate,
)
from src.core.authorization.exceptions import (
    InvalidSelectorError,
    PermissionError,
    ResourceNotFoundError,
)

# Guards are not imported here to avoid circular imports
# Import them directly from src.core.authorization.guards when needed
from src.core.authorization.models import (
    AccessPolicy,
    AccessRole,
    MembershipAssignment,
    PolicyRoleAssignment,
)
from src.core.authorization.services import AccessControlService, PermissionService

# Alias for backward compatibility
AuthorizationService = PermissionService

__all__ = [
    # Constants
    'ACCESS_POLICY_PK_ABBREV',
    'ACCESS_ROLE_PK_ABBREV',
    'MEMBERSHIP_ASSIGNMENT_PK_ABBREV',
    'POLICY_ROLE_ASSIGNMENT_PK_ABBREV',
    'PermissionEffectEnum',
    'PermissionTypeEnum',
    'ResourceSelectorTypeEnum',
    'ResourceTypeEnum',
    'STAFF_ROLE_NAME',
    # Dependencies
    'get_permission_context',
    # Domains
    'AccessPolicyCreate',
    'AccessPolicyRead',
    'AccessPolicyWithRolePayload',
    'AccessRoleCreate',
    'AccessRoleCreateWithPolicies',
    'AccessRoleRead',
    'AccessRoleSummary',
    'CreateCustomerPayload',
    'CustomerDefaultRoleUpdate',
    'Me',
    'MembershipAssignmentCreate',
    'MembershipAssignmentRead',
    'MyLoginConfig',
    'PolicyRoleAssignmentCreate',
    'PolicyRoleAssignmentUpdate',
    'RoleCreateWithPolicies',
    'RoleMembershipAssignmentUpdate',
    'RolePolicyAssignmentUpdate',
    # Exceptions
    'InvalidSelectorError',
    'PermissionError',
    'ResourceNotFoundError',
    # Guards - import directly from src.core.authorization.guards
    # Models
    'AccessPolicy',
    'AccessRole',
    'MembershipAssignment',
    'PolicyRoleAssignment',
    # Services
    'AccessControlService',
    'AuthorizationService',  # Alias for PermissionService (backward compatibility)
    'PermissionService',
]
