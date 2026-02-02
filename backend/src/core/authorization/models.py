from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.model import BaseModel
from src.common.nanoid import NanoIdType
from src.core.authorization.constants import (
    ACCESS_POLICY_PK_ABBREV,
    ACCESS_ROLE_PK_ABBREV,
    MEMBERSHIP_ASSIGNMENT_PK_ABBREV,
    POLICY_ROLE_ASSIGNMENT_PK_ABBREV,
    PermissionEffectEnum,
    PermissionTypeEnum,
    ResourceTypeEnum,
)
from src.core.authorization.domains import (
    AccessPolicyCreate,
    AccessPolicyRead,
    AccessRoleCreate,
    AccessRoleRead,
    MembershipAssignmentCreate,
    MembershipAssignmentRead,
    PermissionCreate,
    PermissionRead,
    PolicyRoleAssignmentCreate,
    PolicyRoleAssignmentRead,
)


# TODO @daniel - deprecate post permissions work
class Permission(BaseModel[PermissionRead, PermissionCreate]):
    id = None
    scope: Mapped[str] = mapped_column(String(length=20), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    user: Mapped['User'] = relationship()  # noqa: F821

    __system_audit__ = True
    __read_domain__ = PermissionRead
    __create_domain__ = PermissionCreate


class AccessRole(BaseModel[AccessRoleRead, AccessRoleCreate]):
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[NanoIdType] = mapped_column(ForeignKey('customer.id', ondelete='CASCADE'), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Relationships
    policy_assignments = relationship(
        'PolicyRoleAssignment', back_populates='access_role', cascade='all, delete-orphan'
    )
    permissions = relationship('AccessPolicy', secondary='policyroleassignment', back_populates='roles', viewonly=True)
    membership_assignments = relationship(
        'MembershipAssignment', back_populates='access_role', cascade='all, delete-orphan'
    )

    __pk_abbrev__ = ACCESS_ROLE_PK_ABBREV
    __system_audit__ = True
    __read_domain__ = AccessRoleRead
    __create_domain__ = AccessRoleCreate

    __table_args__ = (
        # Enforce unique access role names within a customer
        UniqueConstraint('customer_id', 'name', name='uq_access_role_name_per_customer'),
    )


class AccessPolicy(BaseModel[AccessPolicyRead, AccessPolicyCreate]):
    name: Mapped[str] = mapped_column(String(150))
    customer_id: Mapped[NanoIdType] = mapped_column(ForeignKey('customer.id', ondelete='CASCADE'), nullable=True)
    permission_type: Mapped[str] = mapped_column(
        String(50), comment=f"Permission types: {', '.join([p.value for p in PermissionTypeEnum])}"
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), comment=f"Resource types: {', '.join([r.value for r in ResourceTypeEnum])}"
    )
    resource_selector: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}',
        comment='Resource selector configuration to determine which resources this permission applies to',
    )
    effect: Mapped[str] = mapped_column(
        String(10),
        default=PermissionEffectEnum.ALLOW.value,
        server_default=f"'{PermissionEffectEnum.ALLOW.value}'",
        comment=f"Permission effect: {', '.join([e.value for e in PermissionEffectEnum])}",
    )

    # Relationships
    role_assignments = relationship('PolicyRoleAssignment', back_populates='policy', cascade='all, delete-orphan')
    roles = relationship('AccessRole', secondary='policyroleassignment', back_populates='permissions', viewonly=True)

    __pk_abbrev__ = ACCESS_POLICY_PK_ABBREV
    __system_audit__ = True
    __read_domain__ = AccessPolicyRead
    __create_domain__ = AccessPolicyCreate


class PolicyRoleAssignment(BaseModel[PolicyRoleAssignmentRead, PolicyRoleAssignmentCreate]):
    role_id: Mapped[NanoIdType] = mapped_column(ForeignKey('accessrole.id', ondelete='CASCADE'))
    policy_id: Mapped[NanoIdType] = mapped_column(ForeignKey('accesspolicy.id', ondelete='CASCADE'))

    # Relationships
    access_role = relationship('AccessRole', back_populates='policy_assignments')
    policy = relationship('AccessPolicy', back_populates='role_assignments')

    __pk_abbrev__ = POLICY_ROLE_ASSIGNMENT_PK_ABBREV
    __system_audit__ = True
    __read_domain__ = PolicyRoleAssignmentRead
    __create_domain__ = PolicyRoleAssignmentCreate

    __table_args__ = (
        # Ensure a policy can only be assigned to an access role once
        UniqueConstraint('policy_id', 'role_id', name='uq_policy_access_role'),
    )


class MembershipAssignment(BaseModel[MembershipAssignmentRead, MembershipAssignmentCreate]):
    """Association between a membership and an access role"""

    membership_id: Mapped[NanoIdType] = mapped_column(ForeignKey('membership.id', ondelete='CASCADE'))
    access_role_id: Mapped[NanoIdType] = mapped_column(ForeignKey('accessrole.id', ondelete='CASCADE'))

    # Relationships
    access_role = relationship('AccessRole', back_populates='membership_assignments')

    __pk_abbrev__ = MEMBERSHIP_ASSIGNMENT_PK_ABBREV
    __system_audit__ = True
    __read_domain__ = MembershipAssignmentRead
    __create_domain__ = MembershipAssignmentCreate

    __table_args__ = (
        # Ensure a membership can only be assigned to an access role once
        UniqueConstraint('membership_id', 'access_role_id', name='uq_membership_access_role'),
    )
