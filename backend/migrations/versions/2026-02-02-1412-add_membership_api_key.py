"""Add api_key column to membership table

Revision ID: memkey001
Revises: 4f5a6b7c8d9e
Create Date: 2026-02-02
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'memkey001'
down_revision = 'add_auth_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('membership', sa.Column('api_key', sa.String(64), nullable=True))
    op.create_index('ix_membership_api_key', 'membership', ['api_key'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_membership_api_key', table_name='membership')
    op.drop_column('membership', 'api_key')
