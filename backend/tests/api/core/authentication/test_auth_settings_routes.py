"""
Route tests for entity authentication settings endpoints.

These tests verify the CRUD operations for entity authentication settings,
including creating, reading, and updating auth methods, MFA settings, and
OIDC provider associations.
"""

from fastapi.testclient import TestClient

from src import settings
from src.core.authentication import (
    AuthenticationMethodEnum,
    CustomerAuthSettings,
    CustomerAuthSettingsCreate,
    MultiFactorMethodEnum,
)
from src.core.authentication.oidc.domains import OIDCProviderCreate
from src.core.authentication.oidc.models import OIDCProvider
from src.core.customer import Customer
from src.core.user import AuthenticatedUserRead


class TestCustomerAuthSettings:
    """
    Tests for customer authentication settings CRUD operations
    """

    def test_get_auth_settings_for_customer_without_settings(
        self,
        persistent_client: TestClient,
        customer_admin_user: AuthenticatedUserRead,
        customer,
    ):
        """Test getting auth settings for customer that has no settings configured"""
        client = persistent_client

        # Get auth token
        access_token = self._get_auth_token(client, customer_admin_user)

        # Get settings for customer with no configured settings
        response = client.get(
            f'{settings.API_PREFIX}auth/customer/{customer.id}/auth-settings',
            headers={'Authorization': f'Bearer {access_token}'},
        )

        assert response.status_code == 200
        data = response.json()
        # Should return empty/default settings
        assert 'enabledAuthMethods' in data
        assert 'mfaMethods' in data

    def test_create_auth_settings(
        self,
        persistent_client: TestClient,
        customer_admin_user: AuthenticatedUserRead,
        customer,
    ):
        """Test creating new auth settings for a customer"""
        client = persistent_client

        # Get auth token
        access_token = self._get_auth_token(client, customer_admin_user)

        # Create auth settings
        response = client.post(
            f'{settings.API_PREFIX}auth/customer/{customer.id}/auth-settings',
            headers={'Authorization': f'Bearer {access_token}'},
            json={
                'enabledAuthMethods': [
                    AuthenticationMethodEnum.PASSWORD.value,
                    AuthenticationMethodEnum.MAGIC_LINK.value,
                ],
                'mfaMethods': [MultiFactorMethodEnum.EMAIL.value],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'message' in data

        # Verify settings were created
        customer_settings = CustomerAuthSettings.get_or_none(customer_id=customer.id)
        assert customer_settings is not None
        assert AuthenticationMethodEnum.PASSWORD.value in customer_settings.enabled_auth_methods
        assert AuthenticationMethodEnum.MAGIC_LINK.value in customer_settings.enabled_auth_methods
        assert MultiFactorMethodEnum.EMAIL.value in customer_settings.mfa_methods

    def test_update_auth_settings(
        self,
        persistent_client: TestClient,
        customer_admin_user: AuthenticatedUserRead,
        customer: Customer,
    ):
        """Test updating existing auth settings"""
        client = persistent_client

        auth_settings_data = CustomerAuthSettingsCreate(
            customer_id=customer.id,
            enabled_auth_methods=[AuthenticationMethodEnum.PASSWORD.value],
            mfa_methods=[],
        )
        CustomerAuthSettings.create(auth_settings_data)

        # Get auth token
        access_token = self._get_auth_token(client, customer_admin_user)

        # Update settings
        response = client.post(
            f'{settings.API_PREFIX}auth/customer/{customer.id}/auth-settings',
            headers={'Authorization': f'Bearer {access_token}'},
            json={
                'enabledAuthMethods': [
                    AuthenticationMethodEnum.PASSWORD.value,
                    AuthenticationMethodEnum.MAGIC_LINK.value,
                ],
                'mfaMethods': [MultiFactorMethodEnum.TOTP.value],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        # Verify settings were updated
        customer_settings = CustomerAuthSettings.get_or_none(customer_id=customer.id)
        assert customer_settings is not None
        assert len(customer_settings.enabled_auth_methods) == 2
        assert MultiFactorMethodEnum.TOTP.value in customer_settings.mfa_methods

    def test_get_auth_settings_with_oidc_provider(
        self,
        persistent_client: TestClient,
        customer_admin_user: AuthenticatedUserRead,
        customer,
    ):
        """Test getting auth settings with OIDC provider configured"""
        client = persistent_client

        # Create OIDC provider
        oidc_provider = self._create_oidc_provider(
            display_name='Test SSO Provider',
            client_id='test-sso-client',
        )

        auth_settings_data = CustomerAuthSettingsCreate(
            customer_id=customer.id,
            enabled_auth_methods=[AuthenticationMethodEnum.OIDC.value],
            mfa_methods=[],
            oidc_provider_id=oidc_provider.id,
        )
        CustomerAuthSettings.create(auth_settings_data)

        # Get auth token
        access_token = self._get_auth_token(client, customer_admin_user)

        # Get settings
        response = client.get(
            f'{settings.API_PREFIX}auth/customer/{customer.id}/auth-settings',
            headers={'Authorization': f'Bearer {access_token}'},
        )

        assert response.status_code == 200
        data = response.json()
        assert 'oidcProviderId' in data
        assert data['oidcProviderId'] == oidc_provider.id
        assert 'oidcProviderName' in data
        assert data['oidcProviderName'] == oidc_provider.display_name

    def test_create_auth_settings_with_multiple_mfa_methods(
        self,
        persistent_client: TestClient,
        customer_admin_user: AuthenticatedUserRead,
        customer,
    ):
        """Test creating auth settings with multiple MFA methods"""
        client = persistent_client

        # Get auth token
        access_token = self._get_auth_token(client, customer_admin_user)

        # Create auth settings with multiple MFA methods
        response = client.post(
            f'{settings.API_PREFIX}auth/customer/{customer.id}/auth-settings',
            headers={'Authorization': f'Bearer {access_token}'},
            json={
                'enabledAuthMethods': [AuthenticationMethodEnum.PASSWORD.value],
                'mfaMethods': [
                    MultiFactorMethodEnum.EMAIL.value,
                    MultiFactorMethodEnum.TOTP.value,
                    MultiFactorMethodEnum.SMS.value,
                ],
            },
        )

        assert response.status_code == 200

        # Verify all MFA methods were saved
        customer_settings = CustomerAuthSettings.get_or_none(customer_id=customer.id)
        assert customer_settings is not None
        assert len(customer_settings.mfa_methods) == 3
        assert MultiFactorMethodEnum.EMAIL.value in customer_settings.mfa_methods
        assert MultiFactorMethodEnum.TOTP.value in customer_settings.mfa_methods
        assert MultiFactorMethodEnum.SMS.value in customer_settings.mfa_methods

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

    def _get_auth_token(self, client: TestClient, user: AuthenticatedUserRead) -> str:
        """Get an auth token for the user"""
        # Generate MFA token and then complete auth to get access token
        from src.core.authentication import AuthenticationService

        auth_service = AuthenticationService.factory()
        token_data = auth_service.create_auth_token(user_id=user.id, ip_address=None)
        return token_data.access_token
