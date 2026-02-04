"""GitHub Service for fetching and processing GitHub data."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from loguru import logger
from sqlalchemy import func

from src.app.github.domains import (
    GitHubCommitCreate,
    GitHubCommitRead,
    GitHubDailyCreate,
    GitHubDailyRead,
    GitHubPullRequestCreate,
    GitHubPullRequestRead,
)
from src.app.github.exceptions import GitHubAPIError, GitHubCredentialNotFound, GitHubRateLimitError
from src.app.github.models import GitHubCommit, GitHubCredential, GitHubDaily, GitHubPullRequest
from src.network.database import db


class GitHubService:
    """Service for fetching and processing GitHub data."""

    GITHUB_API_BASE = 'https://api.github.com'

    def __init__(self):
        pass

    @classmethod
    def factory(cls) -> 'GitHubService':
        """Factory method to create GitHubService instance."""
        return cls()

    def _get_headers(self, access_token: str) -> dict[str, str]:
        """Get standard headers for GitHub API requests."""
        return {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Check for rate limit and raise if exceeded."""
        remaining = response.headers.get('X-RateLimit-Remaining', '1')
        if int(remaining) == 0:
            reset_time = response.headers.get('X-RateLimit-Reset', '0')
            raise GitHubRateLimitError(f'Rate limit exceeded. Resets at {reset_time}')

    def fetch_commits_for_engineer(
        self,
        engineer_id: str,
        since: datetime | None = None,
    ) -> list[GitHubCommitRead]:
        """
        Fetch commits from GitHub for an engineer.

        Args:
            engineer_id: The engineer ID
            since: Fetch commits after this datetime (defaults to 7 days ago)

        Returns:
            List of GitHubCommitRead objects
        """
        credential = GitHubCredential.get_or_none(engineer_id=engineer_id)
        if not credential:
            raise GitHubCredentialNotFound(f'No GitHub credential for engineer {engineer_id}')

        # Access the raw model to get the decrypted access_token
        # Since credential is a Read domain object, we need to get the model
        credential_model = (
            db.session.query(GitHubCredential).filter(GitHubCredential.engineer_id == engineer_id).first()
        )

        if not credential_model:
            raise GitHubCredentialNotFound(f'No GitHub credential for engineer {engineer_id}')

        access_token = credential_model.access_token
        username = credential.github_username

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=7)

        since_str = since.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Search for commits by this user
        search_url = f'{self.GITHUB_API_BASE}/search/commits'
        params = {
            'q': f'author:{username} committer-date:>={since_str}',
            'sort': 'committer-date',
            'order': 'desc',
            'per_page': 100,
        }

        headers = self._get_headers(access_token)
        headers['Accept'] = 'application/vnd.github.cloak-preview+json'  # Required for commit search

        commits_created = []

        try:
            response = requests.get(search_url, headers=headers, params=params, timeout=60)
            self._handle_rate_limit(response)

            if response.status_code != 200:
                logger.error('GitHub commit search failed', status=response.status_code, response=response.text)
                raise GitHubAPIError(f'Commit search failed: {response.status_code}')

            data = response.json()
            items = data.get('items', [])

            logger.info(
                'Fetched commits from GitHub',
                engineer_id=engineer_id,
                username=username,
                count=len(items),
            )

            for item in items:
                commit = self._process_commit(engineer_id, item, access_token, headers)
                if commit:
                    commits_created.append(commit)

        except requests.RequestException as e:
            logger.error('GitHub API request failed', error=str(e))
            raise GitHubAPIError(f'GitHub API request failed: {str(e)}')

        return commits_created

    def _process_commit(
        self,
        engineer_id: str,
        item: dict[str, Any],
        access_token: str,
        headers: dict[str, str],
    ) -> GitHubCommitRead | None:
        """Process a single commit from GitHub search results."""
        sha = item.get('sha')
        repo = item.get('repository', {})
        repo_full_name = repo.get('full_name', '')
        commit_info = item.get('commit', {})
        message = (commit_info.get('message', '') or '')[:500]  # Truncate to 500 chars
        committer = commit_info.get('committer', {})
        committed_at_str = committer.get('date')

        if not sha or not repo_full_name or not committed_at_str:
            return None

        # Parse committed_at
        committed_at = datetime.fromisoformat(committed_at_str.replace('Z', '+00:00'))

        # Check if we already have this commit
        existing = GitHubCommit.get_or_none(engineer_id=engineer_id, github_commit_sha=sha)
        if existing:
            return existing

        # Fetch commit details for lines added/removed
        lines_added = 0
        lines_removed = 0

        try:
            commit_url = f'{self.GITHUB_API_BASE}/repos/{repo_full_name}/commits/{sha}'
            detail_response = requests.get(commit_url, headers=headers, timeout=30)

            if detail_response.status_code == 200:
                detail_data = detail_response.json()
                stats = detail_data.get('stats', {})
                lines_added = stats.get('additions', 0)
                lines_removed = stats.get('deletions', 0)
        except Exception as e:
            logger.warning('Failed to fetch commit details', sha=sha, error=str(e))

        # Create commit record
        return GitHubCommit.create(
            GitHubCommitCreate(
                engineer_id=engineer_id,
                github_commit_sha=sha,
                repo_full_name=repo_full_name,
                message=message,
                lines_added=lines_added,
                lines_removed=lines_removed,
                committed_at=committed_at,
                raw_payload=item,
            )
        )

    def fetch_prs_for_engineer(
        self,
        engineer_id: str,
        since: datetime | None = None,
    ) -> list[GitHubPullRequestRead]:
        """
        Fetch PRs from GitHub for an engineer (both authored and reviewed).

        Args:
            engineer_id: The engineer ID
            since: Fetch PRs updated after this datetime (defaults to 7 days ago)

        Returns:
            List of GitHubPullRequestRead objects
        """
        credential = GitHubCredential.get_or_none(engineer_id=engineer_id)
        if not credential:
            raise GitHubCredentialNotFound(f'No GitHub credential for engineer {engineer_id}')

        # Get the model to access decrypted token
        credential_model = (
            db.session.query(GitHubCredential).filter(GitHubCredential.engineer_id == engineer_id).first()
        )

        if not credential_model:
            raise GitHubCredentialNotFound(f'No GitHub credential for engineer {engineer_id}')

        access_token = credential_model.access_token
        username = credential.github_username

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=7)

        since_str = since.strftime('%Y-%m-%dT%H:%M:%SZ')
        headers = self._get_headers(access_token)

        prs_created = []

        # Fetch authored PRs
        authored_prs = self._fetch_authored_prs(engineer_id, username, since_str, headers)
        prs_created.extend(authored_prs)

        # Fetch reviewed PRs
        reviewed_prs = self._fetch_reviewed_prs(engineer_id, username, since_str, headers)
        prs_created.extend(reviewed_prs)

        return prs_created

    def _fetch_authored_prs(
        self,
        engineer_id: str,
        username: str,
        since_str: str,
        headers: dict[str, str],
    ) -> list[GitHubPullRequestRead]:
        """Fetch PRs authored by the user."""
        search_url = f'{self.GITHUB_API_BASE}/search/issues'
        params = {
            'q': f'type:pr author:{username} updated:>={since_str}',
            'sort': 'updated',
            'order': 'desc',
            'per_page': 100,
        }

        prs_created = []

        try:
            response = requests.get(search_url, headers=headers, params=params, timeout=60)
            self._handle_rate_limit(response)

            if response.status_code != 200:
                logger.error('GitHub PR search failed', status=response.status_code)
                return prs_created

            data = response.json()
            items = data.get('items', [])

            logger.info(
                'Fetched authored PRs from GitHub',
                engineer_id=engineer_id,
                username=username,
                count=len(items),
            )

            for item in items:
                pr = self._process_pr(engineer_id, item, headers, is_author=True, is_reviewer=False)
                if pr:
                    prs_created.append(pr)

        except requests.RequestException as e:
            logger.error('GitHub API request failed', error=str(e))

        return prs_created

    def _fetch_reviewed_prs(
        self,
        engineer_id: str,
        username: str,
        since_str: str,
        headers: dict[str, str],
    ) -> list[GitHubPullRequestRead]:
        """Fetch PRs reviewed by the user."""
        search_url = f'{self.GITHUB_API_BASE}/search/issues'
        params = {
            'q': f'type:pr reviewed-by:{username} updated:>={since_str} -author:{username}',
            'sort': 'updated',
            'order': 'desc',
            'per_page': 100,
        }

        prs_created = []

        try:
            response = requests.get(search_url, headers=headers, params=params, timeout=60)
            self._handle_rate_limit(response)

            if response.status_code != 200:
                logger.error('GitHub reviewed PR search failed', status=response.status_code)
                return prs_created

            data = response.json()
            items = data.get('items', [])

            logger.info(
                'Fetched reviewed PRs from GitHub',
                engineer_id=engineer_id,
                username=username,
                count=len(items),
            )

            for item in items:
                pr = self._process_pr(engineer_id, item, headers, is_author=False, is_reviewer=True)
                if pr:
                    prs_created.append(pr)

        except requests.RequestException as e:
            logger.error('GitHub API request failed', error=str(e))

        return prs_created

    def _process_pr(
        self,
        engineer_id: str,
        item: dict[str, Any],
        headers: dict[str, str],
        is_author: bool,
        is_reviewer: bool,
    ) -> GitHubPullRequestRead | None:
        """Process a single PR from GitHub search results."""
        pr_id = item.get('id')
        pr_number = item.get('number')
        title = (item.get('title', '') or '')[:500]
        state = item.get('state', 'open')

        # Extract repo info from URL
        # html_url format: https://github.com/owner/repo/pull/123
        html_url = item.get('html_url', '')
        url_parts = html_url.split('/')
        if len(url_parts) >= 5:
            repo_full_name = f'{url_parts[-4]}/{url_parts[-3]}'
        else:
            repo_full_name = ''

        if not pr_id or not pr_number or not repo_full_name:
            return None

        # Check if we already have this PR for this engineer with same role
        existing = GitHubPullRequest.get_or_none(
            engineer_id=engineer_id,
            github_pr_id=pr_id,
            is_author=is_author,
            is_reviewer=is_reviewer,
        )
        if existing:
            # Update state if changed
            if existing.state != state:
                return GitHubPullRequest.update(existing.id, state=state, raw_payload=item)
            return existing

        # Get PR details for lines and merged_at
        pr_url = item.get('pull_request', {}).get('url')
        lines_added = 0
        lines_removed = 0
        merged_at = None
        closed_at = None
        review_comments_count = 0

        if pr_url:
            try:
                detail_response = requests.get(pr_url, headers=headers, timeout=30)
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    lines_added = detail_data.get('additions', 0)
                    lines_removed = detail_data.get('deletions', 0)
                    review_comments_count = detail_data.get('review_comments', 0)

                    if detail_data.get('merged_at'):
                        merged_at = datetime.fromisoformat(detail_data['merged_at'].replace('Z', '+00:00'))
                        state = 'merged'

                    if detail_data.get('closed_at'):
                        closed_at = datetime.fromisoformat(detail_data['closed_at'].replace('Z', '+00:00'))
            except Exception as e:
                logger.warning('Failed to fetch PR details', pr_id=pr_id, error=str(e))

        return GitHubPullRequest.create(
            GitHubPullRequestCreate(
                engineer_id=engineer_id,
                github_pr_id=pr_id,
                github_pr_number=pr_number,
                repo_full_name=repo_full_name,
                title=title,
                state=state,
                is_author=is_author,
                is_reviewer=is_reviewer,
                merged_at=merged_at,
                closed_at=closed_at,
                lines_added=lines_added,
                lines_removed=lines_removed,
                review_comments_count=review_comments_count,
                raw_payload=item,
            )
        )

    def sync_engineer(self, engineer_id: str, since: datetime | None = None) -> dict[str, int]:
        """
        Sync all GitHub data for an engineer.

        Args:
            engineer_id: The engineer ID
            since: Sync data after this datetime

        Returns:
            Dictionary with counts of synced items
        """
        commits = self.fetch_commits_for_engineer(engineer_id, since)
        prs = self.fetch_prs_for_engineer(engineer_id, since)

        return {
            'commits': len(commits),
            'prs': len(prs),
        }

    def sync_all_engineers(self, since: datetime | None = None) -> dict[str, Any]:
        """
        Sync GitHub data for all connected engineers.

        Args:
            since: Sync data after this datetime

        Returns:
            Summary of sync operation
        """
        credentials = GitHubCredential.list()
        results = {
            'engineers_synced': 0,
            'engineers_failed': 0,
            'total_commits': 0,
            'total_prs': 0,
        }

        for credential in credentials:
            try:
                sync_result = self.sync_engineer(credential.engineer_id, since)
                results['engineers_synced'] += 1
                results['total_commits'] += sync_result['commits']
                results['total_prs'] += sync_result['prs']
            except Exception as e:
                logger.error(
                    'Failed to sync GitHub data for engineer',
                    engineer_id=credential.engineer_id,
                    error=str(e),
                )
                results['engineers_failed'] += 1

        logger.info('GitHub sync completed', **results)
        return results

    def rollup_daily(self, for_date: date | None = None) -> int:
        """
        Aggregate raw GitHub data into daily rollups.

        Args:
            for_date: The date to rollup (defaults to yesterday)

        Returns:
            Count of engineers processed
        """
        if for_date is None:
            for_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        # Convert date to datetime range
        start_dt = datetime.combine(for_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(for_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        # Aggregate commits
        commit_stats = (
            db.session.query(
                GitHubCommit.engineer_id,
                func.count(GitHubCommit.id).label('commits_count'),
                func.coalesce(func.sum(GitHubCommit.lines_added), 0).label('lines_added'),
                func.coalesce(func.sum(GitHubCommit.lines_removed), 0).label('lines_removed'),
            )
            .filter(
                GitHubCommit.committed_at >= start_dt,
                GitHubCommit.committed_at <= end_dt,
            )
            .group_by(GitHubCommit.engineer_id)
            .all()
        )

        commit_by_engineer = {
            row.engineer_id: {
                'commits_count': row.commits_count,
                'lines_added': row.lines_added,
                'lines_removed': row.lines_removed,
            }
            for row in commit_stats
        }

        # Aggregate PRs merged (authored)
        prs_merged_stats = (
            db.session.query(
                GitHubPullRequest.engineer_id,
                func.count(GitHubPullRequest.id).label('prs_merged'),
            )
            .filter(
                GitHubPullRequest.merged_at >= start_dt,
                GitHubPullRequest.merged_at <= end_dt,
                GitHubPullRequest.is_author == True,
            )
            .group_by(GitHubPullRequest.engineer_id)
            .all()
        )

        prs_merged_by_engineer = {row.engineer_id: row.prs_merged for row in prs_merged_stats}

        # Aggregate PRs reviewed
        prs_reviewed_stats = (
            db.session.query(
                GitHubPullRequest.engineer_id,
                func.count(GitHubPullRequest.id).label('prs_reviewed'),
                func.coalesce(func.sum(GitHubPullRequest.review_comments_count), 0).label('review_comments'),
            )
            .filter(
                GitHubPullRequest.created_at >= start_dt,
                GitHubPullRequest.created_at <= end_dt,
                GitHubPullRequest.is_reviewer == True,
            )
            .group_by(GitHubPullRequest.engineer_id)
            .all()
        )

        review_by_engineer = {
            row.engineer_id: {
                'prs_reviewed': row.prs_reviewed,
                'review_comments': row.review_comments,
            }
            for row in prs_reviewed_stats
        }

        # Get all engineers with activity
        all_engineer_ids = (
            set(commit_by_engineer.keys()) | set(prs_merged_by_engineer.keys()) | set(review_by_engineer.keys())
        )

        # Upsert daily records
        for engineer_id in all_engineer_ids:
            commit_data = commit_by_engineer.get(
                engineer_id, {'commits_count': 0, 'lines_added': 0, 'lines_removed': 0}
            )
            prs_merged = prs_merged_by_engineer.get(engineer_id, 0)
            review_data = review_by_engineer.get(engineer_id, {'prs_reviewed': 0, 'review_comments': 0})

            existing = GitHubDaily.get_or_none(engineer_id=engineer_id, date=for_date)

            if existing:
                GitHubDaily.update(
                    existing.id,
                    commits_count=commit_data['commits_count'],
                    lines_added=commit_data['lines_added'],
                    lines_removed=commit_data['lines_removed'],
                    prs_merged=prs_merged,
                    prs_reviewed=review_data['prs_reviewed'],
                    review_comments=review_data['review_comments'],
                )
            else:
                GitHubDaily.create(
                    GitHubDailyCreate(
                        engineer_id=engineer_id,
                        date=for_date,
                        commits_count=commit_data['commits_count'],
                        lines_added=commit_data['lines_added'],
                        lines_removed=commit_data['lines_removed'],
                        prs_merged=prs_merged,
                        prs_reviewed=review_data['prs_reviewed'],
                        review_comments=review_data['review_comments'],
                    )
                )

        logger.info('GitHub daily rollup completed', for_date=for_date, engineers_processed=len(all_engineer_ids))
        return len(all_engineer_ids)

    def get_daily_stats_for_engineer(
        self,
        engineer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[GitHubDailyRead]:
        """
        Get daily GitHub stats for an engineer within a date range.

        Args:
            engineer_id: The engineer ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of GitHubDailyRead objects
        """
        return GitHubDaily.list(
            GitHubDaily.engineer_id == engineer_id,
            GitHubDaily.date >= start_date,
            GitHubDaily.date <= end_date,
        )
