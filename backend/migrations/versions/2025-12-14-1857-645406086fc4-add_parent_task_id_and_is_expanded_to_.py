"""Add parent_task_id to task

Revision ID: 645406086fc4
Revises: d3da8826f088
Create Date: 2025-12-14 18:57:52.164494

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '645406086fc4'
down_revision = 'd3da8826f088'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('task', sa.Column('parent_task_id', sa.String(length=50), nullable=True))
    op.create_foreign_key(None, 'task', 'task', ['parent_task_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'task', type_='foreignkey')
    op.drop_column('task', 'parent_task_id')
