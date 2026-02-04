"""Add github_pr_id to githubcommit table

Revision ID: ghprlink001
Revises: 1e681908b6c3
Create Date: 2026-02-04

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'ghprlink001'
down_revision = '1e681908b6c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('githubcommit', sa.Column('github_pr_id', sa.BigInteger(), nullable=True))
    op.create_index('idx_github_commit_pr_id', 'githubcommit', ['github_pr_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_github_commit_pr_id', table_name='githubcommit')
    op.drop_column('githubcommit', 'github_pr_id')
