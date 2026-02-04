"""add remaining auth models

Revision ID: add_auth_models
Revises: add_auth_tables
Create Date: 2026-02-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, INET, UUID

# revision identifiers, used by Alembic.
revision = 'add_auth_models'
down_revision = 'add_auth_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # OIDCProvider table (needed for foreign key in customerauthsettings)
    op.create_table(
        'oidcprovider',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=True),
        sa.Column('client_id', sa.String(length=255), nullable=False),
        sa.Column('client_secret', sa.String(length=255), nullable=True),
        sa.Column('issuer_url', sa.String(length=500), nullable=False),
        sa.Column('authorization_endpoint', sa.String(length=500), nullable=True),
        sa.Column('token_endpoint', sa.String(length=500), nullable=True),
        sa.Column('userinfo_endpoint', sa.String(length=500), nullable=True),
        sa.Column('jwks_uri', sa.String(length=500), nullable=True),
        sa.Column('scopes', ARRAY(sa.String), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # CustomerAuthSettings table
    op.create_table(
        'customerauthsettings',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('enabled_auth_methods', ARRAY(sa.String), nullable=True),
        sa.Column('mfa_methods', ARRAY(sa.String), nullable=True),
        sa.Column('ip_whitelist', ARRAY(INET), nullable=True),
        sa.Column('token_refresh_frequency', sa.Integer(), nullable=True, default=900),
        sa.Column('oidc_provider_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['oidc_provider_id'], ['oidcprovider.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ChallengeToken table
    op.create_table(
        'challengetoken',
        sa.Column('jwt_id', UUID(as_uuid=True), nullable=False),
        sa.Column('expiration_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('jwt_id'),
    )

    # MfaAuthCode table
    op.create_table(
        'mfaauthcode',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('expiration_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    # MFASecret table
    op.create_table(
        'mfasecret',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('mfa_method', sa.String(length=20), nullable=False),
        sa.Column('secret', sa.String(), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('verification_attempts', sa.Integer(), default=0),
        sa.Column('backup_codes', ARRAY(sa.String), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('mfasecret')
    op.drop_table('mfaauthcode')
    op.drop_table('challengetoken')
    op.drop_table('customerauthsettings')
    op.drop_table('oidcprovider')
