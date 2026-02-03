from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.app.leaderboard.domains import (
    DailyTotalsResponse,
    EngineerStatsResponse,
    HistoricalRankingsResponse,
    Leaderboard,
    UsageStats,
)
from src.app.leaderboard.service import LeaderboardService
from src.core.authentication.dependencies import get_current_membership
from src.core.membership.domains import MembershipRead
from src.platform.slack.service import SlackService

router = APIRouter()


class PostResponse(BaseModel):
    success: bool
    date: date


@router.get('', response_model=Leaderboard)
def get_leaderboard(
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> Leaderboard:
    """Get current leaderboard data for the team."""
    return LeaderboardService.get_leaderboard(membership.customer_id, as_of)


@router.get('/stats', response_model=UsageStats)
def get_usage_stats(
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> UsageStats:
    """Get usage stats comparing current vs previous periods at the same point in time."""
    return LeaderboardService.get_usage_stats(membership.customer_id, as_of)


@router.get('/daily-totals', response_model=DailyTotalsResponse)
def get_daily_totals(
    start_date: date | None = None,
    end_date: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> DailyTotalsResponse:
    """Get daily token totals for charting. Defaults to last 7 days."""
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=6))
    return LeaderboardService.get_daily_totals(membership.customer_id, start, end)


@router.get('/engineers/{engineer_id}/stats', response_model=EngineerStatsResponse)
def get_engineer_stats(
    engineer_id: str,
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> EngineerStatsResponse:
    """Get usage stats for a specific engineer."""
    return LeaderboardService.get_engineer_stats(engineer_id, as_of)


@router.get('/engineers/{engineer_id}/daily-totals', response_model=DailyTotalsResponse)
def get_engineer_daily_totals(
    engineer_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> DailyTotalsResponse:
    """Get daily token totals for a specific engineer."""
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=6))
    return LeaderboardService.get_engineer_daily_totals(engineer_id, start, end)


@router.get('/engineers/{engineer_id}/historical-rankings', response_model=HistoricalRankingsResponse)
def get_historical_rankings(
    engineer_id: str,
    period_type: str = 'daily',
    num_periods: int = 20,
    membership: MembershipRead = Depends(get_current_membership),
) -> HistoricalRankingsResponse:
    """Get historical rankings for an engineer."""
    return LeaderboardService.get_historical_rankings(
        membership.customer_id, engineer_id, period_type, num_periods
    )


@router.post('/post', response_model=PostResponse)
def post_to_slack(
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> PostResponse:
    """Post leaderboard to Slack."""
    leaderboard = LeaderboardService.get_leaderboard(membership.customer_id, as_of)
    success = SlackService.post_leaderboard(leaderboard)

    return PostResponse(success=success, date=leaderboard.date)
