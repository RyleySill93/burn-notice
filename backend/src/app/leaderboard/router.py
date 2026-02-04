from datetime import date, timedelta

from fastapi import APIRouter, Depends

from src.app.leaderboard.domains import (
    DailyTotalsByEngineerResponse,
    DailyTotalsResponse,
    EngineerStatsResponse,
    HistoricalRankingsResponse,
    Leaderboard,
    PostResponse,
    TeamTimeSeriesResponse,
    TimeSeriesResponse,
    UsageStats,
)
from src.app.leaderboard.service import LeaderboardService
from src.core.authentication.dependencies import get_current_membership
from src.core.membership.domains import MembershipRead

router = APIRouter()


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


@router.get('/daily-totals-by-engineer', response_model=DailyTotalsByEngineerResponse)
def get_daily_totals_by_engineer(
    start_date: date | None = None,
    end_date: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> DailyTotalsByEngineerResponse:
    """Get daily token totals broken down by engineer for charting. Defaults to last 7 days."""
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=6))
    return LeaderboardService.get_daily_totals_by_engineer(membership.customer_id, start, end)


@router.get('/time-series', response_model=TeamTimeSeriesResponse)
def get_team_time_series(
    period: str = 'hourly',
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> TeamTimeSeriesResponse:
    """
    Get time series data for all engineers in the team.

    Periods:
    - hourly: last 12 hours, 5-minute buckets (ignores as_of)
    - daily: 30 days ending on as_of, daily buckets
    - weekly: 12 weeks ending on as_of, weekly buckets
    - monthly: 12 months ending on as_of, monthly buckets
    """
    return LeaderboardService.get_team_time_series(membership.customer_id, period, as_of)


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
    return LeaderboardService.get_historical_rankings(membership.customer_id, engineer_id, period_type, num_periods)


@router.get('/engineers/{engineer_id}/time-series', response_model=TimeSeriesResponse)
def get_engineer_time_series(
    engineer_id: str,
    period: str = 'hourly',
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> TimeSeriesResponse:
    """
    Get time series data for an engineer.

    Periods:
    - hourly: last 12 hours, 5-minute buckets (ignores as_of)
    - daily: single day, hourly buckets
    - weekly: 7 days ending on as_of, daily buckets
    - monthly: 30 days ending on as_of, daily buckets
    """
    return LeaderboardService.get_engineer_time_series(engineer_id, period, as_of)


@router.post('/post', response_model=PostResponse)
def post_to_slack(
    as_of: date | None = None,
    membership: MembershipRead = Depends(get_current_membership),
) -> PostResponse:
    """Post leaderboard to Slack."""
    return LeaderboardService.post_leaderboard_to_slack(membership.customer_id, as_of)
