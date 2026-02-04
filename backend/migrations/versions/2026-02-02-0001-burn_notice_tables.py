"""burn-notice tables: engineer, usage, usage_daily

Revision ID: burn001
Revises: None
Create Date: 2026-02-02
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'burn001'
down_revision = 'd71b24224f51'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Customer table (teams)
    op.create_table(
        'customer',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Membership table (user-team relationship)
    op.create_table(
        'membership',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'user_id'),
    )

    # Engineer table
    op.create_table(
        'engineer',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=200), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_engineer_customer_id', 'engineer', ['customer_id'])
    op.create_index('idx_engineer_customer_external', 'engineer', ['customer_id', 'external_id'], unique=True)

    # Usage table (raw events)
    op.create_table(
        'usage',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('engineer_id', sa.String(length=50), nullable=False),
        sa.Column('tokens_input', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_output', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_usage_engineer_created', 'usage', ['engineer_id', 'created_at'])

    # UsageDaily table (pre-aggregated)
    op.create_table(
        'usagedaily',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('engineer_id', sa.String(length=50), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('total_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tokens_input', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tokens_output', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('session_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_usage_daily_engineer_date', 'usagedaily', ['engineer_id', 'date'], unique=True)
    op.create_index('idx_usage_daily_date', 'usagedaily', ['date'])


def downgrade() -> None:
    op.drop_table('usagedaily')
    op.drop_table('usage')
    op.drop_table('engineer')
    op.drop_table('membership')
    op.drop_table('customer')
