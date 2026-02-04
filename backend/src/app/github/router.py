"""GitHub API router for OAuth flow and data sync."""

from fastapi import APIRouter, Depends, status
from loguru import logger

from src.app.github.domains import (
    GitHubAuthorizationUrl,
    GitHubCallbackRequest,
    GitHubConnectionStatus,
    GitHubSyncResponse,
)
from src.app.github.exceptions import (
    GitHubCredentialNotFound,
    GitHubOAuthError,
    GitHubOAuthStateExpired,
)
from src.app.github.oauth_service import GitHubOAuthService
from src.app.github.service import GitHubService
from src.common.exceptions import APIException
from src.core.authentication.dependencies import get_current_membership
from src.core.membership.domains import MembershipRead

router = APIRouter()


@router.get('/github/connect')
def get_github_connect_url(
    engineer_id: str,
    membership: MembershipRead = Depends(get_current_membership),
    oauth_service: GitHubOAuthService = Depends(GitHubOAuthService.factory),
) -> GitHubAuthorizationUrl:
    """Get GitHub OAuth authorization URL."""
    try:
        return oauth_service.get_authorization_url(engineer_id)
    except GitHubOAuthError as e:
        logger.error('Failed to generate GitHub OAuth URL', error=str(e))
        raise APIException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message='GitHub OAuth is not configured. Please contact your administrator.',
        )


@router.post('/github/callback')
def github_callback(
    request: GitHubCallbackRequest,
    oauth_service: GitHubOAuthService = Depends(GitHubOAuthService.factory),
) -> GitHubConnectionStatus:
    """Handle GitHub OAuth/installation callback."""
    try:
        return oauth_service.complete_oauth_callback(
            state=request.state,
            code=request.code,
            installation_id=request.installation_id,
        )
    except GitHubOAuthStateExpired as e:
        logger.warning('GitHub OAuth state expired', error=str(e))
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message='OAuth session expired. Please try connecting again.',
        )
    except GitHubOAuthError as e:
        logger.error('GitHub OAuth callback failed', error=str(e))
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message=f'GitHub authentication failed: {str(e)}',
        )


@router.get('/github/status/{engineer_id}')
def get_github_status(
    engineer_id: str,
    membership: MembershipRead = Depends(get_current_membership),
    oauth_service: GitHubOAuthService = Depends(GitHubOAuthService.factory),
) -> GitHubConnectionStatus:
    """Check GitHub connection status for an engineer."""
    return oauth_service.get_connection_status(engineer_id)


@router.delete('/github/disconnect/{engineer_id}')
def disconnect_github(
    engineer_id: str,
    membership: MembershipRead = Depends(get_current_membership),
    oauth_service: GitHubOAuthService = Depends(GitHubOAuthService.factory),
) -> GitHubConnectionStatus:
    """Remove GitHub connection for an engineer."""
    oauth_service.disconnect(engineer_id)
    return oauth_service.get_connection_status(engineer_id)


@router.post('/github/sync/{engineer_id}')
def sync_github(
    engineer_id: str,
    membership: MembershipRead = Depends(get_current_membership),
    github_service: GitHubService = Depends(GitHubService.factory),
) -> GitHubSyncResponse:
    """Manually trigger GitHub data sync for an engineer."""
    try:
        result = github_service.sync_engineer(engineer_id)
        return GitHubSyncResponse(prs=result['prs'])
    except GitHubCredentialNotFound:
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message='GitHub is not connected for this engineer.',
        )
    except Exception as e:
        logger.exception('GitHub sync failed', engineer_id=engineer_id)
        raise APIException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message='Failed to sync GitHub data. Please try again later.',
        )


