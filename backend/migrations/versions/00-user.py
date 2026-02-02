"""

Revision ID: aba94e302521
Revises:
Create Date: 2023-06-15 12:39:17.635318

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'x3441dqa3kpp'
down_revision = '533d9fc57bb8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user',
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('user')"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.audit_table('user', True)
    op.create_table(
        'permission',
        sa.Column('scope', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('scope', 'user_id'),
    )
    op.audit_table('permission', True)
    # ### end Alembic commands ###


def downgrade() -> None:
    op.audit_table('user', False)
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
