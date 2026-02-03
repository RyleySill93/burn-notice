from datetime import date

from pydantic import BaseModel, computed_field


class LeaderboardEntry(BaseModel):
    engineer_id: str
    display_name: str
    tokens: int
    rank: int
    prev_rank: int | None = None

    @computed_field
    @property
    def rank_change(self) -> int | None:
        """Positive = moved up, negative = moved down, None = new."""
        if self.prev_rank is None:
            return None
        return self.prev_rank - self.rank


class Leaderboard(BaseModel):
    date: date
    today: list[LeaderboardEntry]
    yesterday: list[LeaderboardEntry]
    weekly: list[LeaderboardEntry]
    monthly: list[LeaderboardEntry]


class PeriodStats(BaseModel):
    """Stats for a single time period with comparison."""

    tokens: int
    comparison_tokens: int

    @computed_field
    @property
    def change_percent(self) -> float | None:
        """Percentage change from comparison period. None if no comparison data."""
        if self.comparison_tokens == 0:
            return None
        return ((self.tokens - self.comparison_tokens) / self.comparison_tokens) * 100


class UsageStats(BaseModel):
    """Summary stats for the homepage cards."""

    date: date
    today: PeriodStats
    this_week: PeriodStats
    this_month: PeriodStats


class DailyTotal(BaseModel):
    """Token totals for a single day."""

    date: date
    tokens: int


class DailyTotalsResponse(BaseModel):
    """Response for the daily totals chart endpoint."""

    start_date: date
    end_date: date
    totals: list[DailyTotal]


class HistoricalRank(BaseModel):
    """A single historical ranking entry."""

    period_start: date
    period_end: date
    rank: int | None  # None if user had no activity in this period
    tokens: int


class HistoricalRankingsResponse(BaseModel):
    """Response for historical rankings endpoint."""

    engineer_id: str
    period_type: str  # 'daily', 'weekly', 'monthly'
    rankings: list[HistoricalRank]


class EngineerStatsResponse(BaseModel):
    """Stats for a specific engineer."""

    engineer_id: str
    display_name: str
    date: date
    today: PeriodStats
    this_week: PeriodStats
    this_month: PeriodStats
