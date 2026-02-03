"""Add TelemetryEvent table for full OTEL capture

Revision ID: cf71ca0df2c3
Revises: add_invitation
Create Date: 2026-02-02 21:19:05.772563

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'cf71ca0df2c3'
down_revision = 'add_invitation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('telemetryevent',
        sa.Column('engineer_id', sa.String(length=50), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('metric_name', sa.String(length=200), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('tokens_input', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_output', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_read_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_creation_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=True),
        sa.Column('tool_name', sa.String(length=100), nullable=True),
        sa.Column('tool_result', sa.String(length=50), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('time_to_first_token_ms', sa.Integer(), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resource_attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scope_attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('data_point_attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('tel')"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_telemetry_engineer_created', 'telemetryevent', ['engineer_id', 'created_at'], unique=False)
    op.create_index('idx_telemetry_metric_name', 'telemetryevent', ['metric_name'], unique=False)
    op.create_index('idx_telemetry_model', 'telemetryevent', ['model'], unique=False)
    op.create_index('idx_telemetry_session', 'telemetryevent', ['session_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_telemetryevent_engineer_id'), 'telemetryevent', ['engineer_id'], unique=False)
    op.create_index(op.f('ix_telemetryevent_session_id'), 'telemetryevent', ['session_id'], unique=False)
    op.create_index(op.f('ix_telemetryevent_tool_name'), 'telemetryevent', ['tool_name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_telemetryevent_tool_name'), table_name='telemetryevent')
    op.drop_index(op.f('ix_telemetryevent_session_id'), table_name='telemetryevent')
    op.drop_index(op.f('ix_telemetryevent_engineer_id'), table_name='telemetryevent')
    op.drop_index('idx_telemetry_session', table_name='telemetryevent')
    op.drop_index('idx_telemetry_model', table_name='telemetryevent')
    op.drop_index('idx_telemetry_metric_name', table_name='telemetryevent')
    op.drop_index('idx_telemetry_engineer_created', table_name='telemetryevent')
    op.drop_table('telemetryevent')
