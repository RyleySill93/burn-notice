"""Add invitation table

Revision ID: add_invitation
Revises: memkey001
Create Date: 2026-02-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_invitation'
down_revision = 'memkey001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'invitation',
        sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('invt')"), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('invited_by_user_id', sa.String(length=50), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('project_permissions', JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('message', sa.String(length=1000), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_invitation_email', 'invitation', ['email'], unique=False)
    op.create_index('ix_invitation_token', 'invitation', ['token'], unique=True)
    op.create_index(
        'ix_invitation_email_customer_status', 'invitation', ['email', 'customer_id', 'status'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_invitation_email_customer_status', table_name='invitation')
    op.drop_index('ix_invitation_token', table_name='invitation')
    op.drop_index('ix_invitation_email', table_name='invitation')
    op.drop_table('invitation')
