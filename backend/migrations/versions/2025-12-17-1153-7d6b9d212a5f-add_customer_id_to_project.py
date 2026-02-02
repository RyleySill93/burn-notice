"""add_customer_id_to_project

Revision ID: 7d6b9d212a5f
Revises: 2d2ed844b9a3
Create Date: 2025-12-17 11:53:04.349997

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '7d6b9d212a5f'
down_revision = '2d2ed844b9a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add customer_id as nullable first
    op.add_column('project', sa.Column('customer_id', sa.String(length=50), nullable=True))

    # Step 2: Migrate existing projects - get customer_id from user's first active membership
    op.execute("""
        UPDATE project p
        SET customer_id = (
            SELECT m.customer_id
            FROM membership m
            WHERE m.user_id = p.user_id
            AND m.is_active = true
            LIMIT 1
        )
        WHERE p.customer_id IS NULL AND p.user_id IS NOT NULL
    """)

    # Step 2b: Delete orphan projects that couldn't be migrated (users without memberships)
    # First delete related tasks
    op.execute("""
        DELETE FROM task WHERE project_id IN (
            SELECT id FROM project WHERE customer_id IS NULL
        )
    """)
    # Then delete related sections
    op.execute("""
        DELETE FROM section WHERE project_id IN (
            SELECT id FROM project WHERE customer_id IS NULL
        )
    """)
    # Finally delete orphan projects
    op.execute("""
        DELETE FROM project WHERE customer_id IS NULL
    """)

    # Step 3: Make customer_id non-nullable
    op.alter_column('project', 'customer_id', nullable=False)

    # Step 4: Make user_id nullable
    op.alter_column('project', 'user_id', existing_type=sa.VARCHAR(length=50), nullable=True)

    # Step 5: Update foreign key constraints
    op.drop_constraint('project_user_id_fkey', 'project', type_='foreignkey')
    op.create_foreign_key(
        'project_customer_id_fkey', 'project', 'customer', ['customer_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key('project_user_id_fkey', 'project', 'user', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # Reverse the process
    op.drop_constraint('project_user_id_fkey', 'project', type_='foreignkey')
    op.drop_constraint('project_customer_id_fkey', 'project', type_='foreignkey')
    op.create_foreign_key('project_user_id_fkey', 'project', 'user', ['user_id'], ['id'])
    op.alter_column('project', 'user_id', existing_type=sa.VARCHAR(length=50), nullable=False)
    op.drop_column('project', 'customer_id')
