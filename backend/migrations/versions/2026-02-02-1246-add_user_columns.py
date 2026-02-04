"""add hashed_password and archived_at to user

Revision ID: add_user_cols
Revises: burn001
Create Date: 2026-02-02
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_user_cols'
down_revision = 'burn001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user', sa.Column('hashed_password', sa.String(), nullable=True))
    op.add_column('user', sa.Column('archived_at', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'archived_at')
    op.drop_column('user', 'hashed_password')
