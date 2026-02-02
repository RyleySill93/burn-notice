"""OIDC Service for handling OpenID Connect authentication flows."""

import base64
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import jwt
import requests
from fastapi import status
from loguru import logger

from src import settings
from src.common.exceptions import APIException
from src.common.nanoid import NanoIdType
from src.core.authentication.constants import AuthenticationMethodEnum
from src.core.authentication.domains import AuthenticationUrl
from src.core.authentication.models import CustomerAuthSettings
from src.core.authentication.oidc.domains import OIDCProviderCreate, OIDCProviderRead, OIDCProviderUserCreate
from src.core.authentication.oidc.exceptions import (
    MissingEnabledOIDCProvider,
    OIDCDiscoveryError,
    OIDCMissingClaimsError,
    OIDCStaffProviderMissing,
    OIDCTokenExchangeError,
    OIDCTokenValidationError,
    OIDCUserProvisionDisabled,
)
from src.core.authentication.oidc.models import OIDCProvider, OIDCProviderUser
from src.core.customer import CustomerService
from src.core.membership import MembershipService
from src.core.user import UserCreate, UserNotFound, UserRead, UserService
from src.network.cache.cache import Cache


class OIDCService:
    """Handle OIDC flows and token validation"""

    def __init__(self):
        self.jwks_cache = {}  # In-memory cache for public keys
        self.cache = Cache
        self.redirect_uri = f'{settings.FRONTEND_ORIGIN}/auth/oidc/callback'

    @classmethod
    def factory(cls) -> 'OIDCService':
        """Factory method to create OIDCService instance"""
        return cls()

    def get_provider_by_id(self, provider_id: NanoIdType) -> OIDCProviderRead:
        # Check if this is the staff provider by provider_id
        if provider_id == settings.STAFF_OIDC_PROVIDER_ID:
            return self.get_staff_provider()

        # Look up provider by ID
        provider = OIDCProvider.get_or_none(id=provider_id)
        if not provider:
            raise MissingEnabledOIDCProvider(message=f'No enabled OIDC provider found for provider_id: {provider_id}')
        return provider

    def get_provider_by_client_id(self, client_id: str) -> OIDCProviderRead:
        # Check if this is the staff provider by client_id
        if client_id == settings.STAFF_OIDC_CLIENT_ID:
            return self.get_staff_provider()

        # Look up provider by client_id
        provider = OIDCProvider.get_or_none(client_id=client_id)
        if not provider:
            raise MissingEnabledOIDCProvider(message=f'No enabled OIDC provider found for client_id: {client_id}')
        return provider

    def list_providers_by_default_role_id(self, role_id: NanoIdType) -> list[OIDCProviderRead]:
        oidc_providers = OIDCProvider.list(OIDCProvider.default_role_id == role_id)
        return oidc_providers

    def initialize_auth_flow_for_provider_id(self, provider_id: NanoIdType) -> AuthenticationUrl:
        provider = self.get_provider_by_id(provider_id)

        # Generate authorization URL with provider's internal ID encoded in state
        auth_url = self.get_authorization_url(redirect_uri=self.redirect_uri, provider=provider)

        return AuthenticationUrl(url=auth_url)

    def initialize_auth_flow_for_client_id(self, client_id: str) -> AuthenticationUrl:
        provider = self.get_provider_by_client_id(client_id)

        # Generate authorization URL with provider's internal ID encoded in state
        auth_url = self.get_authorization_url(redirect_uri=self.redirect_uri, provider=provider)

        return AuthenticationUrl(url=auth_url)

    def get_authorization_url(
        self,
        redirect_uri: str,
        provider: OIDCProviderRead,
    ) -> str:
        """Build authorization URL for IDP redirect including provider id in state"""
        # Generate state with provider_id encoded
        state_data = {'csrf': secrets.token_urlsafe(32), 'provider_id': provider.id}
        # Encode state data as base64 JSON
        state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode().rstrip('=')

        params = {
            'client_id': provider.client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'openid email profile offline_access',
            'state': state,
            'nonce': secrets.token_urlsafe(32),
        }

        return f'{provider.authorization_endpoint}?{urlencode(params)}'

    def exchange_code(self, provider: OIDCProviderRead, code: str) -> dict:
        """Exchange authorization code for tokens"""

        # Prepare authentication based on provider's preferred method
        # The EncryptedString field automatically decrypts when accessed
        client_secret = provider.client_secret

        if provider.client_auth_method == 'client_secret_basic':
            # Send credentials in Basic Auth header
            auth = (provider.client_id, client_secret)
            data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': self.redirect_uri}
            response = requests.post(provider.token_endpoint, data=data, auth=auth, timeout=30)
        else:
            # Default: client_secret_post - send credentials in POST body
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': provider.client_id,
                'client_secret': client_secret,
                'redirect_uri': self.redirect_uri,
            }
            response = requests.post(provider.token_endpoint, data=data, timeout=30)

        if response.status_code != 200:
            logger.error(f'Token exchange failed: {response.text}')
            raise OIDCTokenExchangeError(f'Token exchange failed: {response.text}')

        return response.json()

    def validate_id_token(self, id_token: str, provider: OIDCProviderRead) -> dict:
        """
        Validate and parse ID token using PyJWT

        Returns claims like:
        {
            'sub': 'user-id-at-idp',  # GUARANTEED - unique user ID at IDP
            'email': 'user@example.com',  # Usually present
            'name': 'John Doe',  # Optional
            'given_name': 'John',  # Optional
            'family_name': 'Doe',  # Optional
            'email_verified': True,  # Optional
            'aud': 'your-client-id',  # GUARANTEED - must match
            'iss': 'https://idp.com',  # GUARANTEED - must match expected
            'exp': 1234567890,  # GUARANTEED - expiration
            'iat': 1234567890,  # GUARANTEED - issued at
        }
        """

        # Get IDP's public keys
        jwks = self._get_jwks(provider)

        # PyJWT will validate:
        # - Signature using public key
        # - Expiration (exp claim)
        # - Audience (aud claim) matches our client_id
        # - Issuer (iss claim) matches expected
        try:
            # Convert JWKS to PyJWT format
            public_keys = {}
            for jwk_key in jwks.get('keys', []):
                kid = jwk_key.get('kid')
                if kid:
                    public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk_key))

            # Get the kid from the token header
            unverified_header = jwt.get_unverified_header(id_token)
            kid = unverified_header.get('kid')

            if not kid or kid not in public_keys:
                # Try without kid - some providers don't use it
                if len(public_keys) == 1:
                    key = list(public_keys.values())[0]
                else:
                    raise OIDCTokenValidationError('Unable to find appropriate key')
            else:
                key = public_keys[kid]

            # Validate the token
            claims = jwt.decode(
                id_token, key=key, algorithms=['RS256'], audience=provider.client_id, issuer=provider.issuer
            )

            # Ensure we have minimum required claims
            if 'email' not in claims and 'upn' not in claims:
                # Try to get email from userinfo endpoint if not in token
                userinfo = self._get_userinfo(provider, id_token)
                if userinfo and 'email' in userinfo:
                    claims['email'] = userinfo['email']
                else:
                    raise OIDCMissingClaimsError('No email in ID token or userinfo')

            # Normalize email claim (some IDPs use 'upn')
            if 'email' not in claims and 'upn' in claims:
                claims['email'] = claims['upn']

            return claims

        except jwt.ExpiredSignatureError:
            raise OIDCTokenValidationError('ID token has expired')
        except jwt.InvalidAudienceError:
            raise OIDCTokenValidationError('ID token audience mismatch')
        except jwt.InvalidIssuerError:
            raise OIDCTokenValidationError('ID token issuer mismatch')
        except jwt.InvalidSignatureError:
            raise OIDCTokenValidationError('ID token signature invalid')
        except Exception as e:
            logger.error(f'ID token validation error: {str(e)}')
            raise OIDCTokenValidationError(f'ID token validation failed: {str(e)}')

    def _get_userinfo(self, provider: OIDCProviderRead, access_token: str) -> Optional[Dict[str, Any]]:
        """Fetch user info from the userinfo endpoint"""
        if not provider.userinfo_endpoint:
            return None

        try:
            response = requests.get(
                provider.userinfo_endpoint, headers={'Authorization': f'Bearer {access_token}'}, timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f'Failed to fetch userinfo: {str(e)}')

        return None

    def _get_jwks(self, provider: OIDCProviderRead) -> dict:
        """Fetch and cache IDP's public keys"""

        # Check cache first
        cache_key = f'jwks:{provider.id}'
        cached = self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # Fetch JWKS from IDP
        try:
            response = requests.get(provider.jwks_uri, timeout=30)
            if response.status_code != 200:
                raise OIDCTokenValidationError('Failed to fetch JWKS')

            jwks = response.json()

            # Cache for 24 hours (keys rarely change)
            self.cache.set(cache_key, json.dumps(jwks), ex=86400)

            return jwks
        except Exception as e:
            logger.error(f'Failed to fetch JWKS: {str(e)}')
            raise OIDCTokenValidationError(f'Failed to fetch JWKS: {str(e)}')

    @classmethod
    def discover_endpoints(cls, discovery_url: str) -> Dict[str, Any]:
        """
        Fetch OIDC discovery document and extract endpoints

        Args:
            discovery_url: The .well-known/openid-configuration URL

        Returns:
            Dictionary with discovered endpoints
        """
        try:
            response = requests.get(discovery_url, timeout=30)
            if response.status_code != 200:
                raise OIDCDiscoveryError(f'Failed to fetch discovery document: {response.status_code}')

            discovery = response.json()

            # Extract key endpoints
            return {
                'issuer': discovery.get('issuer'),
                'authorization_endpoint': discovery.get('authorization_endpoint'),
                'token_endpoint': discovery.get('token_endpoint'),
                'userinfo_endpoint': discovery.get('userinfo_endpoint'),
                'jwks_uri': discovery.get('jwks_uri'),
                'end_session_endpoint': discovery.get('end_session_endpoint'),  # For logout
                'scopes_supported': discovery.get('scopes_supported', []),
                'response_types_supported': discovery.get('response_types_supported', []),
                'grant_types_supported': discovery.get('grant_types_supported', []),
                'token_endpoint_auth_methods_supported': discovery.get('token_endpoint_auth_methods_supported', []),
            }
        except requests.RequestException as e:
            logger.error(f'Failed to discover OIDC endpoints: {str(e)}')
            raise OIDCDiscoveryError(f'Failed to discover OIDC endpoints: {str(e)}')
        except json.JSONDecodeError as e:
            logger.error(f'Invalid discovery document: {str(e)}')
            raise OIDCDiscoveryError(f'Invalid discovery document: {str(e)}')

    def _generate_state(self) -> str:
        """Generate a secure random state parameter for CSRF protection"""
        return secrets.token_urlsafe(32)

    def validate_state(self, state: str, stored_state: str) -> bool:
        """Validate state parameter for CSRF protection"""
        return secrets.compare_digest(state, stored_state)

    @staticmethod
    def extract_name_from_claims(claims: dict) -> tuple[str, str]:
        """
        Extract first and last name from OIDC claims.
        Handles different provider claim formats.

        Returns:
            Tuple of (first_name, last_name)
        """
        # Standard OIDC claims
        first_name = claims.get('given_name', '')
        last_name = claims.get('family_name', '')

        # If standard claims not present, try to parse from 'name' claim (Azure AD, Auth0)
        if not first_name and not last_name and claims.get('name'):
            name_parts = claims['name'].strip().split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''

        return first_name, last_name

    def get_staff_provider(self) -> OIDCProviderRead:
        """
        Get staff OIDC provider configuration from environment variables.
        Ensures the shell database record exists for foreign key constraints.
        """
        if not all(
            [
                AuthenticationMethodEnum.OIDC.value in settings.STAFF_AUTHENTICATION_METHODS,
                settings.STAFF_OIDC_CLIENT_ID,
                settings.STAFF_OIDC_CLIENT_SECRET,
                settings.STAFF_OIDC_ISSUER,
                settings.STAFF_OIDC_AUTHORIZATION_ENDPOINT,
                settings.STAFF_OIDC_TOKEN_ENDPOINT,
                settings.STAFF_OIDC_JWKS_URI,
            ]
        ):
            raise OIDCStaffProviderMissing(message='Staff OIDC provider not configured in environment')

        # Ensure shell record exists in database for foreign key constraints
        existing = OIDCProvider.get_or_none(id=settings.STAFF_OIDC_PROVIDER_ID)
        if not existing:
            OIDCProvider.create(
                OIDCProviderCreate(
                    id=settings.STAFF_OIDC_PROVIDER_ID,
                    display_name='Staff SSO (Shell Record)',
                    client_id='placeholder',
                    client_secret='placeholder',
                    client_auth_method='client_secret_post',
                    issuer=settings.STAFF_OIDC_ISSUER,
                    authorization_endpoint=settings.STAFF_OIDC_AUTHORIZATION_ENDPOINT,
                    token_endpoint=settings.STAFF_OIDC_TOKEN_ENDPOINT,
                    userinfo_endpoint=settings.STAFF_OIDC_USERINFO_ENDPOINT,
                    jwks_uri=settings.STAFF_OIDC_JWKS_URI,
                    auto_create_users=True,
                )
            )

        return OIDCProviderRead(
            id=settings.STAFF_OIDC_PROVIDER_ID,
            display_name=f'Staff SSO ({settings.ENVIRONMENT})',
            client_id=settings.STAFF_OIDC_CLIENT_ID,
            client_secret=settings.STAFF_OIDC_CLIENT_SECRET,
            discovery_endpoint=None,
            client_auth_method='client_secret_post',
            issuer=settings.STAFF_OIDC_ISSUER,
            authorization_endpoint=settings.STAFF_OIDC_AUTHORIZATION_ENDPOINT,
            token_endpoint=settings.STAFF_OIDC_TOKEN_ENDPOINT,
            userinfo_endpoint=settings.STAFF_OIDC_USERINFO_ENDPOINT,
            jwks_uri=settings.STAFF_OIDC_JWKS_URI,
            auto_create_users=settings.STAFF_OIDC_AUTO_CREATE_USERS,
        )

    def authenticate_user(self, provider_id: str, code: str) -> tuple[UserRead, OIDCProviderRead, dict]:
        """
        Complete OIDC authentication flow:
        1. Get provider configuration
        2. Exchange code for tokens
        3. Validate ID token and extract claims
        4. Find or create user mapping

        Returns: (user, provider, claims)
        """
        # Get provider configuration
        provider = self.get_provider_by_id(provider_id)

        # Exchange code for tokens
        tokens = self.exchange_code(provider, code)

        # Validate ID token and extract claims
        claims = self.validate_id_token(tokens['id_token'], provider)
        email = claims.get('email', '').lower()
        external_user_id = claims['sub']

        # Log authentication attempt for debugging
        logger.info(
            f'OIDC authentication attempt - email={email}, '
            f'provider={provider.display_name}, '
            f'auto_create_users={provider.auto_create_users}'
        )

        # Find or create user
        user = self.find_or_create_user(
            provider=provider,
            email=email,
            external_user_id=external_user_id,
            claims=claims,
            idp_refresh_token=tokens.get('refresh_token'),
        )

        return user, provider, claims

    def find_or_create_user(
        self,
        provider: OIDCProviderRead,
        email: str,
        external_user_id: str,
        claims: dict,
        idp_refresh_token: str | None = None,
    ) -> UserRead:
        """Find existing user or create new one with OIDC mapping"""
        user_service = UserService.factory()

        # Try to find by existing mapping
        mapping = OIDCProviderUser.get_or_none(oidc_provider_id=provider.id, external_user_id=external_user_id)

        if mapping:
            # Update the IDP refresh token if we got a new one
            if idp_refresh_token:
                OIDCProviderUser.update(
                    mapping.id,
                    idp_refresh_token=idp_refresh_token,
                    last_idp_validation=datetime.now(tz=timezone.utc),
                    idp_user_info=claims,  # Update stored claims
                )
            return user_service.get_user_for_id(mapping.user_id)

        # Try to find by email
        try:
            user = user_service.get_user_for_email(email)
            # Create mapping for future lookups
            OIDCProviderUser.create(
                OIDCProviderUserCreate(
                    user_id=user.id,
                    oidc_provider_id=provider.id,
                    external_user_id=external_user_id,
                    external_email=email,
                    idp_refresh_token=idp_refresh_token,
                    last_idp_validation=datetime.now(tz=timezone.utc) if idp_refresh_token else None,
                    idp_user_info=claims,  # Store initial claims
                )
            )
            return user
        except UserNotFound:
            # For staff provider, try alternative email lookups before creating new user
            is_staff_provider = provider.id == settings.STAFF_OIDC_PROVIDER_ID
            if is_staff_provider:
                try:
                    # Look for staff user by provider email (for legacy users these are hard coded in Okta)
                    existing_staff_user = user_service.get_user_for_email(email)
                except UserNotFound:
                    existing_staff_user = None
                    pass

                if existing_staff_user:
                    logger.info(
                        f'Staff OIDC: Mapped {email} to existing user {existing_staff_user.email} '
                        f'(id: {existing_staff_user.id})'
                    )
                    # Create oidc user mapping for this
                    OIDCProviderUser.create(
                        OIDCProviderUserCreate(
                            user_id=existing_staff_user.id,
                            oidc_provider_id=provider.id,
                            external_user_id=external_user_id,
                            external_email=email,
                            idp_refresh_token=idp_refresh_token,
                            last_idp_validation=datetime.now(tz=timezone.utc) if idp_refresh_token else None,
                            idp_user_info=claims,
                        )
                    )
                    return existing_staff_user

            # No existing user found - check auto-provision settings
            if provider.auto_create_users:
                # Auto-provision new user
                return self._auto_provision_user(
                    provider=provider,
                    email=email,
                    external_user_id=external_user_id,
                    claims=claims,
                    idp_refresh_token=idp_refresh_token,
                )
            else:
                raise OIDCUserProvisionDisabled(
                    f'User with email "{email}" does not exist in the system. '
                    f'Auto-provisioning is disabled for {provider.display_name}. '
                    f'Contact your administrator to create your account.'
                )

    def _auto_provision_user(
        self,
        provider: OIDCProviderRead,
        email: str,
        external_user_id: str,
        claims: dict,
        idp_refresh_token: str | None = None,
    ) -> UserRead:
        """Auto-provision a new user with OIDC"""
        from src.core.service import CoreService

        core_service = CoreService.factory()
        user_service = UserService.factory()

        # Check if this is the staff provider
        is_staff_provider = provider.id == settings.STAFF_OIDC_PROVIDER_ID

        # Extract names from claims
        first_name, last_name = self.extract_name_from_claims(claims)

        if is_staff_provider:
            # Create staff user
            user = core_service.create_staff_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            user_service.activate_user(user_id=user.id)
        else:
            # Create regular user
            user = user_service.create_user(
                UserCreate(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
            )

            # Activate the user immediately since they've authenticated via OIDC
            user_service.activate_user(user_id=user.id)

            # Find customer that uses this provider and create membership
            customer_settings = CustomerAuthSettings.get_or_none(oidc_provider_id=provider.id)
            if customer_settings:
                membership_service = MembershipService.factory()

                # Create customer membership since entities are now customers
                customer_service = CustomerService.factory()
                # Import here to avoid circular imports
                from src.core.authorization import AccessControlService

                access_control_service = AccessControlService.factory()

                # Get the customer
                customer = customer_service.get_for_id(customer_settings.customer_id)
                # Use the default_role_id from the provider if set
                role_id = provider.default_role_id

                # Create customer membership
                membership = membership_service.create_customer_membership(user_id=user.id, customer_id=customer.id)
                if not role_id:
                    # Fallback to granting admin access if no default role is configured
                    access_control_service.grant_customer_admin_access(
                        membership_id=membership.id,
                        customer_id=customer.id,
                        customer_name=customer.name,
                    )
                else:
                    # Assign the configured default role
                    access_control_service.assign_role_to_membership(membership_id=membership.id, role_id=role_id)

        # Create mapping for both staff and regular users
        OIDCProviderUser.create(
            OIDCProviderUserCreate(
                user_id=user.id,
                oidc_provider_id=provider.id,
                external_user_id=external_user_id,
                external_email=email,
                idp_refresh_token=idp_refresh_token,
                last_idp_validation=datetime.now(tz=timezone.utc) if idp_refresh_token else None,
                idp_user_info=claims,  # Store initial claims
            )
        )

        return user

    def validate_user_on_refresh(self, user_id: str, oidc_provider_id: str) -> None:
        """
        Validate that an OIDC user still has valid access at the IDP
        by attempting to refresh their IDP token.
        """
        # Get the specific mapping for this provider
        mapping = OIDCProviderUser.get_or_none(user_id=user_id, oidc_provider_id=oidc_provider_id)

        if not mapping or not mapping.idp_refresh_token:
            # No refresh token stored, can't validate
            logger.warning(f'No IDP refresh token for user {user_id} provider {oidc_provider_id}')
            return

        # Get the provider
        if oidc_provider_id == settings.STAFF_OIDC_PROVIDER_ID:
            # Virtual staff provider
            provider = self.get_staff_provider()
        else:
            # Regular provider from database
            provider = OIDCProvider.get_or_none(id=oidc_provider_id)
            if not provider:
                logger.error(f'OIDC provider {oidc_provider_id} not found')
                # Force re-authentication
                raise APIException(
                    code=status.HTTP_403_FORBIDDEN,
                    message='OIDC provider removed',
                )

        # Try to refresh the IDP token
        try:
            response = requests.post(
                provider.token_endpoint,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': mapping.idp_refresh_token,
                    'client_id': provider.client_id,
                    'client_secret': provider.client_secret,
                },
                timeout=5,
            )

            if response.status_code == 200:
                # Success! User is still valid at IDP
                tokens = response.json()

                # Update stored refresh token and validation time
                OIDCProviderUser.update(
                    mapping.id,
                    idp_refresh_token=tokens.get('refresh_token', mapping.idp_refresh_token),
                    last_idp_validation=datetime.now(tz=timezone.utc),
                    idp_user_info=tokens,  # Store the full token response for audit
                )
            else:
                # IDP rejected refresh - user revoked or token expired?
                logger.warning(f'IDP token refresh failed for user {user_id}: {response.status_code}')

                # Clear the invalid refresh token
                OIDCProviderUser.update(
                    mapping.id,
                    idp_refresh_token=None,
                )

                # Force re-authentication
                raise APIException(
                    code=status.HTTP_403_FORBIDDEN,
                    message='SSO session expired. Please login again.',
                )

        except requests.RequestException as e:
            # Network error - log but don't block user
            logger.error(f'Failed to validate OIDC user {user_id}: {e}')
            # Continue - don't block on network issues, this would make application unusable in the event of IDP outages
