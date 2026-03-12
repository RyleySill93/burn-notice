"""create medal table

Revision ID: a7c2e4f19b03
Revises: 4b31373a8587
Create Date: 2026-03-12 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c2e4f19b03'
down_revision = '4b31373a8587'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('medal',
    sa.Column('engineer_id', sa.String(length=50), nullable=False),
    sa.Column('customer_id', sa.String(length=50), nullable=False),
    sa.Column('medal_category', sa.String(length=20), nullable=False),
    sa.Column('medal_type', sa.String(length=20), nullable=False),
    sa.Column('metric_type', sa.String(length=20), nullable=False),
    sa.Column('period_type', sa.String(length=20), nullable=True),
    sa.Column('period_start', sa.Date(), nullable=True),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('mdl')"), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('modified_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ),
    sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_medal_customer_category', 'medal', ['customer_id', 'medal_category'], unique=False)
    op.create_index('idx_medal_engineer_category', 'medal', ['engineer_id', 'medal_category'], unique=False)
    op.create_index('idx_medal_period', 'medal', ['customer_id', 'period_type', 'period_start'], unique=False)
    op.create_index(op.f('ix_medal_customer_id'), 'medal', ['customer_id'], unique=False)
    op.create_index(op.f('ix_medal_engineer_id'), 'medal', ['engineer_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_medal_engineer_id'), table_name='medal')
    op.drop_index(op.f('ix_medal_customer_id'), table_name='medal')
    op.drop_index('idx_medal_period', table_name='medal')
    op.drop_index('idx_medal_engineer_category', table_name='medal')
    op.drop_index('idx_medal_customer_category', table_name='medal')
    op.drop_table('medal')
