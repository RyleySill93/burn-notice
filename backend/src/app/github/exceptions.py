"""GitHub domain exceptions."""


class GitHubError(Exception):
    """Base exception for GitHub domain."""

    pass


class GitHubOAuthError(GitHubError):
    """Error during GitHub OAuth flow."""

    pass


class GitHubOAuthStateExpired(GitHubOAuthError):
    """OAuth state has expired or is invalid."""

    pass


class GitHubOAuthStateMismatch(GitHubOAuthError):
    """OAuth state does not match expected value."""

    pass


class GitHubAPIError(GitHubError):
    """Error communicating with GitHub API."""

    pass


class GitHubRateLimitError(GitHubAPIError):
    """GitHub API rate limit exceeded."""

    pass


class GitHubCredentialNotFound(GitHubError):
    """GitHub credential not found for engineer."""

    pass
