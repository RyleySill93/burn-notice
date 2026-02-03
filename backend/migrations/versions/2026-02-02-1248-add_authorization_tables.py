"""add authorization tables

Revision ID: add_auth_tables
Revises: add_user_cols
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_auth_tables'
down_revision = 'add_user_cols'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AccessRole table
    op.create_table(
        'accessrole',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('customer_id', sa.String(length=50), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'name', name='uq_access_role_name_per_customer'),
    )

    # AccessPolicy table
    op.create_table(
        'accesspolicy',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=True),
        sa.Column('permission_type', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_selector', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('effect', sa.String(length=10), nullable=False, server_default="'allow'"),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # PolicyRoleAssignment table
    op.create_table(
        'policyroleassignment',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('role_id', sa.String(length=50), nullable=False),
        sa.Column('policy_id', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['accessrole.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['policy_id'], ['accesspolicy.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('policy_id', 'role_id', name='uq_policy_access_role'),
    )

    # MembershipAssignment table
    op.create_table(
        'membershipassignment',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('membership_id', sa.String(length=50), nullable=False),
        sa.Column('access_role_id', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['membership_id'], ['membership.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['access_role_id'], ['accessrole.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('membership_id', 'access_role_id', name='uq_membership_access_role'),
    )


def downgrade() -> None:
    op.drop_table('membershipassignment')
    op.drop_table('policyroleassignment')
    op.drop_table('accesspolicy')
    op.drop_table('accessrole')
