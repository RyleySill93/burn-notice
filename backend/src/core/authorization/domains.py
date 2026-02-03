from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

from pydantic import Field

from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType
from src.core.authentication import UserAuthSettings
from src.core.authorization.constants import (
    ACCESS_POLICY_PK_ABBREV,
    ACCESS_ROLE_PK_ABBREV,
    MEMBERSHIP_ASSIGNMENT_PK_ABBREV,
    POLICY_ROLE_ASSIGNMENT_PK_ABBREV,
    AuthzScopeEnum,
    PermissionEffectEnum,
    PermissionTypeEnum,
    ResourceSelectorTypeEnum,
    ResourceTypeEnum,
)
from src.core.membership import MembershipWithCustomer
from src.core.user import UserRead


# Resource Selector Models
class ExactResourceSelector(BaseDomain):
    """Selector that matches an exact resource by ID"""

    type: Literal[ResourceSelectorTypeEnum.EXACT]
    id: NanoIdType


class MultipleResourceSelector(BaseDomain):
    """Selector that matches multiple resources by IDs"""

    type: Literal[ResourceSelectorTypeEnum.MULTIPLE]
    ids: List[NanoIdType]


class WildcardResourceSelector(BaseDomain):
    """Selector that matches all resources of a specific type"""

    type: Literal[ResourceSelectorTypeEnum.WILDCARD]


class WildcardExceptResourceSelector(BaseDomain):
    """Selector that matches all resources EXCEPT the specified IDs"""

    type: Literal[ResourceSelectorTypeEnum.WILDCARD_EXCEPT]
    excluded_ids: List[NanoIdType]


class ResourceSelector(BaseDomain):
    """Union type for different resource selector types"""

    selector: Union[
        ExactResourceSelector, MultipleResourceSelector, WildcardResourceSelector, WildcardExceptResourceSelector
    ]

    @classmethod
    def validate_selector(cls, selector: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a resource selector dictionary and return normalized version"""
        if not isinstance(selector, dict):
            raise ValueError(f'Resource selector must be a dictionary, got {type(selector)}')

        selector_type = selector.get('type')
        if not selector_type:
            raise ValueError("Resource selector must include a 'type' field")

        if selector_type == ResourceSelectorTypeEnum.EXACT:
            return ExactResourceSelector(**selector).model_dump()
        elif selector_type == ResourceSelectorTypeEnum.MULTIPLE:
            return MultipleResourceSelector(**selector).model_dump()
        elif selector_type == ResourceSelectorTypeEnum.WILDCARD:
            return WildcardResourceSelector(**selector).model_dump()
        elif selector_type == ResourceSelectorTypeEnum.WILDCARD_EXCEPT:
            # Validate wildcard_except specific requirements
            if 'excluded_ids' not in selector:
                raise ValueError("wildcard_except selector requires 'excluded_ids' field")
            if not isinstance(selector['excluded_ids'], list):
                raise ValueError("wildcard_except 'excluded_ids' must be a list")
            if len(selector['excluded_ids']) == 0:
                raise ValueError("wildcard_except 'excluded_ids' cannot be empty (use 'wildcard' instead)")
            return WildcardExceptResourceSelector(**selector).model_dump()
        else:
            raise ValueError(f'Unknown resource selector type: {selector_type}')


# Original permission models with enhanced validation
class PermissionCreate(BaseDomain):
    user_id: NanoIdType
    scope: AuthzScopeEnum


class PermissionRead(PermissionCreate):
    pass


class AuthorizeScopes(BaseDomain):
    internal: list[AuthzScopeEnum] = Field(default_factory=list)  # Changed from dict to list
    entities: dict[NanoIdType, AuthzScopeEnum] = Field(default_factory=dict)
    customers: dict[NanoIdType, AuthzScopeEnum] = Field(default_factory=dict)


class AuthorizedUser(BaseDomain):
    id: NanoIdType
    email: str
    scopes: AuthorizeScopes | None = None
    impersonator_id: NanoIdType | None = None


class Me(BaseDomain):
    id: NanoIdType
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str
    is_active: bool = False
    impersonator_id: str | None = None
    impersonator_email: str | None = None
    impersonator_full_name: str | None = None
    scopes: AuthorizeScopes | None = None
    memberships: list[MembershipWithCustomer]
    is_staff: bool
    is_super_staff: bool


class MyLoginConfig(BaseDomain):
    email: str
    has_password: bool
    auth_settings: UserAuthSettings

    @classmethod
    def for_anonymous_user(cls, email: str) -> 'MyLoginConfig':
        """
        If a user is anonymous, lets force them down this path
        """
        return cls(
            email=email,
            has_password=True,
            auth_settings=UserAuthSettings.for_anonymous_user(),
        )


class AccessRoleCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=ACCESS_ROLE_PK_ABBREV))
    name: str
    is_default: bool | None = False
    description: Optional[str] = None
    customer_id: NanoIdType | None = None


class AccessRoleRead(AccessRoleCreate):
    id: NanoIdType


class AccessRoleCreateWithPolicies(AccessRoleCreate):
    policy_ids: List[NanoIdType] | None = None

    def to_create_domain(self):
        return AccessRoleCreate(name=self.name, description=self.description, customer_id=self.customer_id)


class ExactSelectorDict(TypedDict):
    type: Literal['exact']
    id: NanoIdType


class MultipleSelectorDict(TypedDict):
    type: Literal['multiple']
    ids: List[NanoIdType]


class WildcardSelectorDict(TypedDict):
    type: Literal['wildcard']


class WildcardExceptSelectorDict(TypedDict):
    type: Literal['wildcard_except']
    excluded_ids: List[NanoIdType]


# Create a union type for the dictionaries
ResourceSelectorDict = Union[ExactSelectorDict, MultipleSelectorDict, WildcardSelectorDict, WildcardExceptSelectorDict]


# In AccessPolicy class, keep resource_selector as a dictionary
class AccessPolicyCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=ACCESS_POLICY_PK_ABBREV))
    name: str
    customer_id: NanoIdType | None = None
    permission_type: PermissionTypeEnum
    resource_type: ResourceTypeEnum
    resource_selector: Dict[str, Any] = Field(default_factory=dict)  # Keep as dictionary
    effect: PermissionEffectEnum = PermissionEffectEnum.ALLOW


class AccessPolicyWithRolePayload(AccessPolicyCreate):
    role_ids: List[NanoIdType] | None = None

    def to_create_domain(self) -> AccessPolicyCreate:
        return AccessPolicyCreate(
            name=self.name,
            customer_id=self.customer_id,
            permission_type=self.permission_type,
            resource_type=self.resource_type,
            resource_selector=self.resource_selector,
            effect=self.effect,
        )


class AccessPolicyRead(AccessPolicyCreate):
    id: NanoIdType


class PolicyRoleAssignmentCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=POLICY_ROLE_ASSIGNMENT_PK_ABBREV))
    role_id: NanoIdType
    policy_id: NanoIdType


class PolicyRoleAssignmentRead(PolicyRoleAssignmentCreate): ...


class PolicyRoleAssignmentUpdate(BaseDomain):
    policy_id: NanoIdType
    role_ids: List[NanoIdType]


class RolePolicyAssignmentUpdate(BaseDomain):
    policy_ids: List[NanoIdType]
    role_id: NanoIdType


class RoleMembershipAssignmentUpdate(BaseDomain):
    role_id: NanoIdType
    membership_ids: List[NanoIdType]


class RoleCreateWithPolicies(BaseDomain):
    """Domain for creating a role with initial policy assignments."""

    name: str
    description: Optional[str] = None
    customer_id: Optional[NanoIdType] = None
    policy_ids: Optional[List[NanoIdType]] = None


# Base domains for MembershipAssignment
class MembershipAssignmentCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=MEMBERSHIP_ASSIGNMENT_PK_ABBREV))
    membership_id: NanoIdType
    access_role_id: NanoIdType  # Changed from role_id to access_role_id


class MembershipAssignmentRead(MembershipAssignmentCreate):
    id: NanoIdType


# Extended domains with relationships
class AccessPolicyWithSet(AccessPolicyRead):
    access_role: AccessRoleRead


class AccessRoleWithRules(AccessRoleRead):
    permissions: List[AccessPolicyRead] = Field(default_factory=list)


class MembershipAssignmentWithSet(MembershipAssignmentRead):
    access_role: AccessRoleRead


# Permission check request/response
class CheckPermissionRequest(BaseDomain):
    user_id: NanoIdType
    permission_type: PermissionTypeEnum
    resource_type: ResourceTypeEnum
    resource_id: Optional[NanoIdType] = None
    property_name: Optional[str] = None


class CheckPermissionResponse(BaseDomain):
    is_allowed: bool
    reason: Optional[str] = None


class AccessRoleSummary(AccessRoleRead):
    policies: Optional[List[AccessPolicyRead]] = None
    users: Optional[List[UserRead]] = None
    membership_count: Optional[int] = None
    policy_count: Optional[int] = None


class CustomerDefaultRoleUpdate(BaseDomain):
    customer_id: NanoIdType
    role_id: NanoIdType


class CreateCustomerPayload(BaseDomain):
    name: str
