"""
Route tests for OIDC authentication endpoints.

These tests verify the OIDC routing and error handling logic by mocking
only the external OAuth provider interactions (token exchange, userinfo).
The internal OIDC service logic runs normally.
"""

import base64
import json

from fastapi.testclient import TestClient

from src import settings
from src.core.authentication.oidc.domains import OIDCProviderCreate
from src.core.authentication.oidc.models import OIDCProvider


class TestOIDCInitiateLogin:
    """
    Tests for OIDC login initiation endpoints
    """

    def test_initiate_login_by_provider_id_returns_auth_url(
        self,
        persistent_client: TestClient,
    ):
        """Test that initiating OIDC login returns a valid authorization URL"""
        client = persistent_client

        # Create an enabled OIDC provider
        provider = self._create_oidc_provider(
            display_name='Test IdP',
            client_id='test-client-id',
        )

        response = client.get(f'{settings.API_PREFIX}auth/oidc/{provider.id}/login')

        assert response.status_code == 200
        data = response.json()
        assert 'url' in data
        # The URL should contain the authorization endpoint
        assert provider.authorization_endpoint in data['url']
        assert provider.client_id in data['url']

    def test_initiate_login_with_nonexistent_provider_fails(
        self,
        persistent_client: TestClient,
    ):
        """Test that nonexistent provider returns 404"""
        client = persistent_client

        fake_provider_id = OIDCProvider.generate_id()
        response = client.get(f'{settings.API_PREFIX}auth/oidc/{fake_provider_id}/login')

        assert response.status_code == 404

    def test_initiate_login_by_client_id_returns_auth_url(
        self,
        persistent_client: TestClient,
    ):
        """Test initiating OIDC login by OAuth client ID (IdP-initiated SSO)"""
        client = persistent_client

        # Create an enabled OIDC provider
        provider = self._create_oidc_provider(
            display_name='Test IdP',
            client_id='test-sso-client-id',
        )

        response = client.get(f'{settings.API_PREFIX}auth/oidc/initiate/{provider.client_id}/login')

        assert response.status_code == 200
        data = response.json()
        assert 'url' in data
        assert provider.authorization_endpoint in data['url']

    def _create_oidc_provider(
        self,
        display_name: str,
        client_id: str,
    ) -> OIDCProvider:
        """Create an OIDC provider for testing"""
        provider_data = OIDCProviderCreate(
            id=OIDCProvider.generate_id(),
            display_name=display_name,
            client_id=client_id,
            client_secret='test-client-secret',
            discovery_endpoint='https://test-idp.example.com/.well-known/openid-configuration',
            issuer='https://test-idp.example.com',
            authorization_endpoint='https://test-idp.example.com/authorize',
            token_endpoint='https://test-idp.example.com/token',
            userinfo_endpoint='https://test-idp.example.com/userinfo',
            jwks_uri='https://test-idp.example.com/.well-known/jwks.json',
            client_auth_method='client_secret_post',
            auto_create_users=True,
        )

        return OIDCProvider.create(provider_data)


class TestOIDCCallback:
    """
    Tests for OIDC callback endpoint

    Note: Full callback testing with actual OAuth flow requires mocking the entire
    OAuth provider (token exchange, ID token validation, JWKS, etc.). These tests
    focus on routing and error handling. Full integration tests should be done
    with real OAuth providers or comprehensive mocking frameworks.
    """

    def test_callback_with_invalid_state_fails(
        self,
        persistent_client: TestClient,
    ):
        """Test that callback fails with invalid state parameter"""
        client = persistent_client

        response = client.get(
            f'{settings.API_PREFIX}auth/oidc/callback',
            params={
                'code': 'mock_code',
                'state': 'invalid-state-value',
            },
        )

        assert response.status_code == 400
        error_msg = response.json().get('message') or response.json().get('detail', '')
        assert 'invalid state' in str(error_msg).lower()

    def test_callback_with_missing_state_fails(
        self,
        persistent_client: TestClient,
    ):
        """Test that callback fails when state is missing"""
        client = persistent_client

        response = client.get(
            f'{settings.API_PREFIX}auth/oidc/callback',
            params={
                'code': 'mock_code',
                # Missing state parameter
            },
        )

        assert response.status_code == 422  # FastAPI validation error

    # Note: Callback tests with valid OAuth codes require extensive mocking of:
    # - Token exchange with OAuth provider
    # - ID token validation (JWT verification, JWKS retrieval)
    # - User provisioning logic
    #
    # These are better tested as:
    # 1. Unit tests for the OIDCService methods
    # 2. Integration tests with mock OAuth servers
    # 3. E2E tests with real OAuth providers in staging
    #
    # Route-level tests focus on error handling and validation above.

    def _create_oidc_provider(
        self,
        display_name: str,
        client_id: str,
        auto_create_users: bool = True,
    ) -> OIDCProvider:
        """Create an OIDC provider for testing"""
        provider_data = OIDCProviderCreate(
            id=OIDCProvider.generate_id(),
            display_name=display_name,
            client_id=client_id,
            client_secret='test-client-secret',
            discovery_endpoint='https://test-idp.example.com/.well-known/openid-configuration',
            issuer='https://test-idp.example.com',
            authorization_endpoint='https://test-idp.example.com/authorize',
            token_endpoint='https://test-idp.example.com/token',
            userinfo_endpoint='https://test-idp.example.com/userinfo',
            jwks_uri='https://test-idp.example.com/.well-known/jwks.json',
            client_auth_method='client_secret_post',
            auto_create_users=auto_create_users,
        )

        return OIDCProvider.create(provider_data)

    @staticmethod
    def _create_state(provider_id: str) -> str:
        """Create a valid state parameter for OIDC flow"""
        state_data = {'provider_id': provider_id}
        state_json = json.dumps(state_data)
        # Base64 encode without padding (as the callback expects)
        return base64.urlsafe_b64encode(state_json.encode()).decode().rstrip('=')
