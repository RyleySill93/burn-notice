"""Add GitHub integration tables

Revision ID: 1e681908b6c3
Revises: cost001
Create Date: 2026-02-03 23:04:35.055448

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1e681908b6c3'
down_revision = 'cost001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GitHub Commit table
    op.create_table(
        'githubcommit',
        sa.Column('engineer_id', sa.String(length=50), nullable=False),
        sa.Column('github_commit_sha', sa.String(length=40), nullable=False),
        sa.Column('repo_full_name', sa.String(length=200), nullable=False),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('lines_added', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lines_removed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('committed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('ghcmt')"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_github_commit_committed_at', 'githubcommit', ['committed_at'], unique=False)
    op.create_index('idx_github_commit_engineer_sha', 'githubcommit', ['engineer_id', 'github_commit_sha'], unique=True)
    op.create_index(op.f('ix_githubcommit_engineer_id'), 'githubcommit', ['engineer_id'], unique=False)

    # GitHub Credential table
    op.create_table(
        'githubcredential',
        sa.Column('engineer_id', sa.String(length=50), nullable=False),
        sa.Column('github_user_id', sa.String(length=50), nullable=False),
        sa.Column('github_username', sa.String(length=100), nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),  # EncryptedString stored as String
        sa.Column('scope', sa.String(length=500), nullable=True),
        sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('ghcred')"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engineer_id'),
    )
    op.create_index('idx_github_credential_engineer', 'githubcredential', ['engineer_id'], unique=True)

    # GitHub Daily table
    op.create_table(
        'githubdaily',
        sa.Column('engineer_id', sa.String(length=50), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('commits_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lines_added', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('lines_removed', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('prs_merged', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prs_reviewed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('review_comments', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('ghd')"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_github_daily_date', 'githubdaily', ['date'], unique=False)
    op.create_index('idx_github_daily_engineer_date', 'githubdaily', ['engineer_id', 'date'], unique=True)

    # GitHub Pull Request table
    op.create_table(
        'githubpullrequest',
        sa.Column('engineer_id', sa.String(length=50), nullable=False),
        sa.Column('github_pr_id', sa.BigInteger(), nullable=False),
        sa.Column('github_pr_number', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(length=200), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False),
        sa.Column('is_author', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_reviewer', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lines_added', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lines_removed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('review_comments_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.String(length=50), server_default=sa.text("gen_nanoid('ghpr')"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['engineer.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_github_pr_engineer_pr',
        'githubpullrequest',
        ['engineer_id', 'github_pr_id', 'is_author', 'is_reviewer'],
        unique=True,
    )
    op.create_index('idx_github_pr_merged_at', 'githubpullrequest', ['merged_at'], unique=False)
    op.create_index(op.f('ix_githubpullrequest_engineer_id'), 'githubpullrequest', ['engineer_id'], unique=False)


def downgrade() -> None:
    # Drop GitHub Pull Request table
    op.drop_index(op.f('ix_githubpullrequest_engineer_id'), table_name='githubpullrequest')
    op.drop_index('idx_github_pr_merged_at', table_name='githubpullrequest')
    op.drop_index('idx_github_pr_engineer_pr', table_name='githubpullrequest')
    op.drop_table('githubpullrequest')

    # Drop GitHub Daily table
    op.drop_index('idx_github_daily_engineer_date', table_name='githubdaily')
    op.drop_index('idx_github_daily_date', table_name='githubdaily')
    op.drop_table('githubdaily')

    # Drop GitHub Credential table
    op.drop_index('idx_github_credential_engineer', table_name='githubcredential')
    op.drop_table('githubcredential')

    # Drop GitHub Commit table
    op.drop_index(op.f('ix_githubcommit_engineer_id'), table_name='githubcommit')
    op.drop_index('idx_github_commit_engineer_sha', table_name='githubcommit')
    op.drop_index('idx_github_commit_committed_at', table_name='githubcommit')
    op.drop_table('githubcommit')
