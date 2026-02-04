from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.github.constants import (
    GITHUB_COMMIT_PK_ABBREV,
    GITHUB_CREDENTIAL_PK_ABBREV,
    GITHUB_DAILY_PK_ABBREV,
    GITHUB_PULL_REQUEST_PK_ABBREV,
)
from src.app.github.domains import (
    GitHubCommitCreate,
    GitHubCommitRead,
    GitHubCredentialCreate,
    GitHubCredentialRead,
    GitHubDailyCreate,
    GitHubDailyRead,
    GitHubPullRequestCreate,
    GitHubPullRequestRead,
)
from src.common.encrypted_field import EncryptedString
from src.common.model import BaseModel


class GitHubCredential(BaseModel[GitHubCredentialRead, GitHubCredentialCreate]):
    """OAuth credentials for GitHub integration per engineer."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, unique=True)
    github_user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    github_username: Mapped[str] = mapped_column(String(100), nullable=False)
    access_token: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    scope: Mapped[str | None] = mapped_column(String(500), nullable=True)

    engineer = relationship('Engineer')

    __pk_abbrev__ = GITHUB_CREDENTIAL_PK_ABBREV
    __read_domain__ = GitHubCredentialRead
    __create_domain__ = GitHubCredentialCreate

    __table_args__ = (Index('idx_github_credential_engineer', 'engineer_id', unique=True),)


class GitHubCommit(BaseModel[GitHubCommitRead, GitHubCommitCreate]):
    """Individual commits from GitHub."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, index=True)
    github_commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    github_pr_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    repo_full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_removed: Mapped[int] = mapped_column(Integer, default=0)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    engineer = relationship('Engineer')

    __pk_abbrev__ = GITHUB_COMMIT_PK_ABBREV
    __read_domain__ = GitHubCommitRead
    __create_domain__ = GitHubCommitCreate

    __table_args__ = (
        Index('idx_github_commit_engineer_sha', 'engineer_id', 'github_commit_sha', unique=True),
        Index('idx_github_commit_committed_at', 'committed_at'),
    )


class GitHubPullRequest(BaseModel[GitHubPullRequestRead, GitHubPullRequestCreate]):
    """Pull request activity from GitHub."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False, index=True)
    github_pr_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    repo_full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)  # 'open', 'closed', 'merged'
    is_author: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reviewer: Mapped[bool] = mapped_column(Boolean, default=False)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_removed: Mapped[int] = mapped_column(Integer, default=0)
    review_comments_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    engineer = relationship('Engineer')

    __pk_abbrev__ = GITHUB_PULL_REQUEST_PK_ABBREV
    __read_domain__ = GitHubPullRequestRead
    __create_domain__ = GitHubPullRequestCreate

    __table_args__ = (
        # Unique per engineer + PR ID + role (author vs reviewer)
        Index('idx_github_pr_engineer_pr', 'engineer_id', 'github_pr_id', 'is_author', 'is_reviewer', unique=True),
        Index('idx_github_pr_merged_at', 'merged_at'),
    )


class GitHubDaily(BaseModel[GitHubDailyRead, GitHubDailyCreate]):
    """Pre-aggregated daily GitHub stats."""

    engineer_id: Mapped[str] = mapped_column(ForeignKey('engineer.id'), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    commits_count: Mapped[int] = mapped_column(Integer, default=0)
    lines_added: Mapped[int] = mapped_column(BigInteger, default=0)
    lines_removed: Mapped[int] = mapped_column(BigInteger, default=0)
    prs_merged: Mapped[int] = mapped_column(Integer, default=0)
    prs_reviewed: Mapped[int] = mapped_column(Integer, default=0)
    review_comments: Mapped[int] = mapped_column(Integer, default=0)

    engineer = relationship('Engineer')

    __pk_abbrev__ = GITHUB_DAILY_PK_ABBREV
    __read_domain__ = GitHubDailyRead
    __create_domain__ = GitHubDailyCreate

    __table_args__ = (
        Index('idx_github_daily_engineer_date', 'engineer_id', 'date', unique=True),
        Index('idx_github_daily_date', 'date'),
    )
