from src.common.enum import BaseEnum


class AuthzScopeEnum(BaseEnum):
    STAFF_ADMIN = 'staff::admin'
    CUSTOMER_ADMIN = 'customer::admin'


class PermissionTypeEnum(BaseEnum):
    READ = 'READ'
    WRITE = 'WRITE'
    ADMIN = 'ADMIN'


class PermissionEffectEnum(BaseEnum):
    ALLOW = 'ALLOW'
    DENY = 'DENY'


class ResourceTypeEnum(BaseEnum):
    STAFF = 'STAFF'
    CUSTOMER = 'CUSTOMER'
    PROJECT = 'PROJECT'


class ResourceSelectorTypeEnum(BaseEnum):
    EXACT = 'exact'
    MULTIPLE = 'multiple'
    WILDCARD = 'wildcard'
    WILDCARD_EXCEPT = 'wildcard_except'


# PK Abbreviation Constants
ACCESS_ROLE_PK_ABBREV = 'arol'
ACCESS_POLICY_PK_ABBREV = 'apol'
POLICY_ROLE_ASSIGNMENT_PK_ABBREV = 'pras'
MEMBERSHIP_ASSIGNMENT_PK_ABBREV = 'masgn'

# Role Names
STAFF_ROLE_NAME = 'Staff'
SUPER_STAFF_ROLE_NAME = 'Super Staff'
