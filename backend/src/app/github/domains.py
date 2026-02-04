from datetime import date, datetime
from typing import Any, Optional

from pydantic import Field

from src.app.github.constants import (
    GITHUB_COMMIT_PK_ABBREV,
    GITHUB_CREDENTIAL_PK_ABBREV,
    GITHUB_DAILY_PK_ABBREV,
    GITHUB_PULL_REQUEST_PK_ABBREV,
)
from src.common.domain import BaseDomain
from src.common.nanoid import NanoId, NanoIdType


# GitHubCredential domains
class GitHubCredentialCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=GITHUB_CREDENTIAL_PK_ABBREV))
    engineer_id: str
    github_user_id: str
    github_username: str
    access_token: str
    scope: str | None = None


class GitHubCredentialRead(BaseDomain):
    id: str
    engineer_id: str
    github_user_id: str
    github_username: str
    scope: str | None
    created_at: datetime
    modified_at: datetime | None


# GitHubCommit domains
class GitHubCommitCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=GITHUB_COMMIT_PK_ABBREV))
    engineer_id: str
    github_commit_sha: str
    github_pr_id: int | None = None
    repo_full_name: str
    message: str | None = None
    lines_added: int = 0
    lines_removed: int = 0
    committed_at: datetime
    raw_payload: dict[str, Any] | None = None


class GitHubCommitRead(BaseDomain):
    id: str
    engineer_id: str
    github_commit_sha: str
    github_pr_id: int | None
    repo_full_name: str
    message: str | None
    lines_added: int
    lines_removed: int
    committed_at: datetime
    raw_payload: dict[str, Any] | None
    created_at: datetime


# GitHubPullRequest domains
class GitHubPullRequestCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=GITHUB_PULL_REQUEST_PK_ABBREV))
    engineer_id: str
    github_pr_id: int
    github_pr_number: int
    repo_full_name: str
    title: str
    state: str  # 'open', 'closed', 'merged'
    is_author: bool = False
    is_reviewer: bool = False
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    lines_added: int = 0
    lines_removed: int = 0
    review_comments_count: int = 0
    raw_payload: dict[str, Any] | None = None


class GitHubPullRequestRead(BaseDomain):
    id: str
    engineer_id: str
    github_pr_id: int
    github_pr_number: int
    repo_full_name: str
    title: str
    state: str
    is_author: bool
    is_reviewer: bool
    merged_at: datetime | None
    closed_at: datetime | None
    lines_added: int
    lines_removed: int
    review_comments_count: int
    raw_payload: dict[str, Any] | None
    created_at: datetime


# GitHubDaily domains (pre-aggregated daily stats)
class GitHubDailyCreate(BaseDomain):
    id: Optional[NanoIdType] = Field(default_factory=lambda: NanoId.gen(abbrev=GITHUB_DAILY_PK_ABBREV))
    engineer_id: str
    date: date
    commits_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    prs_merged: int = 0
    prs_reviewed: int = 0
    review_comments: int = 0


class GitHubDailyRead(BaseDomain):
    id: str
    engineer_id: str
    date: date
    commits_count: int
    lines_added: int
    lines_removed: int
    prs_merged: int
    prs_reviewed: int
    review_comments: int
    created_at: datetime


# API request/response domains
class GitHubCallbackRequest(BaseDomain):
    """Request payload for GitHub OAuth/App installation callback.

    Supports both:
    - OAuth flow: code + state
    - App installation flow: installation_id + state (+ optional code)
    """

    state: str
    code: str | None = None  # OAuth authorization code
    installation_id: int | None = None  # GitHub App installation ID
    setup_action: str | None = None  # 'install' or 'update' (app installation only)


class GitHubSyncResponse(BaseDomain):
    """Response for GitHub sync operation."""

    prs: int  # Number of merged PRs synced


class GitHubConnectionStatus(BaseDomain):
    """Response for GitHub connection status check."""

    connected: bool
    github_username: str | None = None
    github_user_id: str | None = None
    connected_at: datetime | None = None


class GitHubAuthorizationUrl(BaseDomain):
    """Response containing GitHub OAuth authorization URL."""

    authorization_url: str
