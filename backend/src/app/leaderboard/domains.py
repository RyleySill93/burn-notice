from datetime import date

from pydantic import BaseModel, computed_field


class LeaderboardEntry(BaseModel):
    engineer_id: str
    display_name: str
    tokens: int
    tokens_input: int
    tokens_output: int
    cost_usd: float = 0.0
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
    tokens_input: int
    tokens_output: int
    cost_usd: float = 0.0
    comparison_tokens: int
    comparison_tokens_input: int
    comparison_tokens_output: int
    comparison_cost_usd: float = 0.0

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
    tokens_input: int
    tokens_output: int
    cost_usd: float = 0.0


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
    tokens_input: int
    tokens_output: int
    cost_usd: float = 0.0


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


class EngineerDailyTotal(BaseModel):
    """Token totals for a single engineer on a single day."""

    engineer_id: str
    display_name: str
    tokens: int
    tokens_input: int
    tokens_output: int
    cost_usd: float = 0.0


class DayWithEngineers(BaseModel):
    """A single day's totals broken down by engineer."""

    date: date
    engineers: list[EngineerDailyTotal]


class EngineerInfo(BaseModel):
    """Basic info about an engineer for legend/colors."""

    id: str
    display_name: str


class DailyTotalsByEngineerResponse(BaseModel):
    """Response for the daily totals by engineer chart endpoint."""

    start_date: date
    end_date: date
    days: list[DayWithEngineers]
    engineers: list[EngineerInfo]


class TimeSeriesDataPoint(BaseModel):
    """Token totals for a single time bucket."""

    timestamp: str  # ISO format datetime string
    tokens: int
    tokens_input: int
    tokens_output: int
    cost_usd: float = 0.0


class TimeSeriesResponse(BaseModel):
    """Response for the time series chart endpoint."""

    engineer_id: str
    period: str  # 'hourly', 'daily', 'weekly', 'monthly'
    data: list[TimeSeriesDataPoint]
