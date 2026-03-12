"""add medal citation and awarded_by

Revision ID: b8d3f5a71c04
Revises: a7c2e4f19b03
Create Date: 2026-03-12 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8d3f5a71c04'
down_revision: Union[str, None] = 'a7c2e4f19b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('medal', sa.Column('citation', sa.Text(), nullable=True))
    op.add_column('medal', sa.Column('awarded_by_user_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_medal_awarded_by_user', 'medal', 'user', ['awarded_by_user_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_medal_awarded_by_user', 'medal', type_='foreignkey')
    op.drop_column('medal', 'awarded_by_user_id')
    op.drop_column('medal', 'citation')
