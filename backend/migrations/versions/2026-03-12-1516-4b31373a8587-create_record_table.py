"""create record table

Revision ID: 4b31373a8587
Revises: e0a6b2132790
Create Date: 2026-03-12 15:16:55.534968

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b31373a8587'
down_revision = 'e0a6b2132790'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('record',
    sa.Column('engineer_id', sa.String(length=50), nullable=False),
    sa.Column('customer_id', sa.String(length=50), nullable=False),
    sa.Column('record_type', sa.String(length=20), nullable=False),
    sa.Column('record_period', sa.String(length=20), nullable=False),
    sa.Column('record_scope', sa.String(length=20), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('previous_value', sa.Float(), nullable=True),
    sa.Column('record_date', sa.Date(), nullable=False),
    sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('rec')"), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('modified_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ),
    sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_record_customer_type_period', 'record', ['customer_id', 'record_type', 'record_period'], unique=False)
    op.create_index('idx_record_date', 'record', ['record_date'], unique=False)
    op.create_index('idx_record_engineer_type_period', 'record', ['engineer_id', 'record_type', 'record_period'], unique=False)
    op.create_index('idx_record_scope', 'record', ['record_scope'], unique=False)
    op.create_index(op.f('ix_record_customer_id'), 'record', ['customer_id'], unique=False)
    op.create_index(op.f('ix_record_engineer_id'), 'record', ['engineer_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_record_engineer_id'), table_name='record')
    op.drop_index(op.f('ix_record_customer_id'), table_name='record')
    op.drop_index('idx_record_scope', table_name='record')
    op.drop_index('idx_record_engineer_type_period', table_name='record')
    op.drop_index('idx_record_date', table_name='record')
    op.drop_index('idx_record_customer_type_period', table_name='record')
    op.drop_table('record')
