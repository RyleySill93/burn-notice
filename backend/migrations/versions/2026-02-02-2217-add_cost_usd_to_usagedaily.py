"""Add cost_usd column to usagedaily table

Revision ID: cost001
Revises: cf71ca0df2c3
Create Date: 2026-02-02
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'cost001'
down_revision = 'cf71ca0df2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'usagedaily',
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
    )


def downgrade() -> None:
    op.drop_column('usagedaily', 'cost_usd')
