"""Add rolled_up_at to usage table

Revision ID: e0a6b2132790
Revises: ghprlink001
Create Date: 2026-02-04 12:46:26.193411

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e0a6b2132790'
down_revision = 'ghprlink001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('usage', sa.Column('rolled_up_at', sa.DateTime(), nullable=True))
    op.create_index('idx_usage_rolled_up_at', 'usage', ['rolled_up_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_usage_rolled_up_at', table_name='usage')
    op.drop_column('usage', 'rolled_up_at')
