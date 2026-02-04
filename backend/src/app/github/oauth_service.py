"""GitHub OAuth Service for handling OAuth 2.0 authentication flows."""

import secrets
from typing import Any
from urllib.parse import urlencode

import requests
from loguru import logger

from src import settings
from src.app.github.domains import (
    GitHubAuthorizationUrl,
    GitHubConnectionStatus,
    GitHubCredentialCreate,
)
from src.app.github.exceptions import (
    GitHubOAuthError,
    GitHubOAuthStateExpired,
)
from src.app.github.models import GitHubCredential
from src.network.cache.cache import Cache


class GitHubOAuthService:
    """Handle GitHub OAuth flows for engineer GitHub integration."""

    # GitHub OAuth endpoints
    GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
    GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
    GITHUB_USER_URL = 'https://api.github.com/user'

    # OAuth scopes needed for GitHub data
    SCOPES = 'read:user repo'

    # State TTL in seconds (5 minutes)
    STATE_TTL = 300

    def __init__(self):
        self.cache = Cache

    @classmethod
    def factory(cls) -> 'GitHubOAuthService':
        """Factory method to create GitHubOAuthService instance."""
        return cls()

    def get_authorization_url(self, engineer_id: str) -> GitHubAuthorizationUrl:
        """
        Generate GitHub OAuth authorization URL with CSRF state.

        Args:
            engineer_id: The engineer ID to associate with this OAuth flow

        Returns:
            GitHubAuthorizationUrl with the authorization URL
        """
        if not settings.GITHUB_CLIENT_ID:
            raise GitHubOAuthError('GitHub OAuth not configured: GITHUB_CLIENT_ID missing')

        # Generate secure random state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state -> engineer_id mapping in Redis with TTL
        cache_key = f'github_oauth_state:{state}'
        self.cache.set(cache_key, engineer_id, ex=self.STATE_TTL)

        # Build authorization URL
        params = {
            'client_id': settings.GITHUB_CLIENT_ID,
            'redirect_uri': settings.GITHUB_OAUTH_REDIRECT_URI,
            'scope': self.SCOPES,
            'state': state,
        }

        authorization_url = f'{self.GITHUB_AUTHORIZE_URL}?{urlencode(params)}'
        logger.info('Generated GitHub OAuth URL', engineer_id=engineer_id)

        return GitHubAuthorizationUrl(authorization_url=authorization_url)

    def exchange_code(self, code: str, state: str) -> tuple[str, dict[str, Any], str, str]:
        """
        Exchange authorization code for access token.

        Args:
            code: The authorization code from GitHub
            state: The state parameter for CSRF verification

        Returns:
            Tuple of (engineer_id, github_user_info, access_token, scope)

        Raises:
            GitHubOAuthStateExpired: If state not found in cache
            GitHubOAuthStateMismatch: If state validation fails
            GitHubOAuthError: If token exchange fails
        """
        # Validate state and get engineer_id
        cache_key = f'github_oauth_state:{state}'
        engineer_id = self.cache.get(cache_key)

        if not engineer_id:
            raise GitHubOAuthStateExpired('OAuth state expired or invalid. Please try connecting again.')

        # Delete state from cache (one-time use)
        self.cache.delete(cache_key)

        # Exchange code for access token
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise GitHubOAuthError('GitHub OAuth not configured')

        response = requests.post(
            self.GITHUB_TOKEN_URL,
            data={
                'client_id': settings.GITHUB_CLIENT_ID,
                'client_secret': settings.GITHUB_CLIENT_SECRET,
                'code': code,
                'redirect_uri': settings.GITHUB_OAUTH_REDIRECT_URI,
            },
            headers={'Accept': 'application/json'},
            timeout=30,
        )

        if response.status_code != 200:
            logger.error('GitHub token exchange failed', status=response.status_code, response=response.text)
            raise GitHubOAuthError(f'Token exchange failed: {response.status_code}')

        token_data = response.json()

        if 'error' in token_data:
            logger.error(
                'GitHub OAuth error', error=token_data.get('error'), description=token_data.get('error_description')
            )
            raise GitHubOAuthError(token_data.get('error_description', token_data.get('error')))

        access_token = token_data.get('access_token')
        if not access_token:
            raise GitHubOAuthError('No access token in response')

        scope = token_data.get('scope', '')

        # Get user info from GitHub
        user_info = self.get_user_info(access_token)

        logger.info(
            'GitHub OAuth exchange successful',
            engineer_id=engineer_id,
            github_username=user_info.get('login'),
        )

        return engineer_id, user_info, access_token, scope

    def complete_oauth_callback(self, code: str, state: str) -> GitHubConnectionStatus:
        """
        Complete the OAuth callback flow: exchange code, save credential, return status.

        This is the single entry point for handling OAuth callbacks from the router.

        Args:
            code: The authorization code from GitHub
            state: The state parameter for CSRF verification

        Returns:
            GitHubConnectionStatus with connection details

        Raises:
            GitHubOAuthStateExpired: If state not found in cache
            GitHubOAuthError: If token exchange fails
        """
        engineer_id, user_info, access_token, scope = self.exchange_code(code, state)

        self.save_credential(
            engineer_id=engineer_id,
            access_token=access_token,
            github_user=user_info,
            scope=scope,
        )

        return self.get_connection_status(engineer_id)

    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """
        Fetch GitHub user details using access token.

        Args:
            access_token: GitHub OAuth access token

        Returns:
            GitHub user info dictionary

        Raises:
            GitHubOAuthError: If user info fetch fails
        """
        response = requests.get(
            self.GITHUB_USER_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
            },
            timeout=30,
        )

        if response.status_code != 200:
            logger.error('GitHub user info fetch failed', status=response.status_code)
            raise GitHubOAuthError(f'Failed to fetch user info: {response.status_code}')

        return response.json()

    def save_credential(
        self,
        engineer_id: str,
        access_token: str,
        github_user: dict[str, Any],
        scope: str | None = None,
    ) -> GitHubCredential:
        """
        Save or update GitHub credentials for an engineer.

        Args:
            engineer_id: The engineer ID
            access_token: GitHub OAuth access token (will be encrypted)
            github_user: GitHub user info from API
            scope: OAuth scopes granted

        Returns:
            GitHubCredential domain object
        """
        github_user_id = str(github_user['id'])
        github_username = github_user['login']

        # Check if credential already exists
        existing = GitHubCredential.get_or_none(engineer_id=engineer_id)

        if existing:
            # Update existing credential
            return GitHubCredential.update(
                existing.id,
                github_user_id=github_user_id,
                github_username=github_username,
                access_token=access_token,
                scope=scope,
            )
        else:
            # Create new credential
            return GitHubCredential.create(
                GitHubCredentialCreate(
                    engineer_id=engineer_id,
                    github_user_id=github_user_id,
                    github_username=github_username,
                    access_token=access_token,
                    scope=scope,
                )
            )

    def get_connection_status(self, engineer_id: str) -> GitHubConnectionStatus:
        """
        Check GitHub connection status for an engineer.

        Args:
            engineer_id: The engineer ID

        Returns:
            GitHubConnectionStatus with connection details
        """
        credential = GitHubCredential.get_or_none(engineer_id=engineer_id)

        if credential:
            return GitHubConnectionStatus(
                connected=True,
                github_username=credential.github_username,
                github_user_id=credential.github_user_id,
                connected_at=credential.created_at,
            )

        return GitHubConnectionStatus(connected=False)

    def disconnect(self, engineer_id: str) -> bool:
        """
        Remove GitHub connection for an engineer.

        Args:
            engineer_id: The engineer ID

        Returns:
            True if disconnected, False if no connection existed
        """
        credential = GitHubCredential.get_or_none(engineer_id=engineer_id)

        if credential:
            GitHubCredential.delete(GitHubCredential.id == credential.id)
            logger.info('GitHub disconnected', engineer_id=engineer_id)
            return True

        return False

    def get_credential_for_engineer(self, engineer_id: str) -> GitHubCredential | None:
        """
        Get GitHub credential for an engineer.

        Args:
            engineer_id: The engineer ID

        Returns:
            GitHubCredential or None if not connected
        """
        return GitHubCredential.get_or_none(engineer_id=engineer_id)
