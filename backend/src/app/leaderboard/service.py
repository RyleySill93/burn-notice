from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, cast, Date

from src.app.engineers.models import Engineer

# Timezone for day boundaries (when "today" starts/ends)
APP_TIMEZONE = ZoneInfo('America/Los_Angeles')


def get_today() -> date:
    """Get today's date in the app's configured timezone (PST/PDT)."""
    return datetime.now(APP_TIMEZONE).date()


def get_day_bounds_utc(for_date: date) -> tuple[datetime, datetime]:
    """
    Get the UTC datetime bounds for a PST/PDT day.
    Returns (start_utc, end_utc) where start is inclusive and end is exclusive.
    """
    # Create midnight in PST for the given date
    start_local = datetime(for_date.year, for_date.month, for_date.day, tzinfo=APP_TIMEZONE)
    end_local = start_local + timedelta(days=1)

    # Convert to UTC (naive datetimes for database comparison)
    start_utc = start_local.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
    end_utc = end_local.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

    return start_utc, end_utc
from src.app.leaderboard.domains import (
    DailyTotal,
    DailyTotalsResponse,
    DailyTotalsByEngineerResponse,
    DayWithEngineers,
    EngineerDailyTotal,
    EngineerInfo,
    EngineerStatsResponse,
    EngineerTimeSeriesData,
    HistoricalRank,
    HistoricalRankingsResponse,
    Leaderboard,
    LeaderboardEntry,
    PeriodStats,
    TeamTimeSeriesBucket,
    TeamTimeSeriesResponse,
    TimeSeriesDataPoint,
    TimeSeriesResponse,
    UsageStats,
)
from src.app.usage.models import TelemetryEvent, Usage, UsageDaily
from src.network.database import db


class LeaderboardService:
    @staticmethod
    def get_leaderboard(customer_id: str, as_of: date | None = None) -> Leaderboard:
        """Build leaderboard data for today (live), yesterday, weekly, and monthly views."""
        as_of = as_of or get_today()

        # Today shows LIVE data from raw usage table
        today = LeaderboardService._get_live_daily_leaderboard(customer_id, as_of)
        # Yesterday shows rolled up data
        yesterday = LeaderboardService._get_yesterday_leaderboard(customer_id, as_of)
        weekly = LeaderboardService._get_weekly_leaderboard(customer_id, as_of)
        monthly = LeaderboardService._get_monthly_leaderboard(customer_id, as_of)

        return Leaderboard(date=as_of, today=today, yesterday=yesterday, weekly=weekly, monthly=monthly)

    @staticmethod
    def _get_ranked_entries(
        customer_id: str,
        start_date: date,
        end_date: date,
        prev_start_date: date | None = None,
        prev_end_date: date | None = None,
    ) -> list[LeaderboardEntry]:
        """Get ranked entries for a date range with optional previous period comparison."""
        # Current period
        current_results = (
            db.session.query(
                UsageDaily.engineer_id,
                Engineer.display_name,
                func.sum(UsageDaily.total_tokens).label('tokens'),
                func.sum(UsageDaily.tokens_input).label('tokens_input'),
                func.sum(UsageDaily.tokens_output).label('tokens_output'),
                func.sum(UsageDaily.cost_usd).label('cost_usd'),
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date >= start_date,
                UsageDaily.date <= end_date,
            )
            .group_by(UsageDaily.engineer_id, Engineer.display_name)
            .having(func.sum(UsageDaily.total_tokens) > 0)
            .order_by(func.sum(UsageDaily.total_tokens).desc())
            .all()
        )

        # Previous period rankings (if provided)
        prev_rankings: dict[str, int] = {}
        if prev_start_date and prev_end_date:
            prev_results = (
                db.session.query(
                    UsageDaily.engineer_id,
                    func.sum(UsageDaily.total_tokens).label('tokens'),
                )
                .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    UsageDaily.date >= prev_start_date,
                    UsageDaily.date <= prev_end_date,
                )
                .group_by(UsageDaily.engineer_id)
                .having(func.sum(UsageDaily.total_tokens) > 0)
                .order_by(func.sum(UsageDaily.total_tokens).desc())
                .all()
            )
            for rank, row in enumerate(prev_results, 1):
                prev_rankings[row.engineer_id] = rank

        entries = []
        for rank, row in enumerate(current_results, 1):
            entries.append(
                LeaderboardEntry(
                    engineer_id=row.engineer_id,
                    display_name=row.display_name,
                    tokens=row.tokens,
                    tokens_input=row.tokens_input,
                    tokens_output=row.tokens_output,
                    cost_usd=row.cost_usd or 0.0,
                    rank=rank,
                    prev_rank=prev_rankings.get(row.engineer_id),
                )
            )

        return entries

    @staticmethod
    def _get_live_daily_leaderboard(customer_id: str, as_of: date) -> list[LeaderboardEntry]:
        """Get LIVE daily leaderboard from raw usage table for today."""
        # Get PST day bounds in UTC for database comparison
        start_utc, end_utc = get_day_bounds_utc(as_of)

        # Query raw usage table for today's data
        current_results = (
            db.session.query(
                Usage.engineer_id,
                Engineer.display_name,
                func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                func.sum(Usage.tokens_input).label('tokens_input'),
                func.sum(Usage.tokens_output).label('tokens_output'),
            )
            .join(Engineer, Usage.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                Usage.created_at >= start_utc,
                Usage.created_at < end_utc,
            )
            .group_by(Usage.engineer_id, Engineer.display_name)
            .having(func.sum(Usage.tokens_input + Usage.tokens_output) > 0)
            .order_by(func.sum(Usage.tokens_input + Usage.tokens_output).desc())
            .all()
        )

        # Get cost from TelemetryEvent for today
        cost_results = (
            db.session.query(
                TelemetryEvent.engineer_id,
                func.sum(TelemetryEvent.cost_usd).label('cost_usd'),
            )
            .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                TelemetryEvent.created_at >= start_utc,
                TelemetryEvent.created_at < end_utc,
            )
            .group_by(TelemetryEvent.engineer_id)
            .all()
        )
        cost_by_engineer = {r.engineer_id: r.cost_usd or 0.0 for r in cost_results}

        # Get yesterday's rankings for comparison
        yesterday = as_of - timedelta(days=1)
        yesterday_start_utc, yesterday_end_utc = get_day_bounds_utc(yesterday)
        prev_results = (
            db.session.query(
                Usage.engineer_id,
                func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
            )
            .join(Engineer, Usage.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                Usage.created_at >= yesterday_start_utc,
                Usage.created_at < yesterday_end_utc,
            )
            .group_by(Usage.engineer_id)
            .having(func.sum(Usage.tokens_input + Usage.tokens_output) > 0)
            .order_by(func.sum(Usage.tokens_input + Usage.tokens_output).desc())
            .all()
        )

        prev_rankings: dict[str, int] = {}
        for rank, row in enumerate(prev_results, 1):
            prev_rankings[row.engineer_id] = rank

        entries = []
        for rank, row in enumerate(current_results, 1):
            entries.append(
                LeaderboardEntry(
                    engineer_id=row.engineer_id,
                    display_name=row.display_name,
                    tokens=row.tokens,
                    tokens_input=row.tokens_input,
                    tokens_output=row.tokens_output,
                    cost_usd=cost_by_engineer.get(row.engineer_id, 0.0),
                    rank=rank,
                    prev_rank=prev_rankings.get(row.engineer_id),
                )
            )

        return entries

    @staticmethod
    def _get_yesterday_leaderboard(customer_id: str, as_of: date) -> list[LeaderboardEntry]:
        """Get yesterday's leaderboard from rolled up data with rank changes from day before."""
        yesterday = as_of - timedelta(days=1)
        day_before = as_of - timedelta(days=2)

        return LeaderboardService._get_ranked_entries(
            customer_id=customer_id,
            start_date=yesterday,
            end_date=yesterday,
            prev_start_date=day_before,
            prev_end_date=day_before,
        )

    @staticmethod
    def _get_weekly_leaderboard(customer_id: str, as_of: date) -> list[LeaderboardEntry]:
        """Get weekly leaderboard with rank changes from previous week."""
        # Current week (Mon-Sun containing as_of)
        week_start = as_of - timedelta(days=as_of.weekday())
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)

        return LeaderboardService._get_ranked_entries_with_live(
            customer_id=customer_id,
            start_date=week_start,
            end_date=as_of,
            prev_start_date=prev_week_start,
            prev_end_date=prev_week_end,
        )

    @staticmethod
    def _get_monthly_leaderboard(customer_id: str, as_of: date) -> list[LeaderboardEntry]:
        """Get monthly leaderboard with rank changes from previous month."""
        # Current month
        month_start = as_of.replace(day=1)
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        return LeaderboardService._get_ranked_entries_with_live(
            customer_id=customer_id,
            start_date=month_start,
            end_date=as_of,
            prev_start_date=prev_month_start,
            prev_end_date=prev_month_end,
        )

    @staticmethod
    def _get_ranked_entries_with_live(
        customer_id: str,
        start_date: date,
        end_date: date,
        prev_start_date: date | None = None,
        prev_end_date: date | None = None,
    ) -> list[LeaderboardEntry]:
        """Get ranked entries including live data for today."""
        today = get_today()

        # Get daily totals from UsageDaily (excluding today)
        daily_end = min(end_date, today - timedelta(days=1)) if end_date >= today else end_date

        # Store totals as dict of engineer_id -> (tokens, tokens_input, tokens_output, cost_usd)
        totals_by_engineer: dict[str, tuple[int, int, int, float]] = {}

        if start_date <= daily_end:
            daily_results = (
                db.session.query(
                    UsageDaily.engineer_id,
                    func.sum(UsageDaily.total_tokens).label('tokens'),
                    func.sum(UsageDaily.tokens_input).label('tokens_input'),
                    func.sum(UsageDaily.tokens_output).label('tokens_output'),
                    func.sum(UsageDaily.cost_usd).label('cost_usd'),
                )
                .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    UsageDaily.date >= start_date,
                    UsageDaily.date <= daily_end,
                )
                .group_by(UsageDaily.engineer_id)
                .all()
            )
            for r in daily_results:
                totals_by_engineer[r.engineer_id] = (r.tokens, r.tokens_input, r.tokens_output, r.cost_usd or 0.0)

        # Add live data for today if in range
        if start_date <= today <= end_date:
            today_start_utc, today_end_utc = get_day_bounds_utc(today)
            live_results = (
                db.session.query(
                    Usage.engineer_id,
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                    func.sum(Usage.tokens_input).label('tokens_input'),
                    func.sum(Usage.tokens_output).label('tokens_output'),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= today_start_utc,
                    Usage.created_at < today_end_utc,
                )
                .group_by(Usage.engineer_id)
                .all()
            )
            # Get cost from TelemetryEvent for today
            cost_results = (
                db.session.query(
                    TelemetryEvent.engineer_id,
                    func.sum(TelemetryEvent.cost_usd).label('cost_usd'),
                )
                .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    TelemetryEvent.created_at >= today_start_utc,
                    TelemetryEvent.created_at < today_end_utc,
                )
                .group_by(TelemetryEvent.engineer_id)
                .all()
            )
            live_cost_by_engineer = {r.engineer_id: r.cost_usd or 0.0 for r in cost_results}

            for r in live_results:
                existing = totals_by_engineer.get(r.engineer_id, (0, 0, 0, 0.0))
                live_cost = live_cost_by_engineer.get(r.engineer_id, 0.0)
                totals_by_engineer[r.engineer_id] = (
                    existing[0] + r.tokens,
                    existing[1] + r.tokens_input,
                    existing[2] + r.tokens_output,
                    existing[3] + live_cost,
                )

        # Get engineer names
        engineer_names = {
            e.id: e.display_name
            for e in db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()
        }

        # Sort and rank by total tokens
        sorted_results = sorted(
            [(eng_id, data) for eng_id, data in totals_by_engineer.items() if data[0] > 0],
            key=lambda x: x[1][0],
            reverse=True,
        )

        # Previous period rankings
        prev_rankings: dict[str, int] = {}
        if prev_start_date and prev_end_date:
            prev_results = (
                db.session.query(
                    UsageDaily.engineer_id,
                    func.sum(UsageDaily.total_tokens).label('tokens'),
                )
                .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    UsageDaily.date >= prev_start_date,
                    UsageDaily.date <= prev_end_date,
                )
                .group_by(UsageDaily.engineer_id)
                .having(func.sum(UsageDaily.total_tokens) > 0)
                .order_by(func.sum(UsageDaily.total_tokens).desc())
                .all()
            )
            for rank, row in enumerate(prev_results, 1):
                prev_rankings[row.engineer_id] = rank

        entries = []
        for rank, (eng_id, (tokens, tokens_input, tokens_output, cost_usd)) in enumerate(sorted_results, 1):
            entries.append(
                LeaderboardEntry(
                    engineer_id=eng_id,
                    display_name=engineer_names.get(eng_id, 'Unknown'),
                    tokens=tokens,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=cost_usd,
                    rank=rank,
                    prev_rank=prev_rankings.get(eng_id),
                )
            )

        return entries

    @staticmethod
    def get_usage_stats(customer_id: str, as_of: date | None = None) -> UsageStats:
        """Get usage stats comparing current period to same point in previous period."""
        as_of = as_of or get_today()

        # Today (live) vs yesterday at this point
        today_tokens = LeaderboardService._get_live_tokens_for_date_detailed(customer_id, as_of)
        yesterday_tokens = LeaderboardService._get_daily_tokens_detailed(customer_id, as_of - timedelta(days=1))

        # This week vs last week at this point
        # e.g., Mon-Wed this week vs Mon-Wed last week
        week_start = as_of - timedelta(days=as_of.weekday())
        day_of_week = as_of.weekday()  # 0=Mon, 6=Sun
        last_week_start = week_start - timedelta(days=7)
        last_week_same_day = last_week_start + timedelta(days=day_of_week)

        this_week_tokens = LeaderboardService._get_tokens_for_range_full_detailed(customer_id, week_start, as_of)
        last_week_tokens = LeaderboardService._get_tokens_for_range_full_detailed(customer_id, last_week_start, last_week_same_day)

        # This month vs last month at this point
        # e.g., 1st-5th this month vs 1st-5th last month
        month_start = as_of.replace(day=1)
        day_of_month = as_of.day
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        # Handle case where last month has fewer days
        last_month_same_day = min(day_of_month, last_month_end.day)
        last_month_comparison_end = last_month_start.replace(day=last_month_same_day)

        this_month_tokens = LeaderboardService._get_tokens_for_range_full_detailed(customer_id, month_start, as_of)
        last_month_tokens = LeaderboardService._get_tokens_for_range_full_detailed(customer_id, last_month_start, last_month_comparison_end)

        return UsageStats(
            date=as_of,
            today=PeriodStats(
                tokens=today_tokens[0],
                tokens_input=today_tokens[1],
                tokens_output=today_tokens[2],
                cost_usd=today_tokens[3],
                comparison_tokens=yesterday_tokens[0],
                comparison_tokens_input=yesterday_tokens[1],
                comparison_tokens_output=yesterday_tokens[2],
                comparison_cost_usd=yesterday_tokens[3],
            ),
            this_week=PeriodStats(
                tokens=this_week_tokens[0],
                tokens_input=this_week_tokens[1],
                tokens_output=this_week_tokens[2],
                cost_usd=this_week_tokens[3],
                comparison_tokens=last_week_tokens[0],
                comparison_tokens_input=last_week_tokens[1],
                comparison_tokens_output=last_week_tokens[2],
                comparison_cost_usd=last_week_tokens[3],
            ),
            this_month=PeriodStats(
                tokens=this_month_tokens[0],
                tokens_input=this_month_tokens[1],
                tokens_output=this_month_tokens[2],
                cost_usd=this_month_tokens[3],
                comparison_tokens=last_month_tokens[0],
                comparison_tokens_input=last_month_tokens[1],
                comparison_tokens_output=last_month_tokens[2],
                comparison_cost_usd=last_month_tokens[3],
            ),
        )

    @staticmethod
    def _get_live_tokens_for_date(customer_id: str, for_date: date) -> int:
        """Get total tokens for a date from live Usage table."""
        start_utc, end_utc = get_day_bounds_utc(for_date)
        result = (
            db.session.query(func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0))
            .join(Engineer, Usage.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                Usage.created_at >= start_utc,
                Usage.created_at < end_utc,
            )
            .scalar()
        )
        return result or 0

    @staticmethod
    def _get_live_tokens_for_date_detailed(customer_id: str, for_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown (total, input, output, cost) for a date from live Usage/TelemetryEvent table."""
        start_utc, end_utc = get_day_bounds_utc(for_date)
        result = (
            db.session.query(
                func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0),
                func.coalesce(func.sum(Usage.tokens_input), 0),
                func.coalesce(func.sum(Usage.tokens_output), 0),
            )
            .join(Engineer, Usage.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                Usage.created_at >= start_utc,
                Usage.created_at < end_utc,
            )
            .one()
        )
        # Get cost from TelemetryEvent
        cost_result = (
            db.session.query(func.coalesce(func.sum(TelemetryEvent.cost_usd), 0.0))
            .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                TelemetryEvent.created_at >= start_utc,
                TelemetryEvent.created_at < end_utc,
            )
            .scalar()
        )
        return (result[0] or 0, result[1] or 0, result[2] or 0, cost_result or 0.0)

    @staticmethod
    def _get_daily_tokens(customer_id: str, for_date: date) -> int:
        """Get total tokens for a date from UsageDaily (rolled up data)."""
        result = (
            db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date == for_date,
            )
            .scalar()
        )
        return result or 0

    @staticmethod
    def _get_daily_tokens_detailed(customer_id: str, for_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown (total, input, output, cost) for a date from UsageDaily."""
        result = (
            db.session.query(
                func.coalesce(func.sum(UsageDaily.total_tokens), 0),
                func.coalesce(func.sum(UsageDaily.tokens_input), 0),
                func.coalesce(func.sum(UsageDaily.tokens_output), 0),
                func.coalesce(func.sum(UsageDaily.cost_usd), 0.0),
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date == for_date,
            )
            .one()
        )
        return (result[0] or 0, result[1] or 0, result[2] or 0, result[3] or 0.0)

    @staticmethod
    def _get_tokens_for_range_full(customer_id: str, start_date: date, end_date: date) -> int:
        """Get total tokens for a date range (full days, no time cutoff)."""
        today = get_today()

        # Get from UsageDaily for all days except today
        if start_date <= end_date:
            daily_end = min(end_date, today - timedelta(days=1)) if end_date >= today else end_date
            if start_date <= daily_end:
                daily_result = (
                    db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
                    .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                    .filter(
                        Engineer.customer_id == customer_id,
                        UsageDaily.date >= start_date,
                        UsageDaily.date <= daily_end,
                    )
                    .scalar()
                ) or 0
            else:
                daily_result = 0
        else:
            daily_result = 0

        # Add live data for today if in range
        if start_date <= today <= end_date:
            live_result = LeaderboardService._get_live_tokens_for_date(customer_id, today)
        else:
            live_result = 0

        return daily_result + live_result

    @staticmethod
    def _get_tokens_for_range_full_detailed(customer_id: str, start_date: date, end_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown (total, input, output, cost) for a date range (full days, no time cutoff)."""
        today = get_today()

        # Get from UsageDaily for all days except today
        daily_total, daily_input, daily_output, daily_cost = 0, 0, 0, 0.0
        if start_date <= end_date:
            daily_end = min(end_date, today - timedelta(days=1)) if end_date >= today else end_date
            if start_date <= daily_end:
                result = (
                    db.session.query(
                        func.coalesce(func.sum(UsageDaily.total_tokens), 0),
                        func.coalesce(func.sum(UsageDaily.tokens_input), 0),
                        func.coalesce(func.sum(UsageDaily.tokens_output), 0),
                        func.coalesce(func.sum(UsageDaily.cost_usd), 0.0),
                    )
                    .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                    .filter(
                        Engineer.customer_id == customer_id,
                        UsageDaily.date >= start_date,
                        UsageDaily.date <= daily_end,
                    )
                    .one()
                )
                daily_total = result[0] or 0
                daily_input = result[1] or 0
                daily_output = result[2] or 0
                daily_cost = result[3] or 0.0

        # Add live data for today if in range
        live_total, live_input, live_output, live_cost = 0, 0, 0, 0.0
        if start_date <= today <= end_date:
            live_total, live_input, live_output, live_cost = LeaderboardService._get_live_tokens_for_date_detailed(customer_id, today)

        return (daily_total + live_total, daily_input + live_input, daily_output + live_output, daily_cost + live_cost)

    @staticmethod
    def _get_tokens_up_to_time(customer_id: str, for_date: date, up_to_time) -> int:
        """Get total tokens for a date up to a specific time of day (in PST)."""
        # Create the cutoff time in PST, then convert to UTC
        cutoff_local = datetime.combine(for_date, up_to_time).replace(tzinfo=APP_TIMEZONE)
        cutoff_utc = cutoff_local.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        start_utc, _ = get_day_bounds_utc(for_date)

        result = (
            db.session.query(func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0))
            .join(Engineer, Usage.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                Usage.created_at >= start_utc,
                Usage.created_at <= cutoff_utc,
            )
            .scalar()
        )
        return result or 0

    @staticmethod
    def _get_tokens_for_range(customer_id: str, start_date: date, end_date: date, up_to_time=None) -> int:
        """Get total tokens for a date range, with optional time cutoff on end_date."""
        # For dates before end_date, use full day from UsageDaily
        if start_date < end_date:
            daily_result = (
                db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
                .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    UsageDaily.date >= start_date,
                    UsageDaily.date < end_date,
                )
                .scalar()
            ) or 0
        else:
            daily_result = 0

        # For end_date, use raw Usage with time cutoff if provided
        if up_to_time:
            end_date_result = LeaderboardService._get_tokens_up_to_time(customer_id, end_date, up_to_time)
        else:
            start_utc, end_utc = get_day_bounds_utc(end_date)
            end_date_result = (
                db.session.query(func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0))
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at < end_utc,
                )
                .scalar()
            ) or 0

        return daily_result + end_date_result

    @staticmethod
    def get_daily_totals(customer_id: str, start_date: date, end_date: date | None = None) -> DailyTotalsResponse:
        """Get daily token totals for charting."""
        end_date = end_date or get_today()

        # Get rolled up data from UsageDaily for all days except today
        daily_results = (
            db.session.query(
                UsageDaily.date,
                func.sum(UsageDaily.total_tokens).label('tokens'),
                func.sum(UsageDaily.tokens_input).label('tokens_input'),
                func.sum(UsageDaily.tokens_output).label('tokens_output'),
                func.sum(UsageDaily.cost_usd).label('cost_usd'),
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date >= start_date,
                UsageDaily.date <= end_date,
            )
            .group_by(UsageDaily.date)
            .order_by(UsageDaily.date)
            .all()
        )

        # Build a dict of date -> (tokens, tokens_input, tokens_output, cost_usd)
        totals_by_date: dict[date, tuple[int, int, int, float]] = {
            row.date: (row.tokens, row.tokens_input, row.tokens_output, row.cost_usd or 0.0) for row in daily_results
        }

        # If end_date is today, get live data from Usage/TelemetryEvent table
        today = get_today()
        if end_date >= today:
            today_start_utc, today_end_utc = get_day_bounds_utc(today)
            live_result = (
                db.session.query(
                    func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0),
                    func.coalesce(func.sum(Usage.tokens_input), 0),
                    func.coalesce(func.sum(Usage.tokens_output), 0),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= today_start_utc,
                    Usage.created_at < today_end_utc,
                )
                .one()
            )
            # Get cost from TelemetryEvent for today
            cost_result = (
                db.session.query(func.coalesce(func.sum(TelemetryEvent.cost_usd), 0.0))
                .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    TelemetryEvent.created_at >= today_start_utc,
                    TelemetryEvent.created_at < today_end_utc,
                )
                .scalar()
            )
            totals_by_date[today] = (live_result[0] or 0, live_result[1] or 0, live_result[2] or 0, cost_result or 0.0)

        # Build complete list with zeros for missing days
        totals = []
        current = start_date
        while current <= end_date:
            data = totals_by_date.get(current, (0, 0, 0, 0.0))
            totals.append(DailyTotal(date=current, tokens=data[0], tokens_input=data[1], tokens_output=data[2], cost_usd=data[3]))
            current += timedelta(days=1)

        return DailyTotalsResponse(start_date=start_date, end_date=end_date, totals=totals)

    @staticmethod
    def get_engineer_stats(engineer_id: str, as_of: date | None = None) -> EngineerStatsResponse:
        """Get usage stats for a specific engineer comparing to same point in previous period."""
        as_of = as_of or get_today()

        engineer = Engineer.get(id=engineer_id)

        # Today (live) vs yesterday at this point
        today_tokens = LeaderboardService._get_engineer_live_tokens_detailed(engineer_id, as_of)
        yesterday_tokens = LeaderboardService._get_engineer_daily_tokens_detailed(engineer_id, as_of - timedelta(days=1))

        # This week vs last week at this point
        week_start = as_of - timedelta(days=as_of.weekday())
        day_of_week = as_of.weekday()
        last_week_start = week_start - timedelta(days=7)
        last_week_same_day = last_week_start + timedelta(days=day_of_week)

        this_week_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(engineer_id, week_start, as_of)
        last_week_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(engineer_id, last_week_start, last_week_same_day)

        # This month vs last month at this point
        month_start = as_of.replace(day=1)
        day_of_month = as_of.day
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        last_month_same_day = min(day_of_month, last_month_end.day)
        last_month_comparison_end = last_month_start.replace(day=last_month_same_day)

        this_month_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(engineer_id, month_start, as_of)
        last_month_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(engineer_id, last_month_start, last_month_comparison_end)

        return EngineerStatsResponse(
            engineer_id=engineer_id,
            display_name=engineer.display_name,
            date=as_of,
            today=PeriodStats(
                tokens=today_tokens[0],
                tokens_input=today_tokens[1],
                tokens_output=today_tokens[2],
                cost_usd=today_tokens[3],
                comparison_tokens=yesterday_tokens[0],
                comparison_tokens_input=yesterday_tokens[1],
                comparison_tokens_output=yesterday_tokens[2],
                comparison_cost_usd=yesterday_tokens[3],
            ),
            this_week=PeriodStats(
                tokens=this_week_tokens[0],
                tokens_input=this_week_tokens[1],
                tokens_output=this_week_tokens[2],
                cost_usd=this_week_tokens[3],
                comparison_tokens=last_week_tokens[0],
                comparison_tokens_input=last_week_tokens[1],
                comparison_tokens_output=last_week_tokens[2],
                comparison_cost_usd=last_week_tokens[3],
            ),
            this_month=PeriodStats(
                tokens=this_month_tokens[0],
                tokens_input=this_month_tokens[1],
                tokens_output=this_month_tokens[2],
                cost_usd=this_month_tokens[3],
                comparison_tokens=last_month_tokens[0],
                comparison_tokens_input=last_month_tokens[1],
                comparison_tokens_output=last_month_tokens[2],
                comparison_cost_usd=last_month_tokens[3],
            ),
        )

    @staticmethod
    def _get_engineer_live_tokens(engineer_id: str, for_date: date) -> int:
        """Get total tokens for an engineer from live Usage table."""
        start_utc, end_utc = get_day_bounds_utc(for_date)
        result = (
            db.session.query(func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0))
            .filter(
                Usage.engineer_id == engineer_id,
                Usage.created_at >= start_utc,
                Usage.created_at < end_utc,
            )
            .scalar()
        )
        return result or 0

    @staticmethod
    def _get_engineer_live_tokens_detailed(engineer_id: str, for_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown (total, input, output, cost) for an engineer from live Usage/TelemetryEvent table."""
        start_utc, end_utc = get_day_bounds_utc(for_date)
        result = (
            db.session.query(
                func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0),
                func.coalesce(func.sum(Usage.tokens_input), 0),
                func.coalesce(func.sum(Usage.tokens_output), 0),
            )
            .filter(
                Usage.engineer_id == engineer_id,
                Usage.created_at >= start_utc,
                Usage.created_at < end_utc,
            )
            .one()
        )
        # Get cost from TelemetryEvent
        cost_result = (
            db.session.query(func.coalesce(func.sum(TelemetryEvent.cost_usd), 0.0))
            .filter(
                TelemetryEvent.engineer_id == engineer_id,
                TelemetryEvent.created_at >= start_utc,
                TelemetryEvent.created_at < end_utc,
            )
            .scalar()
        )
        return (result[0] or 0, result[1] or 0, result[2] or 0, cost_result or 0.0)

    @staticmethod
    def _get_engineer_daily_tokens(engineer_id: str, for_date: date) -> int:
        """Get total tokens for an engineer from UsageDaily."""
        result = (
            db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
            .filter(
                UsageDaily.engineer_id == engineer_id,
                UsageDaily.date == for_date,
            )
            .scalar()
        )
        return result or 0

    @staticmethod
    def _get_engineer_daily_tokens_detailed(engineer_id: str, for_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown (total, input, output, cost) for an engineer from UsageDaily."""
        result = (
            db.session.query(
                func.coalesce(func.sum(UsageDaily.total_tokens), 0),
                func.coalesce(func.sum(UsageDaily.tokens_input), 0),
                func.coalesce(func.sum(UsageDaily.tokens_output), 0),
                func.coalesce(func.sum(UsageDaily.cost_usd), 0.0),
            )
            .filter(
                UsageDaily.engineer_id == engineer_id,
                UsageDaily.date == for_date,
            )
            .one()
        )
        return (result[0] or 0, result[1] or 0, result[2] or 0, result[3] or 0.0)

    @staticmethod
    def _get_engineer_tokens_for_range_full(engineer_id: str, start_date: date, end_date: date) -> int:
        """Get total tokens for an engineer in a date range (full days)."""
        today = get_today()

        # Get from UsageDaily for all days except today
        if start_date <= end_date:
            daily_end = min(end_date, today - timedelta(days=1)) if end_date >= today else end_date
            if start_date <= daily_end:
                daily_result = (
                    db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
                    .filter(
                        UsageDaily.engineer_id == engineer_id,
                        UsageDaily.date >= start_date,
                        UsageDaily.date <= daily_end,
                    )
                    .scalar()
                ) or 0
            else:
                daily_result = 0
        else:
            daily_result = 0

        # Add live data for today if in range
        if start_date <= today <= end_date:
            live_result = LeaderboardService._get_engineer_live_tokens(engineer_id, today)
        else:
            live_result = 0

        return daily_result + live_result

    @staticmethod
    def _get_engineer_tokens_for_range_full_detailed(engineer_id: str, start_date: date, end_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown (total, input, output, cost) for an engineer in a date range (full days)."""
        today = get_today()

        # Get from UsageDaily for all days except today
        daily_total, daily_input, daily_output, daily_cost = 0, 0, 0, 0.0
        if start_date <= end_date:
            daily_end = min(end_date, today - timedelta(days=1)) if end_date >= today else end_date
            if start_date <= daily_end:
                result = (
                    db.session.query(
                        func.coalesce(func.sum(UsageDaily.total_tokens), 0),
                        func.coalesce(func.sum(UsageDaily.tokens_input), 0),
                        func.coalesce(func.sum(UsageDaily.tokens_output), 0),
                        func.coalesce(func.sum(UsageDaily.cost_usd), 0.0),
                    )
                    .filter(
                        UsageDaily.engineer_id == engineer_id,
                        UsageDaily.date >= start_date,
                        UsageDaily.date <= daily_end,
                    )
                    .one()
                )
                daily_total = result[0] or 0
                daily_input = result[1] or 0
                daily_output = result[2] or 0
                daily_cost = result[3] or 0.0

        # Add live data for today if in range
        live_total, live_input, live_output, live_cost = 0, 0, 0, 0.0
        if start_date <= today <= end_date:
            live_total, live_input, live_output, live_cost = LeaderboardService._get_engineer_live_tokens_detailed(engineer_id, today)

        return (daily_total + live_total, daily_input + live_input, daily_output + live_output, daily_cost + live_cost)

    @staticmethod
    def _get_engineer_tokens_up_to_time(engineer_id: str, for_date: date, up_to_time) -> int:
        """Get tokens for a specific engineer up to a time of day (in PST)."""
        # Create the cutoff time in PST, then convert to UTC
        cutoff_local = datetime.combine(for_date, up_to_time).replace(tzinfo=APP_TIMEZONE)
        cutoff_utc = cutoff_local.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        start_utc, _ = get_day_bounds_utc(for_date)

        result = (
            db.session.query(func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0))
            .filter(
                Usage.engineer_id == engineer_id,
                Usage.created_at >= start_utc,
                Usage.created_at <= cutoff_utc,
            )
            .scalar()
        )
        return result or 0

    @staticmethod
    def _get_engineer_tokens_for_range(engineer_id: str, start_date: date, end_date: date, up_to_time=None) -> int:
        """Get tokens for a specific engineer in a date range."""
        if start_date < end_date:
            daily_result = (
                db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
                .filter(
                    UsageDaily.engineer_id == engineer_id,
                    UsageDaily.date >= start_date,
                    UsageDaily.date < end_date,
                )
                .scalar()
            ) or 0
        else:
            daily_result = 0

        if up_to_time:
            end_date_result = LeaderboardService._get_engineer_tokens_up_to_time(engineer_id, end_date, up_to_time)
        else:
            start_utc, end_utc = get_day_bounds_utc(end_date)
            end_date_result = (
                db.session.query(func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0))
                .filter(
                    Usage.engineer_id == engineer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at < end_utc,
                )
                .scalar()
            ) or 0

        return daily_result + end_date_result

    @staticmethod
    def get_engineer_daily_totals(engineer_id: str, start_date: date, end_date: date | None = None) -> DailyTotalsResponse:
        """Get daily token totals for a specific engineer."""
        end_date = end_date or get_today()

        daily_results = (
            db.session.query(
                UsageDaily.date,
                UsageDaily.total_tokens.label('tokens'),
                UsageDaily.tokens_input,
                UsageDaily.tokens_output,
                UsageDaily.cost_usd,
            )
            .filter(
                UsageDaily.engineer_id == engineer_id,
                UsageDaily.date >= start_date,
                UsageDaily.date <= end_date,
            )
            .order_by(UsageDaily.date)
            .all()
        )

        # Build a dict of date -> (tokens, tokens_input, tokens_output, cost_usd)
        totals_by_date: dict[date, tuple[int, int, int, float]] = {
            row.date: (row.tokens, row.tokens_input, row.tokens_output, row.cost_usd or 0.0) for row in daily_results
        }

        # Live data for today
        today = get_today()
        if end_date >= today:
            today_start_utc, today_end_utc = get_day_bounds_utc(today)
            live_result = (
                db.session.query(
                    func.coalesce(func.sum(Usage.tokens_input + Usage.tokens_output), 0),
                    func.coalesce(func.sum(Usage.tokens_input), 0),
                    func.coalesce(func.sum(Usage.tokens_output), 0),
                )
                .filter(
                    Usage.engineer_id == engineer_id,
                    Usage.created_at >= today_start_utc,
                    Usage.created_at < today_end_utc,
                )
                .one()
            )
            # Get cost from TelemetryEvent for today
            cost_result = (
                db.session.query(func.coalesce(func.sum(TelemetryEvent.cost_usd), 0.0))
                .filter(
                    TelemetryEvent.engineer_id == engineer_id,
                    TelemetryEvent.created_at >= today_start_utc,
                    TelemetryEvent.created_at < today_end_utc,
                )
                .scalar()
            )
            totals_by_date[today] = (live_result[0] or 0, live_result[1] or 0, live_result[2] or 0, cost_result or 0.0)

        totals = []
        current = start_date
        while current <= end_date:
            data = totals_by_date.get(current, (0, 0, 0, 0.0))
            totals.append(DailyTotal(date=current, tokens=data[0], tokens_input=data[1], tokens_output=data[2], cost_usd=data[3]))
            current += timedelta(days=1)

        return DailyTotalsResponse(start_date=start_date, end_date=end_date, totals=totals)

    @staticmethod
    def get_historical_rankings(
        customer_id: str, engineer_id: str, period_type: str, num_periods: int = 20
    ) -> HistoricalRankingsResponse:
        """Get historical rankings for an engineer over past periods."""
        today = get_today()
        rankings = []

        if period_type == 'daily':
            for i in range(num_periods):
                period_date = today - timedelta(days=i)
                rank, tokens, tokens_input, tokens_output, cost_usd = LeaderboardService._get_rank_for_day_detailed(customer_id, engineer_id, period_date)
                rankings.append(HistoricalRank(
                    period_start=period_date,
                    period_end=period_date,
                    rank=rank,
                    tokens=tokens,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=cost_usd,
                ))

        elif period_type == 'weekly':
            # Start from current week
            current_week_start = today - timedelta(days=today.weekday())
            for i in range(num_periods):
                week_start = current_week_start - timedelta(weeks=i)
                week_end = week_start + timedelta(days=6)
                if week_end > today:
                    week_end = today
                rank, tokens, tokens_input, tokens_output, cost_usd = LeaderboardService._get_rank_for_range_detailed(customer_id, engineer_id, week_start, week_end)
                rankings.append(HistoricalRank(
                    period_start=week_start,
                    period_end=week_end,
                    rank=rank,
                    tokens=tokens,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=cost_usd,
                ))

        elif period_type == 'monthly':
            current_month_start = today.replace(day=1)
            for i in range(num_periods):
                if i == 0:
                    month_start = current_month_start
                    month_end = today
                else:
                    # Go back i months
                    year = current_month_start.year
                    month = current_month_start.month - i
                    while month <= 0:
                        month += 12
                        year -= 1
                    month_start = date(year, month, 1)
                    # End of that month
                    if month == 12:
                        month_end = date(year + 1, 1, 1) - timedelta(days=1)
                    else:
                        month_end = date(year, month + 1, 1) - timedelta(days=1)

                rank, tokens, tokens_input, tokens_output, cost_usd = LeaderboardService._get_rank_for_range_detailed(customer_id, engineer_id, month_start, month_end)
                rankings.append(HistoricalRank(
                    period_start=month_start,
                    period_end=month_end,
                    rank=rank,
                    tokens=tokens,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=cost_usd,
                ))

        return HistoricalRankingsResponse(
            engineer_id=engineer_id,
            period_type=period_type,
            rankings=rankings,
        )

    @staticmethod
    def _get_rank_for_day(customer_id: str, engineer_id: str, for_date: date) -> tuple[int | None, int]:
        """Get an engineer's rank for a specific day."""
        today = get_today()

        if for_date == today:
            # Use live data
            start_utc, end_utc = get_day_bounds_utc(for_date)
            results = (
                db.session.query(
                    Usage.engineer_id,
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at < end_utc,
                )
                .group_by(Usage.engineer_id)
                .having(func.sum(Usage.tokens_input + Usage.tokens_output) > 0)
                .order_by(func.sum(Usage.tokens_input + Usage.tokens_output).desc())
                .all()
            )
        else:
            # Use daily rollup
            results = (
                db.session.query(
                    UsageDaily.engineer_id,
                    UsageDaily.total_tokens.label('tokens'),
                )
                .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    UsageDaily.date == for_date,
                    UsageDaily.total_tokens > 0,
                )
                .order_by(UsageDaily.total_tokens.desc())
                .all()
            )

        for rank, row in enumerate(results, 1):
            if row.engineer_id == engineer_id:
                return rank, row.tokens

        return None, 0

    @staticmethod
    def _get_rank_for_day_detailed(customer_id: str, engineer_id: str, for_date: date) -> tuple[int | None, int, int, int, float]:
        """Get an engineer's rank and token breakdown for a specific day."""
        today = get_today()

        if for_date == today:
            # Use live data
            start_utc, end_utc = get_day_bounds_utc(for_date)
            results = (
                db.session.query(
                    Usage.engineer_id,
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                    func.sum(Usage.tokens_input).label('tokens_input'),
                    func.sum(Usage.tokens_output).label('tokens_output'),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at < end_utc,
                )
                .group_by(Usage.engineer_id)
                .having(func.sum(Usage.tokens_input + Usage.tokens_output) > 0)
                .order_by(func.sum(Usage.tokens_input + Usage.tokens_output).desc())
                .all()
            )
            # Get cost from TelemetryEvent for today
            cost_results = (
                db.session.query(
                    TelemetryEvent.engineer_id,
                    func.sum(TelemetryEvent.cost_usd).label('cost_usd'),
                )
                .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    TelemetryEvent.created_at >= start_utc,
                    TelemetryEvent.created_at < end_utc,
                )
                .group_by(TelemetryEvent.engineer_id)
                .all()
            )
            cost_by_engineer = {r.engineer_id: r.cost_usd or 0.0 for r in cost_results}

            for rank, row in enumerate(results, 1):
                if row.engineer_id == engineer_id:
                    return rank, row.tokens, row.tokens_input, row.tokens_output, cost_by_engineer.get(engineer_id, 0.0)
            return None, 0, 0, 0, 0.0
        else:
            # Use daily rollup
            results = (
                db.session.query(
                    UsageDaily.engineer_id,
                    UsageDaily.total_tokens.label('tokens'),
                    UsageDaily.tokens_input,
                    UsageDaily.tokens_output,
                    UsageDaily.cost_usd,
                )
                .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    UsageDaily.date == for_date,
                    UsageDaily.total_tokens > 0,
                )
                .order_by(UsageDaily.total_tokens.desc())
                .all()
            )

            for rank, row in enumerate(results, 1):
                if row.engineer_id == engineer_id:
                    return rank, row.tokens, row.tokens_input, row.tokens_output, row.cost_usd or 0.0

        return None, 0, 0, 0, 0.0

    @staticmethod
    def _get_rank_for_range(customer_id: str, engineer_id: str, start_date: date, end_date: date) -> tuple[int | None, int]:
        """Get an engineer's rank for a date range."""
        today = get_today()

        # Get aggregated totals for the range
        results = (
            db.session.query(
                UsageDaily.engineer_id,
                func.sum(UsageDaily.total_tokens).label('tokens'),
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date >= start_date,
                UsageDaily.date <= end_date,
            )
            .group_by(UsageDaily.engineer_id)
            .having(func.sum(UsageDaily.total_tokens) > 0)
            .order_by(func.sum(UsageDaily.total_tokens).desc())
            .all()
        )

        # If range includes today, add live data
        if end_date >= today:
            today_start_utc, today_end_utc = get_day_bounds_utc(today)
            live_results = (
                db.session.query(
                    Usage.engineer_id,
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= today_start_utc,
                    Usage.created_at < today_end_utc,
                )
                .group_by(Usage.engineer_id)
                .all()
            )
            live_by_engineer = {r.engineer_id: r.tokens for r in live_results}

            # Merge live data with daily data
            totals_by_engineer = {r.engineer_id: r.tokens for r in results}
            for eng_id, tokens in live_by_engineer.items():
                totals_by_engineer[eng_id] = totals_by_engineer.get(eng_id, 0) + tokens

            # Re-sort
            sorted_results = sorted(totals_by_engineer.items(), key=lambda x: x[1], reverse=True)
            for rank, (eng_id, tokens) in enumerate(sorted_results, 1):
                if eng_id == engineer_id:
                    return rank, tokens
            return None, 0

        for rank, row in enumerate(results, 1):
            if row.engineer_id == engineer_id:
                return rank, row.tokens

        return None, 0

    @staticmethod
    def _get_rank_for_range_detailed(customer_id: str, engineer_id: str, start_date: date, end_date: date) -> tuple[int | None, int, int, int, float]:
        """Get an engineer's rank and token breakdown for a date range."""
        today = get_today()

        # Get aggregated totals for the range
        results = (
            db.session.query(
                UsageDaily.engineer_id,
                func.sum(UsageDaily.total_tokens).label('tokens'),
                func.sum(UsageDaily.tokens_input).label('tokens_input'),
                func.sum(UsageDaily.tokens_output).label('tokens_output'),
                func.sum(UsageDaily.cost_usd).label('cost_usd'),
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date >= start_date,
                UsageDaily.date <= end_date,
            )
            .group_by(UsageDaily.engineer_id)
            .having(func.sum(UsageDaily.total_tokens) > 0)
            .order_by(func.sum(UsageDaily.total_tokens).desc())
            .all()
        )

        # If range includes today, add live data
        if end_date >= today:
            today_start_utc, today_end_utc = get_day_bounds_utc(today)
            live_results = (
                db.session.query(
                    Usage.engineer_id,
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                    func.sum(Usage.tokens_input).label('tokens_input'),
                    func.sum(Usage.tokens_output).label('tokens_output'),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= today_start_utc,
                    Usage.created_at < today_end_utc,
                )
                .group_by(Usage.engineer_id)
                .all()
            )
            # Get cost from TelemetryEvent for today
            cost_results = (
                db.session.query(
                    TelemetryEvent.engineer_id,
                    func.sum(TelemetryEvent.cost_usd).label('cost_usd'),
                )
                .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    TelemetryEvent.created_at >= today_start_utc,
                    TelemetryEvent.created_at < today_end_utc,
                )
                .group_by(TelemetryEvent.engineer_id)
                .all()
            )
            live_cost_by_engineer = {r.engineer_id: r.cost_usd or 0.0 for r in cost_results}
            live_by_engineer = {r.engineer_id: (r.tokens, r.tokens_input, r.tokens_output) for r in live_results}

            # Merge live data with daily data: dict of engineer_id -> (tokens, tokens_input, tokens_output, cost_usd)
            totals_by_engineer: dict[str, tuple[int, int, int, float]] = {
                r.engineer_id: (r.tokens, r.tokens_input, r.tokens_output, r.cost_usd or 0.0) for r in results
            }
            for eng_id, (tokens, tokens_input, tokens_output) in live_by_engineer.items():
                existing = totals_by_engineer.get(eng_id, (0, 0, 0, 0.0))
                live_cost = live_cost_by_engineer.get(eng_id, 0.0)
                totals_by_engineer[eng_id] = (
                    existing[0] + tokens,
                    existing[1] + tokens_input,
                    existing[2] + tokens_output,
                    existing[3] + live_cost,
                )

            # Re-sort by total tokens
            sorted_results = sorted(totals_by_engineer.items(), key=lambda x: x[1][0], reverse=True)
            for rank, (eng_id, (tokens, tokens_input, tokens_output, cost_usd)) in enumerate(sorted_results, 1):
                if eng_id == engineer_id:
                    return rank, tokens, tokens_input, tokens_output, cost_usd
            return None, 0, 0, 0, 0.0

        for rank, row in enumerate(results, 1):
            if row.engineer_id == engineer_id:
                return rank, row.tokens, row.tokens_input, row.tokens_output, row.cost_usd or 0.0

        return None, 0, 0, 0, 0.0

    @staticmethod
    def get_daily_totals_by_engineer(
        customer_id: str, start_date: date, end_date: date
    ) -> DailyTotalsByEngineerResponse:
        """Get daily token totals broken down by engineer for charting."""
        today = get_today()

        # Get all engineers for this customer
        all_engineers = (
            db.session.query(Engineer.id, Engineer.display_name)
            .filter(Engineer.customer_id == customer_id)
            .all()
        )
        engineer_names = {e.id: e.display_name for e in all_engineers}

        # Get rolled up data from UsageDaily for all days except today
        daily_results = (
            db.session.query(
                UsageDaily.date,
                UsageDaily.engineer_id,
                func.sum(UsageDaily.total_tokens).label('tokens'),
                func.sum(UsageDaily.tokens_input).label('tokens_input'),
                func.sum(UsageDaily.tokens_output).label('tokens_output'),
                func.sum(UsageDaily.cost_usd).label('cost_usd'),
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date >= start_date,
                UsageDaily.date <= end_date,
            )
            .group_by(UsageDaily.date, UsageDaily.engineer_id)
            .order_by(UsageDaily.date, UsageDaily.engineer_id)
            .all()
        )

        # Build a dict of date -> engineer_id -> (tokens, tokens_input, tokens_output, cost_usd)
        data_by_date: dict[date, dict[str, tuple[int, int, int, float]]] = {}
        engineers_with_data: set[str] = set()

        for row in daily_results:
            if row.date not in data_by_date:
                data_by_date[row.date] = {}
            data_by_date[row.date][row.engineer_id] = (
                row.tokens,
                row.tokens_input,
                row.tokens_output,
                row.cost_usd or 0.0,
            )
            engineers_with_data.add(row.engineer_id)

        # If end_date is today, get live data from Usage/TelemetryEvent table
        if end_date >= today:
            today_start_utc, today_end_utc = get_day_bounds_utc(today)
            live_results = (
                db.session.query(
                    Usage.engineer_id,
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                    func.sum(Usage.tokens_input).label('tokens_input'),
                    func.sum(Usage.tokens_output).label('tokens_output'),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= today_start_utc,
                    Usage.created_at < today_end_utc,
                )
                .group_by(Usage.engineer_id)
                .all()
            )
            # Get cost from TelemetryEvent for today
            cost_results = (
                db.session.query(
                    TelemetryEvent.engineer_id,
                    func.sum(TelemetryEvent.cost_usd).label('cost_usd'),
                )
                .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    TelemetryEvent.created_at >= today_start_utc,
                    TelemetryEvent.created_at < today_end_utc,
                )
                .group_by(TelemetryEvent.engineer_id)
                .all()
            )
            cost_by_engineer = {r.engineer_id: r.cost_usd or 0.0 for r in cost_results}

            if today not in data_by_date:
                data_by_date[today] = {}
            for r in live_results:
                data_by_date[today][r.engineer_id] = (
                    r.tokens or 0,
                    r.tokens_input or 0,
                    r.tokens_output or 0,
                    cost_by_engineer.get(r.engineer_id, 0.0),
                )
                engineers_with_data.add(r.engineer_id)

        # Build response with all days in range
        days = []
        current = start_date
        while current <= end_date:
            day_data = data_by_date.get(current, {})
            engineers_for_day = []
            for eng_id, (tokens, tokens_input, tokens_output, cost_usd) in day_data.items():
                engineers_for_day.append(
                    EngineerDailyTotal(
                        engineer_id=eng_id,
                        display_name=engineer_names.get(eng_id, 'Unknown'),
                        tokens=tokens,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        cost_usd=cost_usd,
                    )
                )
            days.append(DayWithEngineers(date=current, engineers=engineers_for_day))
            current += timedelta(days=1)

        # Build engineer list (only engineers who have data in the range)
        engineers = [
            EngineerInfo(id=eng_id, display_name=engineer_names.get(eng_id, 'Unknown'))
            for eng_id in sorted(engineers_with_data)
            if eng_id in engineer_names
        ]

        return DailyTotalsByEngineerResponse(
            start_date=start_date,
            end_date=end_date,
            days=days,
            engineers=engineers,
        )

    @staticmethod
    def get_engineer_time_series(
        engineer_id: str,
        period: str = 'hourly',
        as_of: date | None = None,
    ) -> TimeSeriesResponse:
        """
        Get time series data for an engineer.

        Periods and their granularity:
        - hourly: 24 hours for selected day, hourly buckets
        - daily: last 30 days, daily buckets
        - weekly: last 12 weeks, weekly buckets
        - monthly: last 12 months, monthly buckets
        """
        now = datetime.now(APP_TIMEZONE)
        as_of_date = as_of or get_today()

        if period == 'hourly':
            # 24 hours for the selected day with hourly granularity
            start_time = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=APP_TIMEZONE)
            end_of_day = start_time + timedelta(days=1)
            # If viewing today, only go up to now; otherwise show full day
            end_time = min(end_of_day, now)
            trunc_interval = 'hour'
            bucket_minutes = 60
        elif period == 'daily':
            # Last 30 days with daily granularity
            end_date = as_of_date
            start_date = end_date - timedelta(days=29)
            start_time = datetime(start_date.year, start_date.month, start_date.day, tzinfo=APP_TIMEZONE)
            end_time = datetime(end_date.year, end_date.month, end_date.day, tzinfo=APP_TIMEZONE) + timedelta(days=1)
            if end_time > now:
                end_time = now
            trunc_interval = 'day'
            bucket_minutes = 1440
        elif period == 'weekly':
            # Last 12 weeks with weekly granularity
            # Find the start of the current week (Monday)
            days_since_monday = as_of_date.weekday()
            current_week_start = as_of_date - timedelta(days=days_since_monday)
            start_date = current_week_start - timedelta(weeks=11)
            start_time = datetime(start_date.year, start_date.month, start_date.day, tzinfo=APP_TIMEZONE)
            end_time = datetime(current_week_start.year, current_week_start.month, current_week_start.day, tzinfo=APP_TIMEZONE) + timedelta(days=7)
            if end_time > now:
                end_time = now
            trunc_interval = 'week'
            bucket_minutes = 10080  # 7 days
        else:  # monthly
            # Last 12 months with monthly granularity
            current_month_start = as_of_date.replace(day=1)
            # Go back 11 months
            year = current_month_start.year
            month = current_month_start.month - 11
            while month <= 0:
                month += 12
                year -= 1
            start_date = date(year, month, 1)
            start_time = datetime(start_date.year, start_date.month, start_date.day, tzinfo=APP_TIMEZONE)
            # End at the end of current month
            if current_month_start.month == 12:
                next_month = date(current_month_start.year + 1, 1, 1)
            else:
                next_month = date(current_month_start.year, current_month_start.month + 1, 1)
            end_time = datetime(next_month.year, next_month.month, next_month.day, tzinfo=APP_TIMEZONE)
            if end_time > now:
                end_time = now
            trunc_interval = 'month'
            bucket_minutes = 43200  # ~30 days, not used for iteration

        # Convert to UTC for database query
        start_utc = start_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        end_utc = end_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

        # For 5-minute buckets, we need custom truncation
        if period == 'hourly':
            # Use a formula to bucket into 5-minute intervals
            # We'll query raw data and bucket it in Python for simplicity
            results = (
                db.session.query(
                    Usage.created_at,
                    Usage.tokens_input,
                    Usage.tokens_output,
                )
                .filter(
                    Usage.engineer_id == engineer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at <= end_utc,
                )
                .all()
            )
            cost_results = (
                db.session.query(
                    TelemetryEvent.created_at,
                    TelemetryEvent.cost_usd,
                )
                .filter(
                    TelemetryEvent.engineer_id == engineer_id,
                    TelemetryEvent.created_at >= start_utc,
                    TelemetryEvent.created_at <= end_utc,
                )
                .all()
            )

            # Bucket the data into hourly intervals
            data_by_bucket: dict[datetime, tuple[int, int, int]] = {}
            for r in results:
                # Convert to local time for bucketing
                local_time = r.created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                bucket_time = local_time.replace(
                    minute=0,
                    second=0,
                    microsecond=0
                )
                existing = data_by_bucket.get(bucket_time, (0, 0, 0))
                data_by_bucket[bucket_time] = (
                    existing[0] + r.tokens_input + r.tokens_output,
                    existing[1] + r.tokens_input,
                    existing[2] + r.tokens_output,
                )

            cost_by_bucket: dict[datetime, float] = {}
            for r in cost_results:
                local_time = r.created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                bucket_time = local_time.replace(
                    minute=0,
                    second=0,
                    microsecond=0
                )
                cost_by_bucket[bucket_time] = cost_by_bucket.get(bucket_time, 0.0) + (r.cost_usd or 0.0)

            # Build complete list with zeros for missing buckets
            data_points = []
            current = start_time
            while current <= end_time:
                data = data_by_bucket.get(current, (0, 0, 0))
                cost = cost_by_bucket.get(current, 0.0)
                data_points.append(TimeSeriesDataPoint(
                    timestamp=current.isoformat(),
                    tokens=data[0],
                    tokens_input=data[1],
                    tokens_output=data[2],
                    cost_usd=cost,
                ))
                current += timedelta(hours=1)

        else:
            # Use database truncation for hourly/daily buckets
            results = (
                db.session.query(
                    func.date_trunc(trunc_interval, Usage.created_at).label('bucket'),
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                    func.sum(Usage.tokens_input).label('tokens_input'),
                    func.sum(Usage.tokens_output).label('tokens_output'),
                )
                .filter(
                    Usage.engineer_id == engineer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at <= end_utc,
                )
                .group_by(func.date_trunc(trunc_interval, Usage.created_at))
                .order_by(func.date_trunc(trunc_interval, Usage.created_at))
                .all()
            )

            cost_results = (
                db.session.query(
                    func.date_trunc(trunc_interval, TelemetryEvent.created_at).label('bucket'),
                    func.sum(TelemetryEvent.cost_usd).label('cost_usd'),
                )
                .filter(
                    TelemetryEvent.engineer_id == engineer_id,
                    TelemetryEvent.created_at >= start_utc,
                    TelemetryEvent.created_at <= end_utc,
                )
                .group_by(func.date_trunc(trunc_interval, TelemetryEvent.created_at))
                .all()
            )

            # Build dicts keyed by UTC bucket time
            data_by_bucket = {}
            for r in results:
                data_by_bucket[r.bucket] = (r.tokens or 0, r.tokens_input or 0, r.tokens_output or 0)

            cost_by_bucket = {r.bucket: r.cost_usd or 0.0 for r in cost_results}

            # Build complete list with zeros for missing buckets
            data_points = []
            current = start_time

            while current < end_time:
                current_utc = current.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
                data = data_by_bucket.get(current_utc, (0, 0, 0))
                cost = cost_by_bucket.get(current_utc, 0.0)
                data_points.append(TimeSeriesDataPoint(
                    timestamp=current.isoformat(),
                    tokens=data[0],
                    tokens_input=data[1],
                    tokens_output=data[2],
                    cost_usd=cost,
                ))

                # Advance to next bucket based on period
                if period == 'daily':
                    current += timedelta(days=1)
                elif period == 'weekly':
                    current += timedelta(weeks=1)
                elif period == 'monthly':
                    # Move to next month
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)
                else:
                    current += timedelta(minutes=bucket_minutes)

        return TimeSeriesResponse(engineer_id=engineer_id, period=period, data=data_points)

    @staticmethod
    def get_team_time_series(
        customer_id: str,
        period: str = 'hourly',
        as_of: date | None = None,
    ) -> TeamTimeSeriesResponse:
        """
        Get time series data for all engineers in a team.

        Periods and their granularity:
        - hourly: 24 hours for selected day, hourly buckets
        - daily: last 30 days, daily buckets
        - weekly: last 12 weeks, weekly buckets
        - monthly: last 12 months, monthly buckets
        """
        now = datetime.now(APP_TIMEZONE)
        as_of_date = as_of or get_today()

        # Get all engineers for this customer
        all_engineers = (
            db.session.query(Engineer.id, Engineer.display_name)
            .filter(Engineer.customer_id == customer_id)
            .all()
        )
        engineer_names = {e.id: e.display_name for e in all_engineers}

        if period == 'hourly':
            # 24 hours for the selected day with hourly granularity
            start_time = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=APP_TIMEZONE)
            end_of_day = start_time + timedelta(days=1)
            # If viewing today, only go up to now; otherwise show full day
            end_time = min(end_of_day, now)
        elif period == 'daily':
            # Last 30 days with daily granularity
            end_date = as_of_date
            start_date = end_date - timedelta(days=29)
            start_time = datetime(start_date.year, start_date.month, start_date.day, tzinfo=APP_TIMEZONE)
            end_time = datetime(end_date.year, end_date.month, end_date.day, tzinfo=APP_TIMEZONE) + timedelta(days=1)
            if end_time > now:
                end_time = now
        elif period == 'weekly':
            # Last 12 weeks with weekly granularity
            days_since_monday = as_of_date.weekday()
            current_week_start = as_of_date - timedelta(days=days_since_monday)
            start_date = current_week_start - timedelta(weeks=11)
            start_time = datetime(start_date.year, start_date.month, start_date.day, tzinfo=APP_TIMEZONE)
            end_time = datetime(current_week_start.year, current_week_start.month, current_week_start.day, tzinfo=APP_TIMEZONE) + timedelta(days=7)
            if end_time > now:
                end_time = now
        else:  # monthly
            # Last 12 months with monthly granularity
            current_month_start = as_of_date.replace(day=1)
            year = current_month_start.year
            month = current_month_start.month - 11
            while month <= 0:
                month += 12
                year -= 1
            start_date = date(year, month, 1)
            start_time = datetime(start_date.year, start_date.month, start_date.day, tzinfo=APP_TIMEZONE)
            if current_month_start.month == 12:
                next_month = date(current_month_start.year + 1, 1, 1)
            else:
                next_month = date(current_month_start.year, current_month_start.month + 1, 1)
            end_time = datetime(next_month.year, next_month.month, next_month.day, tzinfo=APP_TIMEZONE)
            if end_time > now:
                end_time = now

        # Convert to UTC for database query
        start_utc = start_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        end_utc = end_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

        # Data structure: bucket_time -> engineer_id -> (tokens, tokens_input, tokens_output, cost_usd)
        data_by_bucket: dict[datetime, dict[str, tuple[int, int, int, float]]] = {}
        engineers_with_data: set[str] = set()

        if period == 'hourly':
            # Query raw data and bucket in Python for 5-minute intervals
            results = (
                db.session.query(
                    Usage.engineer_id,
                    Usage.created_at,
                    Usage.tokens_input,
                    Usage.tokens_output,
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at <= end_utc,
                )
                .all()
            )
            cost_results = (
                db.session.query(
                    TelemetryEvent.engineer_id,
                    TelemetryEvent.created_at,
                    TelemetryEvent.cost_usd,
                )
                .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    TelemetryEvent.created_at >= start_utc,
                    TelemetryEvent.created_at <= end_utc,
                )
                .all()
            )

            for r in results:
                local_time = r.created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                bucket_time = local_time.replace(
                    minute=0,
                    second=0,
                    microsecond=0
                )
                if bucket_time not in data_by_bucket:
                    data_by_bucket[bucket_time] = {}
                existing = data_by_bucket[bucket_time].get(r.engineer_id, (0, 0, 0, 0.0))
                data_by_bucket[bucket_time][r.engineer_id] = (
                    existing[0] + r.tokens_input + r.tokens_output,
                    existing[1] + r.tokens_input,
                    existing[2] + r.tokens_output,
                    existing[3],
                )
                engineers_with_data.add(r.engineer_id)

            for r in cost_results:
                local_time = r.created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                bucket_time = local_time.replace(
                    minute=0,
                    second=0,
                    microsecond=0
                )
                if bucket_time not in data_by_bucket:
                    data_by_bucket[bucket_time] = {}
                existing = data_by_bucket[bucket_time].get(r.engineer_id, (0, 0, 0, 0.0))
                data_by_bucket[bucket_time][r.engineer_id] = (
                    existing[0],
                    existing[1],
                    existing[2],
                    existing[3] + (r.cost_usd or 0.0),
                )

            # Build complete list with zeros for missing buckets
            data_points = []
            current = start_time
            while current <= end_time:
                bucket_data = data_by_bucket.get(current, {})
                engineers_list = [
                    EngineerTimeSeriesData(
                        engineer_id=eng_id,
                        tokens=data[0],
                        tokens_input=data[1],
                        tokens_output=data[2],
                        cost_usd=data[3],
                    )
                    for eng_id, data in bucket_data.items()
                ]
                data_points.append(TeamTimeSeriesBucket(
                    timestamp=current.isoformat(),
                    engineers=engineers_list,
                ))
                current += timedelta(hours=1)

        else:
            # Use database truncation for daily/weekly/monthly
            trunc_interval = 'day' if period == 'daily' else 'week' if period == 'weekly' else 'month'

            results = (
                db.session.query(
                    Usage.engineer_id,
                    func.date_trunc(trunc_interval, Usage.created_at).label('bucket'),
                    func.sum(Usage.tokens_input + Usage.tokens_output).label('tokens'),
                    func.sum(Usage.tokens_input).label('tokens_input'),
                    func.sum(Usage.tokens_output).label('tokens_output'),
                )
                .join(Engineer, Usage.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    Usage.created_at >= start_utc,
                    Usage.created_at <= end_utc,
                )
                .group_by(Usage.engineer_id, func.date_trunc(trunc_interval, Usage.created_at))
                .all()
            )

            cost_results = (
                db.session.query(
                    TelemetryEvent.engineer_id,
                    func.date_trunc(trunc_interval, TelemetryEvent.created_at).label('bucket'),
                    func.sum(TelemetryEvent.cost_usd).label('cost_usd'),
                )
                .join(Engineer, TelemetryEvent.engineer_id == Engineer.id)
                .filter(
                    Engineer.customer_id == customer_id,
                    TelemetryEvent.created_at >= start_utc,
                    TelemetryEvent.created_at <= end_utc,
                )
                .group_by(TelemetryEvent.engineer_id, func.date_trunc(trunc_interval, TelemetryEvent.created_at))
                .all()
            )

            # Build data structure keyed by UTC bucket time
            for r in results:
                if r.bucket not in data_by_bucket:
                    data_by_bucket[r.bucket] = {}
                data_by_bucket[r.bucket][r.engineer_id] = (
                    r.tokens or 0,
                    r.tokens_input or 0,
                    r.tokens_output or 0,
                    0.0,
                )
                engineers_with_data.add(r.engineer_id)

            for r in cost_results:
                if r.bucket not in data_by_bucket:
                    data_by_bucket[r.bucket] = {}
                existing = data_by_bucket[r.bucket].get(r.engineer_id, (0, 0, 0, 0.0))
                data_by_bucket[r.bucket][r.engineer_id] = (
                    existing[0],
                    existing[1],
                    existing[2],
                    r.cost_usd or 0.0,
                )

            # Build complete list
            data_points = []
            current = start_time

            while current < end_time:
                current_utc = current.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
                bucket_data = data_by_bucket.get(current_utc, {})
                engineers_list = [
                    EngineerTimeSeriesData(
                        engineer_id=eng_id,
                        tokens=data[0],
                        tokens_input=data[1],
                        tokens_output=data[2],
                        cost_usd=data[3],
                    )
                    for eng_id, data in bucket_data.items()
                ]
                data_points.append(TeamTimeSeriesBucket(
                    timestamp=current.isoformat(),
                    engineers=engineers_list,
                ))

                # Advance to next bucket
                if period == 'daily':
                    current += timedelta(days=1)
                elif period == 'weekly':
                    current += timedelta(weeks=1)
                elif period == 'monthly':
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)

        # Build engineer list (only engineers who have data)
        engineers = [
            EngineerInfo(id=eng_id, display_name=engineer_names.get(eng_id, 'Unknown'))
            for eng_id in sorted(engineers_with_data)
            if eng_id in engineer_names
        ]

        return TeamTimeSeriesResponse(
            period=period,
            engineers=engineers,
            data=data_points,
        )
