"""remove_is_expanded_from_section

Revision ID: 2d2ed844b9a3
Revises: 645406086fc4
Create Date: 2025-12-14 19:15:41.244534

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '2d2ed844b9a3'
down_revision = '645406086fc4'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Only drop columns if they exist (handles partial migration states)
    if column_exists('section', 'is_expanded'):
        op.drop_column('section', 'is_expanded')
    if column_exists('task', 'is_expanded'):
        op.drop_column('task', 'is_expanded')


def downgrade() -> None:
    op.add_column(
        'task',
        sa.Column('is_expanded', sa.BOOLEAN(), autoincrement=False, nullable=False, server_default=sa.text('true')),
    )
    op.add_column(
        'section',
        sa.Column('is_expanded', sa.BOOLEAN(), autoincrement=False, nullable=False, server_default=sa.text('true')),
    )
