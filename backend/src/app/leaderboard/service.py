from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func

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


from src.app.github.models import GitHubDaily
from src.app.leaderboard.domains import (
    CrownHolder,
    DailyTotal,
    DailyTotalsByEngineerResponse,
    DailyTotalsResponse,
    DayWithEngineers,
    EngineerCrown,
    EngineerDailyTotal,
    EngineerInfo,
    EngineerMedalEntry,
    EngineerMedalsResponse,
    EngineerStatsResponse,
    EngineerTimeSeriesData,
    HistoricalRank,
    HistoricalRankingsResponse,
    Leaderboard,
    LeaderboardEntry,
    MedalAwarded,
    MilestoneAwarded,
    PeriodStats,
    PostResponse,
    RecapPodiumEntry,
    RecapRecord,
    TeamTimeSeriesBucket,
    TeamTimeSeriesResponse,
    TimeSeriesDataPoint,
    TimeSeriesResponse,
    UsageStats,
    WeeklyRecapResponse,
)
from src.app.usage.models import TelemetryEvent, Usage, UsageDaily
from src.network.database import db

ACTIVE_MINUTES_GAP_SECONDS = 600  # 10 minutes


class LeaderboardService:
    @staticmethod
    def _calculate_active_minutes(engineer_id: str, start_utc: datetime, end_utc: datetime) -> int:
        """Calculate active minutes from TelemetryEvent gaps for a single engineer."""
        timestamps = [
            r[0]
            for r in db.session.query(TelemetryEvent.created_at)
            .filter(
                TelemetryEvent.engineer_id == engineer_id,
                TelemetryEvent.created_at >= start_utc,
                TelemetryEvent.created_at < end_utc,
            )
            .order_by(TelemetryEvent.created_at)
            .all()
        ]

        if len(timestamps) < 2:
            return 0

        total_seconds = 0.0
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
            if gap <= ACTIVE_MINUTES_GAP_SECONDS:
                total_seconds += gap

        return int(total_seconds / 60)

    @staticmethod
    def _calculate_active_minutes_batch(
        engineer_ids: list[str], start_utc: datetime, end_utc: datetime
    ) -> dict[str, int]:
        """Calculate active minutes for multiple engineers in one query."""
        if not engineer_ids:
            return {}

        results = (
            db.session.query(TelemetryEvent.engineer_id, TelemetryEvent.created_at)
            .filter(
                TelemetryEvent.engineer_id.in_(engineer_ids),
                TelemetryEvent.created_at >= start_utc,
                TelemetryEvent.created_at < end_utc,
            )
            .order_by(TelemetryEvent.engineer_id, TelemetryEvent.created_at)
            .all()
        )

        active_by_engineer: dict[str, int] = {}
        current_eng = None
        prev_ts = None
        total_seconds = 0.0

        for row in results:
            if row.engineer_id != current_eng:
                if current_eng is not None:
                    active_by_engineer[current_eng] = int(total_seconds / 60)
                current_eng = row.engineer_id
                prev_ts = row.created_at
                total_seconds = 0.0
                continue

            gap = (row.created_at - prev_ts).total_seconds()
            if gap <= ACTIVE_MINUTES_GAP_SECONDS:
                total_seconds += gap
            prev_ts = row.created_at

        if current_eng is not None:
            active_by_engineer[current_eng] = int(total_seconds / 60)

        return active_by_engineer

    @staticmethod
    def _calculate_active_minutes_by_day(engineer_id: str, start_utc: datetime, end_utc: datetime) -> dict[date, int]:
        """Calculate active minutes per day for an engineer. Days are in PST/PDT."""
        timestamps = (
            db.session.query(TelemetryEvent.created_at)
            .filter(
                TelemetryEvent.engineer_id == engineer_id,
                TelemetryEvent.created_at >= start_utc,
                TelemetryEvent.created_at < end_utc,
            )
            .order_by(TelemetryEvent.created_at)
            .all()
        )

        if not timestamps:
            return {}

        # Group timestamps by PST/PDT day
        from collections import defaultdict

        by_day: dict[date, list[datetime]] = defaultdict(list)
        for (ts,) in timestamps:
            local_time = ts.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
            by_day[local_time.date()].append(ts)

        result: dict[date, int] = {}
        for day, day_timestamps in by_day.items():
            total_seconds = 0.0
            for i in range(1, len(day_timestamps)):
                gap = (day_timestamps[i] - day_timestamps[i - 1]).total_seconds()
                if gap <= ACTIVE_MINUTES_GAP_SECONDS:
                    total_seconds += gap
            result[day] = int(total_seconds / 60)

        return result

    @staticmethod
    def _calculate_active_minutes_by_day_batch(
        engineer_ids: list[str], start_utc: datetime, end_utc: datetime
    ) -> dict[date, dict[str, int]]:
        """Calculate active minutes per day per engineer. Returns {date: {engineer_id: minutes}}."""
        if not engineer_ids:
            return {}

        results = (
            db.session.query(TelemetryEvent.engineer_id, TelemetryEvent.created_at)
            .filter(
                TelemetryEvent.engineer_id.in_(engineer_ids),
                TelemetryEvent.created_at >= start_utc,
                TelemetryEvent.created_at < end_utc,
            )
            .order_by(TelemetryEvent.engineer_id, TelemetryEvent.created_at)
            .all()
        )

        from collections import defaultdict

        # Group by (engineer_id, date)
        by_eng_day: dict[str, dict[date, list[datetime]]] = defaultdict(lambda: defaultdict(list))
        for row in results:
            local_time = row.created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
            by_eng_day[row.engineer_id][local_time.date()].append(row.created_at)

        result: dict[date, dict[str, int]] = defaultdict(dict)
        for eng_id, days in by_eng_day.items():
            for day, timestamps in days.items():
                total_seconds = 0.0
                for i in range(1, len(timestamps)):
                    gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
                    if gap <= ACTIVE_MINUTES_GAP_SECONDS:
                        total_seconds += gap
                result[day][eng_id] = int(total_seconds / 60)

        return dict(result)

    @staticmethod
    def _get_active_minutes_for_range(customer_id: str, start_date: date, end_date: date) -> int:
        """Get total active minutes for all engineers in a date range."""
        start_utc, _ = get_day_bounds_utc(start_date)
        _, end_utc = get_day_bounds_utc(end_date)
        engineer_ids = [e.id for e in db.session.query(Engineer.id).filter(Engineer.customer_id == customer_id).all()]
        active_by_eng = LeaderboardService._calculate_active_minutes_batch(engineer_ids, start_utc, end_utc)
        return sum(active_by_eng.values())

    @staticmethod
    def _get_active_minutes_at_this_point(customer_id: str, for_date: date) -> int:
        """Get active minutes up to the current time of day (for comparisons)."""
        now_utc = datetime.utcnow()
        start_utc, _ = get_day_bounds_utc(for_date)
        today_start_utc, _ = get_day_bounds_utc(get_today())
        time_elapsed = now_utc - today_start_utc
        end_utc = start_utc + time_elapsed
        engineer_ids = [e.id for e in db.session.query(Engineer.id).filter(Engineer.customer_id == customer_id).all()]
        active_by_eng = LeaderboardService._calculate_active_minutes_batch(engineer_ids, start_utc, end_utc)
        return sum(active_by_eng.values())

    @staticmethod
    def _get_engineer_active_minutes_for_range(engineer_id: str, start_date: date, end_date: date) -> int:
        """Get active minutes for a single engineer in a date range."""
        start_utc, _ = get_day_bounds_utc(start_date)
        _, end_utc = get_day_bounds_utc(end_date)
        return LeaderboardService._calculate_active_minutes(engineer_id, start_utc, end_utc)

    @staticmethod
    def _get_engineer_active_minutes_at_this_point(engineer_id: str, for_date: date) -> int:
        """Get active minutes for a single engineer up to current time of day."""
        now_utc = datetime.utcnow()
        start_utc, _ = get_day_bounds_utc(for_date)
        today_start_utc, _ = get_day_bounds_utc(get_today())
        time_elapsed = now_utc - today_start_utc
        end_utc = start_utc + time_elapsed
        return LeaderboardService._calculate_active_minutes(engineer_id, start_utc, end_utc)

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

        # Get GitHub stats for the period
        github_results = (
            db.session.query(
                GitHubDaily.engineer_id,
                func.sum(GitHubDaily.commits_count).label('commits'),
                func.sum(GitHubDaily.lines_added).label('additions'),
                func.sum(GitHubDaily.lines_removed).label('deletions'),
                func.sum(GitHubDaily.prs_merged).label('prs_merged'),
            )
            .join(Engineer, GitHubDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                GitHubDaily.date >= start_date,
                GitHubDaily.date <= end_date,
            )
            .group_by(GitHubDaily.engineer_id)
            .all()
        )
        github_by_engineer = {
            r.engineer_id: {
                'commits': r.commits,
                'additions': r.additions,
                'deletions': r.deletions,
                'prs_merged': r.prs_merged,
            }
            for r in github_results
        }

        # Active minutes for each engineer
        start_utc, _ = get_day_bounds_utc(start_date)
        _, end_utc = get_day_bounds_utc(end_date)
        active_engineer_ids = [r.engineer_id for r in current_results]
        active_by_engineer = LeaderboardService._calculate_active_minutes_batch(active_engineer_ids, start_utc, end_utc)

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
            github_data = github_by_engineer.get(row.engineer_id)
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
                    github_commits=github_data['commits'] if github_data else None,
                    github_additions=github_data['additions'] if github_data else None,
                    github_deletions=github_data['deletions'] if github_data else None,
                    github_prs_merged=github_data['prs_merged'] if github_data else None,
                    active_minutes=active_by_engineer.get(row.engineer_id, 0),
                )
            )

        return entries

    @staticmethod
    def _get_live_daily_leaderboard(customer_id: str, as_of: date) -> list[LeaderboardEntry]:
        """
        Get daily leaderboard combining rolled-up UsageDaily with unrolled Usage data.

        This ensures we don't miss any data whether it's been rolled up or not.
        """
        # Get PST day bounds in UTC for database comparison
        start_utc, end_utc = get_day_bounds_utc(as_of)

        # Store totals as dict of engineer_id -> (display_name, tokens, tokens_input, tokens_output, cost_usd)
        totals_by_engineer: dict[str, tuple[str, int, int, int, float]] = {}

        # 1. Get rolled-up data from UsageDaily for this date
        daily_results = (
            db.session.query(
                UsageDaily.engineer_id,
                Engineer.display_name,
                UsageDaily.total_tokens,
                UsageDaily.tokens_input,
                UsageDaily.tokens_output,
                UsageDaily.cost_usd,
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date == as_of,
            )
            .all()
        )
        for r in daily_results:
            totals_by_engineer[r.engineer_id] = (
                r.display_name,
                r.total_tokens or 0,
                r.tokens_input or 0,
                r.tokens_output or 0,
                r.cost_usd or 0.0,
            )

        # 2. Get UNROLLED data from Usage (rolled_up_at IS NULL) for this date
        unrolled_results = (
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
                Usage.rolled_up_at.is_(None),  # Only unrolled records
            )
            .group_by(Usage.engineer_id, Engineer.display_name)
            .having(func.sum(Usage.tokens_input + Usage.tokens_output) > 0)
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

        # Add unrolled data to totals
        for r in unrolled_results:
            existing = totals_by_engineer.get(r.engineer_id)
            unrolled_cost = cost_by_engineer.get(r.engineer_id, 0.0)
            if existing:
                totals_by_engineer[r.engineer_id] = (
                    existing[0],  # display_name
                    existing[1] + (r.tokens or 0),
                    existing[2] + (r.tokens_input or 0),
                    existing[3] + (r.tokens_output or 0),
                    existing[4] + unrolled_cost,
                )
            else:
                totals_by_engineer[r.engineer_id] = (
                    r.display_name,
                    r.tokens or 0,
                    r.tokens_input or 0,
                    r.tokens_output or 0,
                    unrolled_cost,
                )

        # Sort by total tokens descending
        sorted_engineers = sorted(
            totals_by_engineer.items(),
            key=lambda x: x[1][1],  # Sort by tokens (index 1)
            reverse=True,
        )

        # Get GitHub stats for today from GitHubDaily
        github_results = (
            db.session.query(
                GitHubDaily.engineer_id,
                GitHubDaily.commits_count,
                GitHubDaily.lines_added,
                GitHubDaily.lines_removed,
                GitHubDaily.prs_merged,
            )
            .join(Engineer, GitHubDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                GitHubDaily.date == as_of,
            )
            .all()
        )
        github_by_engineer = {
            r.engineer_id: {
                'commits': r.commits_count,
                'additions': r.lines_added,
                'deletions': r.lines_removed,
                'prs_merged': r.prs_merged,
            }
            for r in github_results
        }

        # Active minutes for today
        active_by_engineer = LeaderboardService._calculate_active_minutes_batch(
            list(totals_by_engineer.keys()), start_utc, end_utc
        )

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
        for rank, (engineer_id, data) in enumerate(sorted_engineers, 1):
            display_name, tokens, tokens_input, tokens_output, cost_usd = data
            github_data = github_by_engineer.get(engineer_id)
            entries.append(
                LeaderboardEntry(
                    engineer_id=engineer_id,
                    display_name=display_name,
                    tokens=tokens,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=cost_usd,
                    rank=rank,
                    prev_rank=prev_rankings.get(engineer_id),
                    github_commits=github_data['commits'] if github_data else None,
                    github_additions=github_data['additions'] if github_data else None,
                    github_deletions=github_data['deletions'] if github_data else None,
                    github_prs_merged=github_data['prs_merged'] if github_data else None,
                    active_minutes=active_by_engineer.get(engineer_id, 0),
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
        """
        Get ranked entries combining rolled-up UsageDaily with unrolled Usage data.

        This ensures metrics include both:
        - Historical data that has been rolled up into UsageDaily
        - Any unrolled Usage records (rolled_up_at IS NULL) within the date range
        """
        # Get date bounds in UTC
        start_utc, _ = get_day_bounds_utc(start_date)
        _, end_utc = get_day_bounds_utc(end_date)

        # Store totals as dict of engineer_id -> (tokens, tokens_input, tokens_output, cost_usd)
        totals_by_engineer: dict[str, tuple[int, int, int, float]] = {}

        # 1. Get rolled-up data from UsageDaily for the date range
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
                UsageDaily.date <= end_date,
            )
            .group_by(UsageDaily.engineer_id)
            .all()
        )
        for r in daily_results:
            totals_by_engineer[r.engineer_id] = (
                r.tokens or 0,
                r.tokens_input or 0,
                r.tokens_output or 0,
                r.cost_usd or 0.0,
            )

        # 2. Get UNROLLED data from Usage (rolled_up_at IS NULL) for the date range
        unrolled_results = (
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
                Usage.rolled_up_at.is_(None),  # Only unrolled records
            )
            .group_by(Usage.engineer_id)
            .all()
        )

        # Get cost from TelemetryEvent for unrolled period
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
        unrolled_cost_by_engineer = {r.engineer_id: r.cost_usd or 0.0 for r in cost_results}

        # Add unrolled data to totals
        for r in unrolled_results:
            existing = totals_by_engineer.get(r.engineer_id, (0, 0, 0, 0.0))
            unrolled_cost = unrolled_cost_by_engineer.get(r.engineer_id, 0.0)
            totals_by_engineer[r.engineer_id] = (
                existing[0] + (r.tokens or 0),
                existing[1] + (r.tokens_input or 0),
                existing[2] + (r.tokens_output or 0),
                existing[3] + unrolled_cost,
            )

        # Get GitHub stats for the period
        github_results = (
            db.session.query(
                GitHubDaily.engineer_id,
                func.sum(GitHubDaily.commits_count).label('commits'),
                func.sum(GitHubDaily.lines_added).label('additions'),
                func.sum(GitHubDaily.lines_removed).label('deletions'),
                func.sum(GitHubDaily.prs_merged).label('prs_merged'),
            )
            .join(Engineer, GitHubDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                GitHubDaily.date >= start_date,
                GitHubDaily.date <= end_date,
            )
            .group_by(GitHubDaily.engineer_id)
            .all()
        )
        github_by_engineer = {
            r.engineer_id: {
                'commits': r.commits,
                'additions': r.additions,
                'deletions': r.deletions,
                'prs_merged': r.prs_merged,
            }
            for r in github_results
        }

        # Active minutes
        active_by_engineer = LeaderboardService._calculate_active_minutes_batch(
            list(totals_by_engineer.keys()), start_utc, end_utc
        )

        # Get engineer names
        engineer_names = {
            e.id: e.display_name for e in db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()
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
            github_data = github_by_engineer.get(eng_id)
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
                    github_commits=github_data['commits'] if github_data else None,
                    github_additions=github_data['additions'] if github_data else None,
                    github_deletions=github_data['deletions'] if github_data else None,
                    github_prs_merged=github_data['prs_merged'] if github_data else None,
                    active_minutes=active_by_engineer.get(eng_id, 0),
                )
            )

        return entries

    @staticmethod
    def _get_github_stats_for_range(customer_id: str, start_date: date, end_date: date) -> tuple[int, int, int, int]:
        """Get GitHub stats (commits, additions, deletions, prs_merged) for a date range."""
        result = (
            db.session.query(
                func.coalesce(func.sum(GitHubDaily.commits_count), 0),
                func.coalesce(func.sum(GitHubDaily.lines_added), 0),
                func.coalesce(func.sum(GitHubDaily.lines_removed), 0),
                func.coalesce(func.sum(GitHubDaily.prs_merged), 0),
            )
            .join(Engineer, GitHubDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                GitHubDaily.date >= start_date,
                GitHubDaily.date <= end_date,
            )
            .one()
        )
        return (result[0] or 0, result[1] or 0, result[2] or 0, result[3] or 0)

    @staticmethod
    def get_usage_stats(customer_id: str, as_of: date | None = None) -> UsageStats:
        """Get usage stats comparing current period to same point in previous period."""
        as_of = as_of or get_today()

        # Today (live) vs yesterday at this point
        today_tokens = LeaderboardService._get_live_tokens_for_date_detailed(customer_id, as_of)
        yesterday_tokens = LeaderboardService._get_tokens_at_this_point_detailed(customer_id, as_of - timedelta(days=1))

        # GitHub stats for today vs yesterday
        today_github = LeaderboardService._get_github_stats_for_range(customer_id, as_of, as_of)
        yesterday_github = LeaderboardService._get_github_stats_for_range(
            customer_id, as_of - timedelta(days=1), as_of - timedelta(days=1)
        )

        # This week vs last week at this point
        # e.g., Mon-Wed this week vs Mon-Wed last week
        week_start = as_of - timedelta(days=as_of.weekday())
        day_of_week = as_of.weekday()  # 0=Mon, 6=Sun
        last_week_start = week_start - timedelta(days=7)
        last_week_same_day = last_week_start + timedelta(days=day_of_week)

        this_week_tokens = LeaderboardService._get_tokens_for_range_full_detailed(customer_id, week_start, as_of)
        last_week_tokens = LeaderboardService._get_tokens_for_range_full_detailed(
            customer_id, last_week_start, last_week_same_day
        )
        this_week_github = LeaderboardService._get_github_stats_for_range(customer_id, week_start, as_of)
        last_week_github = LeaderboardService._get_github_stats_for_range(
            customer_id, last_week_start, last_week_same_day
        )

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
        last_month_tokens = LeaderboardService._get_tokens_for_range_full_detailed(
            customer_id, last_month_start, last_month_comparison_end
        )
        this_month_github = LeaderboardService._get_github_stats_for_range(customer_id, month_start, as_of)
        last_month_github = LeaderboardService._get_github_stats_for_range(
            customer_id, last_month_start, last_month_comparison_end
        )

        # Active minutes
        today_active = LeaderboardService._get_active_minutes_for_range(customer_id, as_of, as_of)
        yesterday_active = LeaderboardService._get_active_minutes_at_this_point(customer_id, as_of - timedelta(days=1))
        this_week_active = LeaderboardService._get_active_minutes_for_range(customer_id, week_start, as_of)
        last_week_active = LeaderboardService._get_active_minutes_for_range(
            customer_id, last_week_start, last_week_same_day
        )
        this_month_active = LeaderboardService._get_active_minutes_for_range(customer_id, month_start, as_of)
        last_month_active = LeaderboardService._get_active_minutes_for_range(
            customer_id, last_month_start, last_month_comparison_end
        )

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
                github_commits=today_github[0],
                github_additions=today_github[1],
                github_deletions=today_github[2],
                github_prs_merged=today_github[3],
                comparison_github_commits=yesterday_github[0],
                comparison_github_additions=yesterday_github[1],
                comparison_github_deletions=yesterday_github[2],
                comparison_github_prs_merged=yesterday_github[3],
                active_minutes=today_active,
                comparison_active_minutes=yesterday_active,
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
                github_commits=this_week_github[0],
                github_additions=this_week_github[1],
                github_deletions=this_week_github[2],
                github_prs_merged=this_week_github[3],
                comparison_github_commits=last_week_github[0],
                comparison_github_additions=last_week_github[1],
                comparison_github_deletions=last_week_github[2],
                comparison_github_prs_merged=last_week_github[3],
                active_minutes=this_week_active,
                comparison_active_minutes=last_week_active,
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
                github_commits=this_month_github[0],
                github_additions=this_month_github[1],
                github_deletions=this_month_github[2],
                github_prs_merged=this_month_github[3],
                comparison_github_commits=last_month_github[0],
                comparison_github_additions=last_month_github[1],
                comparison_github_deletions=last_month_github[2],
                comparison_github_prs_merged=last_month_github[3],
                active_minutes=this_month_active,
                comparison_active_minutes=last_month_active,
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
        """Get token breakdown (total, input, output, cost) for a date.

        Combines rolled-up UsageDaily data with unrolled Usage records to ensure
        no data is missed regardless of rollup state.
        """
        start_utc, end_utc = get_day_bounds_utc(for_date)

        # 1. Get rolled-up token data from UsageDaily
        daily_result = (
            db.session.query(
                func.coalesce(func.sum(UsageDaily.total_tokens), 0),
                func.coalesce(func.sum(UsageDaily.tokens_input), 0),
                func.coalesce(func.sum(UsageDaily.tokens_output), 0),
            )
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(
                Engineer.customer_id == customer_id,
                UsageDaily.date == for_date,
            )
            .one()
        )

        # 2. Get unrolled token data from Usage (rolled_up_at IS NULL)
        unrolled_result = (
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
                Usage.rolled_up_at.is_(None),
            )
            .one()
        )

        # 3. Get cost from TelemetryEvent for the full date range
        # (TelemetryEvents are never marked as rolled up, so always query the full range)
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

        total = (daily_result[0] or 0) + (unrolled_result[0] or 0)
        total_input = (daily_result[1] or 0) + (unrolled_result[1] or 0)
        total_output = (daily_result[2] or 0) + (unrolled_result[2] or 0)

        return (total, total_input, total_output, cost_result or 0.0)

    @staticmethod
    def _get_tokens_at_this_point_detailed(customer_id: str, for_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown for a date up to the current time of day (for 'at this point' comparisons)."""
        now_utc = datetime.utcnow()
        start_utc, _ = get_day_bounds_utc(for_date)

        # Calculate the end time as: start of that day + time elapsed since start of today
        today_start_utc, _ = get_day_bounds_utc(get_today())
        time_elapsed = now_utc - today_start_utc
        end_utc = start_utc + time_elapsed

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
    def _get_tokens_for_range_full_detailed(
        customer_id: str, start_date: date, end_date: date
    ) -> tuple[int, int, int, float]:
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
            live_total, live_input, live_output, live_cost = LeaderboardService._get_live_tokens_for_date_detailed(
                customer_id, today
            )

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

        # Active minutes by day
        full_start_utc, _ = get_day_bounds_utc(start_date)
        _, full_end_utc = get_day_bounds_utc(end_date)
        engineer_ids = [e.id for e in db.session.query(Engineer.id).filter(Engineer.customer_id == customer_id).all()]
        active_by_day_by_eng = LeaderboardService._calculate_active_minutes_by_day_batch(
            engineer_ids, full_start_utc, full_end_utc
        )
        active_by_day: dict[date, int] = {}
        for day, eng_data in active_by_day_by_eng.items():
            active_by_day[day] = sum(eng_data.values())

        # Build complete list with zeros for missing days
        totals = []
        current = start_date
        while current <= end_date:
            data = totals_by_date.get(current, (0, 0, 0, 0.0))
            totals.append(
                DailyTotal(
                    date=current,
                    tokens=data[0],
                    tokens_input=data[1],
                    tokens_output=data[2],
                    cost_usd=data[3],
                    active_minutes=active_by_day.get(current, 0),
                )
            )
            current += timedelta(days=1)

        return DailyTotalsResponse(start_date=start_date, end_date=end_date, totals=totals)

    @staticmethod
    def _get_engineer_github_stats_for_range(
        engineer_id: str, start_date: date, end_date: date
    ) -> tuple[int, int, int, int]:
        """Get GitHub stats (commits, additions, deletions, prs_merged) for an engineer in a date range."""
        result = (
            db.session.query(
                func.coalesce(func.sum(GitHubDaily.commits_count), 0),
                func.coalesce(func.sum(GitHubDaily.lines_added), 0),
                func.coalesce(func.sum(GitHubDaily.lines_removed), 0),
                func.coalesce(func.sum(GitHubDaily.prs_merged), 0),
            )
            .filter(
                GitHubDaily.engineer_id == engineer_id,
                GitHubDaily.date >= start_date,
                GitHubDaily.date <= end_date,
            )
            .one()
        )
        return (result[0] or 0, result[1] or 0, result[2] or 0, result[3] or 0)

    @staticmethod
    def get_engineer_stats(engineer_id: str, as_of: date | None = None) -> EngineerStatsResponse:
        """Get usage stats for a specific engineer comparing to same point in previous period."""
        as_of = as_of or get_today()

        engineer = Engineer.get(id=engineer_id)

        # Today (live) vs yesterday at this point
        today_tokens = LeaderboardService._get_engineer_live_tokens_detailed(engineer_id, as_of)
        yesterday_tokens = LeaderboardService._get_engineer_tokens_at_this_point_detailed(
            engineer_id, as_of - timedelta(days=1)
        )

        # GitHub stats for today vs yesterday
        today_github = LeaderboardService._get_engineer_github_stats_for_range(engineer_id, as_of, as_of)
        yesterday_github = LeaderboardService._get_engineer_github_stats_for_range(
            engineer_id, as_of - timedelta(days=1), as_of - timedelta(days=1)
        )

        # This week vs last week at this point
        week_start = as_of - timedelta(days=as_of.weekday())
        day_of_week = as_of.weekday()
        last_week_start = week_start - timedelta(days=7)
        last_week_same_day = last_week_start + timedelta(days=day_of_week)

        this_week_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(
            engineer_id, week_start, as_of
        )
        last_week_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(
            engineer_id, last_week_start, last_week_same_day
        )
        this_week_github = LeaderboardService._get_engineer_github_stats_for_range(engineer_id, week_start, as_of)
        last_week_github = LeaderboardService._get_engineer_github_stats_for_range(
            engineer_id, last_week_start, last_week_same_day
        )

        # This month vs last month at this point
        month_start = as_of.replace(day=1)
        day_of_month = as_of.day
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        last_month_same_day = min(day_of_month, last_month_end.day)
        last_month_comparison_end = last_month_start.replace(day=last_month_same_day)

        this_month_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(
            engineer_id, month_start, as_of
        )
        last_month_tokens = LeaderboardService._get_engineer_tokens_for_range_full_detailed(
            engineer_id, last_month_start, last_month_comparison_end
        )
        this_month_github = LeaderboardService._get_engineer_github_stats_for_range(engineer_id, month_start, as_of)
        last_month_github = LeaderboardService._get_engineer_github_stats_for_range(
            engineer_id, last_month_start, last_month_comparison_end
        )

        # Active minutes
        today_active = LeaderboardService._get_engineer_active_minutes_for_range(engineer_id, as_of, as_of)
        yesterday_active = LeaderboardService._get_engineer_active_minutes_at_this_point(
            engineer_id, as_of - timedelta(days=1)
        )
        this_week_active = LeaderboardService._get_engineer_active_minutes_for_range(engineer_id, week_start, as_of)
        last_week_active = LeaderboardService._get_engineer_active_minutes_for_range(
            engineer_id, last_week_start, last_week_same_day
        )
        this_month_active = LeaderboardService._get_engineer_active_minutes_for_range(engineer_id, month_start, as_of)
        last_month_active = LeaderboardService._get_engineer_active_minutes_for_range(
            engineer_id, last_month_start, last_month_comparison_end
        )

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
                github_commits=today_github[0],
                github_additions=today_github[1],
                github_deletions=today_github[2],
                github_prs_merged=today_github[3],
                comparison_github_commits=yesterday_github[0],
                comparison_github_additions=yesterday_github[1],
                comparison_github_deletions=yesterday_github[2],
                comparison_github_prs_merged=yesterday_github[3],
                active_minutes=today_active,
                comparison_active_minutes=yesterday_active,
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
                github_commits=this_week_github[0],
                github_additions=this_week_github[1],
                github_deletions=this_week_github[2],
                github_prs_merged=this_week_github[3],
                comparison_github_commits=last_week_github[0],
                comparison_github_additions=last_week_github[1],
                comparison_github_deletions=last_week_github[2],
                comparison_github_prs_merged=last_week_github[3],
                active_minutes=this_week_active,
                comparison_active_minutes=last_week_active,
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
                github_commits=this_month_github[0],
                github_additions=this_month_github[1],
                github_deletions=this_month_github[2],
                github_prs_merged=this_month_github[3],
                comparison_github_commits=last_month_github[0],
                comparison_github_additions=last_month_github[1],
                comparison_github_deletions=last_month_github[2],
                comparison_github_prs_merged=last_month_github[3],
                active_minutes=this_month_active,
                comparison_active_minutes=last_month_active,
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
    def _get_engineer_tokens_at_this_point_detailed(engineer_id: str, for_date: date) -> tuple[int, int, int, float]:
        """Get token breakdown for an engineer up to the current time of day (for 'at this point' comparisons)."""
        now_utc = datetime.utcnow()
        start_utc, _ = get_day_bounds_utc(for_date)

        # Calculate the end time as: start of that day + time elapsed since start of today
        today_start_utc, _ = get_day_bounds_utc(get_today())
        time_elapsed = now_utc - today_start_utc
        end_utc = start_utc + time_elapsed

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
    def _get_engineer_tokens_for_range_full_detailed(
        engineer_id: str, start_date: date, end_date: date
    ) -> tuple[int, int, int, float]:
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
            live_total, live_input, live_output, live_cost = LeaderboardService._get_engineer_live_tokens_detailed(
                engineer_id, today
            )

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
    def get_engineer_daily_totals(
        engineer_id: str, start_date: date, end_date: date | None = None
    ) -> DailyTotalsResponse:
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

        # Active minutes by day
        full_start_utc, _ = get_day_bounds_utc(start_date)
        _, full_end_utc = get_day_bounds_utc(end_date)
        active_by_day = LeaderboardService._calculate_active_minutes_by_day(engineer_id, full_start_utc, full_end_utc)

        totals = []
        current = start_date
        while current <= end_date:
            data = totals_by_date.get(current, (0, 0, 0, 0.0))
            totals.append(
                DailyTotal(
                    date=current,
                    tokens=data[0],
                    tokens_input=data[1],
                    tokens_output=data[2],
                    cost_usd=data[3],
                    active_minutes=active_by_day.get(current, 0),
                )
            )
            current += timedelta(days=1)

        return DailyTotalsResponse(start_date=start_date, end_date=end_date, totals=totals)

    @staticmethod
    def get_historical_rankings(
        customer_id: str, engineer_id: str, period_type: str, num_periods: int = 20, as_of: date | None = None
    ) -> HistoricalRankingsResponse:
        """Get historical rankings for an engineer over past periods."""
        today = as_of if as_of is not None else get_today()
        rankings = []

        if period_type == 'daily':
            for i in range(num_periods):
                period_date = today - timedelta(days=i)
                rank, tokens, tokens_input, tokens_output, cost_usd = LeaderboardService._get_rank_for_day_detailed(
                    customer_id, engineer_id, period_date
                )
                active = LeaderboardService._get_engineer_active_minutes_for_range(
                    engineer_id, period_date, period_date
                )
                rankings.append(
                    HistoricalRank(
                        period_start=period_date,
                        period_end=period_date,
                        rank=rank,
                        tokens=tokens,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        cost_usd=cost_usd,
                        active_minutes=active,
                    )
                )

        elif period_type == 'weekly':
            # Start from current week
            current_week_start = today - timedelta(days=today.weekday())
            for i in range(num_periods):
                week_start = current_week_start - timedelta(weeks=i)
                week_end = week_start + timedelta(days=6)
                if week_end > today:
                    week_end = today
                rank, tokens, tokens_input, tokens_output, cost_usd = LeaderboardService._get_rank_for_range_detailed(
                    customer_id, engineer_id, week_start, week_end
                )
                active = LeaderboardService._get_engineer_active_minutes_for_range(engineer_id, week_start, week_end)
                rankings.append(
                    HistoricalRank(
                        period_start=week_start,
                        period_end=week_end,
                        rank=rank,
                        tokens=tokens,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        cost_usd=cost_usd,
                        active_minutes=active,
                    )
                )

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

                rank, tokens, tokens_input, tokens_output, cost_usd = LeaderboardService._get_rank_for_range_detailed(
                    customer_id, engineer_id, month_start, month_end
                )
                active = LeaderboardService._get_engineer_active_minutes_for_range(engineer_id, month_start, month_end)
                rankings.append(
                    HistoricalRank(
                        period_start=month_start,
                        period_end=month_end,
                        rank=rank,
                        tokens=tokens,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        cost_usd=cost_usd,
                        active_minutes=active,
                    )
                )

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
    def _get_rank_for_day_detailed(
        customer_id: str, engineer_id: str, for_date: date
    ) -> tuple[int | None, int, int, int, float]:
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

            if results:
                for rank, row in enumerate(results, 1):
                    if row.engineer_id == engineer_id:
                        return rank, row.tokens, row.tokens_input, row.tokens_output, row.cost_usd or 0.0
                return None, 0, 0, 0, 0.0

            # Fallback to raw Usage table if no rollup data exists
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

    @staticmethod
    def _get_rank_for_range(
        customer_id: str, engineer_id: str, start_date: date, end_date: date
    ) -> tuple[int | None, int]:
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
    def _get_rank_for_range_detailed(
        customer_id: str, engineer_id: str, start_date: date, end_date: date
    ) -> tuple[int | None, int, int, int, float]:
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

        if results:
            for rank, row in enumerate(results, 1):
                if row.engineer_id == engineer_id:
                    return rank, row.tokens, row.tokens_input, row.tokens_output, row.cost_usd or 0.0
            return None, 0, 0, 0, 0.0

        # Fallback to raw Usage table if no rollup data exists for the range
        start_utc, _ = get_day_bounds_utc(start_date)
        _, end_utc = get_day_bounds_utc(end_date)
        fallback_results = (
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

        for rank, row in enumerate(fallback_results, 1):
            if row.engineer_id == engineer_id:
                return rank, row.tokens, row.tokens_input, row.tokens_output, cost_by_engineer.get(engineer_id, 0.0)

        return None, 0, 0, 0, 0.0

    @staticmethod
    def get_daily_totals_by_engineer(
        customer_id: str, start_date: date, end_date: date
    ) -> DailyTotalsByEngineerResponse:
        """Get daily token totals broken down by engineer for charting."""
        today = get_today()

        # Get all engineers for this customer
        all_engineers = (
            db.session.query(Engineer.id, Engineer.display_name).filter(Engineer.customer_id == customer_id).all()
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
        - hourly: 24 hours for selected day, 10-minute buckets
        - daily: last 30 days, daily buckets
        - weekly: last 12 weeks, weekly buckets
        - monthly: last 12 months, monthly buckets
        """
        now = datetime.now(APP_TIMEZONE)
        as_of_date = as_of or get_today()

        if period == 'hourly':
            # 24 hours for the selected day with 10-minute granularity
            start_time = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=APP_TIMEZONE)
            end_of_day = start_time + timedelta(days=1)
            # If viewing today, only go up to now; otherwise show full day
            end_time = min(end_of_day, now)
            trunc_interval = 'minute'
            bucket_minutes = 10
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
            end_time = datetime(
                current_week_start.year, current_week_start.month, current_week_start.day, tzinfo=APP_TIMEZONE
            ) + timedelta(days=7)
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

            # Bucket the data into 10-minute intervals
            data_by_bucket: dict[datetime, tuple[int, int, int]] = {}
            for r in results:
                # Convert to local time for bucketing
                local_time = r.created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                bucket_time = local_time.replace(minute=(local_time.minute // 10) * 10, second=0, microsecond=0)
                existing = data_by_bucket.get(bucket_time, (0, 0, 0))
                data_by_bucket[bucket_time] = (
                    existing[0] + r.tokens_input + r.tokens_output,
                    existing[1] + r.tokens_input,
                    existing[2] + r.tokens_output,
                )

            cost_by_bucket: dict[datetime, float] = {}
            for r in cost_results:
                local_time = r.created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                bucket_time = local_time.replace(minute=(local_time.minute // 10) * 10, second=0, microsecond=0)
                cost_by_bucket[bucket_time] = cost_by_bucket.get(bucket_time, 0.0) + (r.cost_usd or 0.0)

            # Compute active minutes per 10-minute bucket from TelemetryEvent gaps
            active_minutes_by_bucket: dict[datetime, float] = {}
            telemetry_timestamps = sorted([r.created_at for r in cost_results])
            for i in range(1, len(telemetry_timestamps)):
                gap = (telemetry_timestamps[i] - telemetry_timestamps[i - 1]).total_seconds()
                if gap <= ACTIVE_MINUTES_GAP_SECONDS:
                    local_time = telemetry_timestamps[i].replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                    bucket_time = local_time.replace(minute=(local_time.minute // 10) * 10, second=0, microsecond=0)
                    active_minutes_by_bucket[bucket_time] = active_minutes_by_bucket.get(bucket_time, 0.0) + gap / 60

            # Build complete list with zeros for missing buckets
            data_points = []
            current = start_time
            while current <= end_time:
                data = data_by_bucket.get(current, (0, 0, 0))
                cost = cost_by_bucket.get(current, 0.0)
                data_points.append(
                    TimeSeriesDataPoint(
                        timestamp=current.isoformat(),
                        tokens=data[0],
                        tokens_input=data[1],
                        tokens_output=data[2],
                        cost_usd=cost,
                        active_minutes=min(10, round(active_minutes_by_bucket.get(current, 0.0))),
                    )
                )
                current += timedelta(minutes=10)

        else:
            # Use UsageDaily for daily/weekly/monthly views (rolled-up data)
            start_date_only = start_time.date()
            end_date_only = (end_time - timedelta(seconds=1)).date()  # end_time is exclusive

            data_by_bucket: dict[datetime, tuple[int, int, int]] = {}
            cost_by_bucket: dict[datetime, float] = {}

            if period == 'daily':
                # Query UsageDaily directly
                results = (
                    db.session.query(
                        UsageDaily.date,
                        UsageDaily.total_tokens.label('tokens'),
                        UsageDaily.tokens_input,
                        UsageDaily.tokens_output,
                        UsageDaily.cost_usd,
                    )
                    .filter(
                        UsageDaily.engineer_id == engineer_id,
                        UsageDaily.date >= start_date_only,
                        UsageDaily.date <= end_date_only,
                    )
                    .all()
                )

                for r in results:
                    bucket_time = datetime(r.date.year, r.date.month, r.date.day, tzinfo=APP_TIMEZONE)
                    data_by_bucket[bucket_time] = (r.tokens or 0, r.tokens_input or 0, r.tokens_output or 0)
                    cost_by_bucket[bucket_time] = r.cost_usd or 0.0

            else:
                # Weekly/monthly: aggregate UsageDaily records
                results = (
                    db.session.query(
                        func.date_trunc(trunc_interval, UsageDaily.date).label('bucket'),
                        func.sum(UsageDaily.total_tokens).label('tokens'),
                        func.sum(UsageDaily.tokens_input).label('tokens_input'),
                        func.sum(UsageDaily.tokens_output).label('tokens_output'),
                        func.sum(UsageDaily.cost_usd).label('cost_usd'),
                    )
                    .filter(
                        UsageDaily.engineer_id == engineer_id,
                        UsageDaily.date >= start_date_only,
                        UsageDaily.date <= end_date_only,
                    )
                    .group_by(func.date_trunc(trunc_interval, UsageDaily.date))
                    .order_by(func.date_trunc(trunc_interval, UsageDaily.date))
                    .all()
                )

                for r in results:
                    # Extract the date from the truncated timestamp and create midnight in APP_TIMEZONE
                    # date_trunc on a date column returns a naive timestamp, not UTC
                    if isinstance(r.bucket, datetime):
                        bucket_date = r.bucket.date()
                    else:
                        bucket_date = r.bucket
                    bucket_time = datetime(bucket_date.year, bucket_date.month, bucket_date.day, tzinfo=APP_TIMEZONE)
                    data_by_bucket[bucket_time] = (r.tokens or 0, r.tokens_input or 0, r.tokens_output or 0)
                    cost_by_bucket[bucket_time] = r.cost_usd or 0.0

            # Active minutes by day
            active_by_day = LeaderboardService._calculate_active_minutes_by_day(engineer_id, start_utc, end_utc)

            # Build complete list with zeros for missing buckets
            data_points = []
            current = start_time

            while current < end_time:
                data = data_by_bucket.get(current, (0, 0, 0))
                cost = cost_by_bucket.get(current, 0.0)

                # Compute active minutes for this bucket
                if period == 'daily':
                    bucket_active = active_by_day.get(current.date(), 0)
                else:
                    # Weekly/monthly: sum daily active minutes within the bucket range
                    if period == 'weekly':
                        bucket_end = current + timedelta(weeks=1)
                    else:
                        if current.month == 12:
                            bucket_end = current.replace(year=current.year + 1, month=1)
                        else:
                            bucket_end = current.replace(month=current.month + 1)
                    bucket_active = sum(
                        minutes for day, minutes in active_by_day.items() if current.date() <= day < bucket_end.date()
                    )

                data_points.append(
                    TimeSeriesDataPoint(
                        timestamp=current.isoformat(),
                        tokens=data[0],
                        tokens_input=data[1],
                        tokens_output=data[2],
                        cost_usd=cost,
                        active_minutes=bucket_active,
                    )
                )

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
        - hourly: 24 hours for selected day, 10-minute buckets
        - daily: last 30 days, daily buckets
        - weekly: last 12 weeks, weekly buckets
        - monthly: last 12 months, monthly buckets
        """
        now = datetime.now(APP_TIMEZONE)
        as_of_date = as_of or get_today()

        # Get all engineers for this customer
        all_engineers = (
            db.session.query(Engineer.id, Engineer.display_name).filter(Engineer.customer_id == customer_id).all()
        )
        engineer_names = {e.id: e.display_name for e in all_engineers}

        if period == 'hourly':
            # 24 hours for the selected day with 10-minute granularity
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
            end_time = datetime(
                current_week_start.year, current_week_start.month, current_week_start.day, tzinfo=APP_TIMEZONE
            ) + timedelta(days=7)
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
                bucket_time = local_time.replace(minute=(local_time.minute // 10) * 10, second=0, microsecond=0)
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
                bucket_time = local_time.replace(minute=(local_time.minute // 10) * 10, second=0, microsecond=0)
                if bucket_time not in data_by_bucket:
                    data_by_bucket[bucket_time] = {}
                existing = data_by_bucket[bucket_time].get(r.engineer_id, (0, 0, 0, 0.0))
                data_by_bucket[bucket_time][r.engineer_id] = (
                    existing[0],
                    existing[1],
                    existing[2],
                    existing[3] + (r.cost_usd or 0.0),
                )

            # Compute active minutes per 10-minute bucket per engineer from TelemetryEvent gaps
            telemetry_by_engineer: dict[str, list[datetime]] = defaultdict(list)
            for r in cost_results:
                telemetry_by_engineer[r.engineer_id].append(r.created_at)

            active_minutes_by_bucket_eng: dict[datetime, dict[str, float]] = defaultdict(lambda: defaultdict(float))
            for eng_id, timestamps in telemetry_by_engineer.items():
                timestamps.sort()
                for i in range(1, len(timestamps)):
                    gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
                    if gap <= ACTIVE_MINUTES_GAP_SECONDS:
                        local_time = timestamps[i].replace(tzinfo=ZoneInfo('UTC')).astimezone(APP_TIMEZONE)
                        bucket_time = local_time.replace(minute=(local_time.minute // 10) * 10, second=0, microsecond=0)
                        active_minutes_by_bucket_eng[bucket_time][eng_id] += gap / 60

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
                        active_minutes=min(10, round(active_minutes_by_bucket_eng.get(current, {}).get(eng_id, 0.0))),
                    )
                    for eng_id, data in bucket_data.items()
                ]
                data_points.append(
                    TeamTimeSeriesBucket(
                        timestamp=current.isoformat(),
                        engineers=engineers_list,
                    )
                )
                current += timedelta(minutes=10)

        else:
            # Use UsageDaily for daily/weekly/monthly views (rolled-up data)
            start_date_only = start_time.date()
            end_date_only = (end_time - timedelta(seconds=1)).date()  # end_time is exclusive

            from loguru import logger

            logger.info(
                f'Team time series query: period={period}, customer={customer_id}, start={start_date_only}, end={end_date_only}'
            )

            if period == 'daily':
                # Query UsageDaily directly - one record per engineer per day
                results = (
                    db.session.query(
                        UsageDaily.engineer_id,
                        UsageDaily.date,
                        UsageDaily.total_tokens.label('tokens'),
                        UsageDaily.tokens_input,
                        UsageDaily.tokens_output,
                        UsageDaily.cost_usd,
                    )
                    .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                    .filter(
                        Engineer.customer_id == customer_id,
                        UsageDaily.date >= start_date_only,
                        UsageDaily.date <= end_date_only,
                    )
                    .all()
                )

                logger.info(f'Daily query returned {len(results)} results')

                for r in results:
                    bucket_time = datetime(r.date.year, r.date.month, r.date.day, tzinfo=APP_TIMEZONE)
                    if bucket_time not in data_by_bucket:
                        data_by_bucket[bucket_time] = {}
                    data_by_bucket[bucket_time][r.engineer_id] = (
                        r.tokens or 0,
                        r.tokens_input or 0,
                        r.tokens_output or 0,
                        r.cost_usd or 0.0,
                    )
                    engineers_with_data.add(r.engineer_id)

            else:
                # Weekly/monthly: aggregate UsageDaily records
                trunc_interval = 'week' if period == 'weekly' else 'month'

                results = (
                    db.session.query(
                        UsageDaily.engineer_id,
                        func.date_trunc(trunc_interval, UsageDaily.date).label('bucket'),
                        func.sum(UsageDaily.total_tokens).label('tokens'),
                        func.sum(UsageDaily.tokens_input).label('tokens_input'),
                        func.sum(UsageDaily.tokens_output).label('tokens_output'),
                        func.sum(UsageDaily.cost_usd).label('cost_usd'),
                    )
                    .join(Engineer, UsageDaily.engineer_id == Engineer.id)
                    .filter(
                        Engineer.customer_id == customer_id,
                        UsageDaily.date >= start_date_only,
                        UsageDaily.date <= end_date_only,
                    )
                    .group_by(UsageDaily.engineer_id, func.date_trunc(trunc_interval, UsageDaily.date))
                    .all()
                )

                for r in results:
                    # Extract the date from the truncated timestamp and create midnight in APP_TIMEZONE
                    # date_trunc on a date column returns a naive timestamp, not UTC
                    if isinstance(r.bucket, datetime):
                        bucket_date = r.bucket.date()
                    else:
                        bucket_date = r.bucket
                    bucket_time = datetime(bucket_date.year, bucket_date.month, bucket_date.day, tzinfo=APP_TIMEZONE)
                    if bucket_time not in data_by_bucket:
                        data_by_bucket[bucket_time] = {}
                    data_by_bucket[bucket_time][r.engineer_id] = (
                        r.tokens or 0,
                        r.tokens_input or 0,
                        r.tokens_output or 0,
                        r.cost_usd or 0.0,
                    )
                    engineers_with_data.add(r.engineer_id)

            # Active minutes by day by engineer
            active_by_day_by_eng = LeaderboardService._calculate_active_minutes_by_day_batch(
                list(engineers_with_data), start_utc, end_utc
            )

            # Build complete list
            data_points = []
            current = start_time

            while current < end_time:
                bucket_data = data_by_bucket.get(current, {})

                # Compute active minutes per engineer for this bucket
                if period == 'daily':
                    day_active = active_by_day_by_eng.get(current.date(), {})
                    engineers_list = [
                        EngineerTimeSeriesData(
                            engineer_id=eng_id,
                            tokens=data[0],
                            tokens_input=data[1],
                            tokens_output=data[2],
                            cost_usd=data[3],
                            active_minutes=day_active.get(eng_id, 0),
                        )
                        for eng_id, data in bucket_data.items()
                    ]
                else:
                    # Weekly/monthly: sum daily active minutes within the bucket range per engineer
                    if period == 'weekly':
                        bucket_end = current + timedelta(weeks=1)
                    else:
                        if current.month == 12:
                            bucket_end = current.replace(year=current.year + 1, month=1)
                        else:
                            bucket_end = current.replace(month=current.month + 1)
                    # Aggregate active minutes per engineer for days in this bucket
                    bucket_active_by_eng: dict[str, int] = {}
                    for day, eng_data in active_by_day_by_eng.items():
                        if current.date() <= day < bucket_end.date():
                            for eng_id, minutes in eng_data.items():
                                bucket_active_by_eng[eng_id] = bucket_active_by_eng.get(eng_id, 0) + minutes
                    engineers_list = [
                        EngineerTimeSeriesData(
                            engineer_id=eng_id,
                            tokens=data[0],
                            tokens_input=data[1],
                            tokens_output=data[2],
                            cost_usd=data[3],
                            active_minutes=bucket_active_by_eng.get(eng_id, 0),
                        )
                        for eng_id, data in bucket_data.items()
                    ]

                data_points.append(
                    TeamTimeSeriesBucket(
                        timestamp=current.isoformat(),
                        engineers=engineers_list,
                    )
                )

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

        from loguru import logger

        logger.info(
            f'Team time series response: {len(engineers)} engineers, {len(data_points)} data points, engineers_with_data={len(engineers_with_data)}'
        )

        return TeamTimeSeriesResponse(
            period=period,
            engineers=engineers,
            data=data_points,
        )

    @staticmethod
    def post_leaderboard_to_slack(customer_id: str, as_of: date | None = None) -> PostResponse:
        """
        Get leaderboard and post it to Slack.

        Args:
            customer_id: The customer/team ID
            as_of: Optional date to get leaderboard for

        Returns:
            PostResponse with success status and date
        """
        # Import here to avoid circular import
        from src.platform.slack.service import SlackService

        leaderboard = LeaderboardService.get_leaderboard(customer_id, as_of)
        success = SlackService.post_leaderboard(leaderboard)
        return PostResponse(success=success, date=leaderboard.date)

    @staticmethod
    @staticmethod
    def award_action_medal(
        customer_id: str,
        engineer_id: str,
        medal_type: str,
        citation: str,
        awarded_by_user_id: str,
    ) -> 'EngineerMedalsResponse':
        """Award an action medal and return the updated medals response."""
        from src.app.medals.service import MedalService

        MedalService.award_action_medal(
            customer_id=customer_id,
            engineer_id=engineer_id,
            medal_type=medal_type,
            citation=citation,
            awarded_by_user_id=awarded_by_user_id,
        )
        return LeaderboardService.get_engineer_medals(customer_id, engineer_id)

    @staticmethod
    def get_engineer_medals(customer_id: str, engineer_id: str) -> 'EngineerMedalsResponse':
        """Get all medals and crowns for an engineer."""
        from collections import Counter

        from src.app.medals.models import Medal
        from src.app.records.enums import RecordPeriod, RecordScope, RecordType
        from src.app.records.models import Record
        from src.core.user.models import User

        # Get all medals for this engineer
        medal_rows = (
            db.session.query(Medal)
            .filter(Medal.engineer_id == engineer_id, Medal.customer_id == customer_id)
            .order_by(Medal.created_at.desc())
            .all()
        )

        # Resolve display names for action medal awarders
        awarder_user_ids = {m.awarded_by_user_id for m in medal_rows if m.awarded_by_user_id}
        awarder_names: dict[str, str] = {}
        if awarder_user_ids:
            users = db.session.query(User).filter(User.id.in_(awarder_user_ids)).all()
            awarder_names = {u.id: u.email.split('@')[0] for u in users}

        medals = [
            EngineerMedalEntry(
                medal_category=m.medal_category,
                medal_type=m.medal_type,
                metric_type=m.metric_type,
                period_type=m.period_type,
                period_start=m.period_start,
                value=m.value,
                created_at=m.created_at.date() if m.created_at else date.today(),
                citation=m.citation,
                awarded_by_display_name=awarder_names.get(m.awarded_by_user_id) if m.awarded_by_user_id else None,
            )
            for m in medal_rows
        ]

        # Count medals by type
        medal_counts = dict(Counter(m.medal_type for m in medal_rows))

        # Check which crowns this engineer holds
        crown_combos = [
            ('weekly_tokens', RecordType.TOKENS, RecordPeriod.WEEKLY),
            ('weekly_time', RecordType.TIME, RecordPeriod.WEEKLY),
        ]
        crowns: list[EngineerCrown] = []
        for crown_type, record_type, record_period in crown_combos:
            top_record = (
                db.session.query(Record)
                .filter(
                    Record.customer_id == customer_id,
                    Record.record_type == record_type,
                    Record.record_period == record_period,
                    Record.record_scope == RecordScope.COMPANY,
                )
                .order_by(Record.value.desc())
                .first()
            )
            if top_record and top_record.engineer_id == engineer_id:
                crowns.append(
                    EngineerCrown(
                        crown_type=crown_type,
                        value=top_record.value,
                        record_date=top_record.record_date,
                    )
                )

        return EngineerMedalsResponse(
            engineer_id=engineer_id,
            medals=medals,
            crowns=crowns,
            medal_counts=medal_counts,
        )

    @staticmethod
    def get_weekly_recap(customer_id: str, as_of: date | None = None) -> 'WeeklyRecapResponse':
        """Build weekly recap data for presentation mode."""
        from src.app.medals.enums import MedalCategory
        from src.app.medals.models import Medal
        from src.app.records.enums import RecordPeriod, RecordScope, RecordType
        from src.app.records.models import Record

        today = as_of or get_today()
        # Current week Mon-Sun
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Get weekly leaderboard entries (already sorted by tokens desc)
        weekly_entries = LeaderboardService._get_weekly_leaderboard(customer_id, today)

        # Build tokens podium (top 3)
        tokens_podium = [
            RecapPodiumEntry(
                engineer_id=e.engineer_id,
                display_name=e.display_name,
                rank=e.rank,
                value=float(e.tokens),
            )
            for e in weekly_entries[:3]
        ]

        # Build time podium (sort by active_minutes desc, take top 3)
        time_sorted = sorted(weekly_entries, key=lambda e: e.active_minutes, reverse=True)
        time_podium = [
            RecapPodiumEntry(
                engineer_id=e.engineer_id,
                display_name=e.display_name,
                rank=i + 1,
                value=float(e.active_minutes),
            )
            for i, e in enumerate(time_sorted[:3])
        ]

        # Get records set during this week
        week_records = (
            db.session.query(Record)
            .join(Engineer, Record.engineer_id == Engineer.id)
            .filter(
                Record.customer_id == customer_id,
                Record.record_date >= week_start,
                Record.record_date <= week_end,
            )
            .all()
        )

        # Get engineer names for records/crowns/medals
        engineer_names = {
            e.id: e.display_name for e in db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()
        }

        records = [
            RecapRecord(
                engineer_id=r.engineer_id,
                display_name=engineer_names.get(r.engineer_id, 'Unknown'),
                record_type=r.record_type,
                record_period=r.record_period,
                record_scope=r.record_scope,
                value=r.value,
                previous_value=r.previous_value,
                record_date=r.record_date,
            )
            for r in week_records
        ]

        # Team totals
        team_total_tokens = sum(e.tokens for e in weekly_entries)
        team_total_minutes = sum(e.active_minutes for e in weekly_entries)

        # --- Crowns: only NEW company records set during this week ---
        crown_combos = [
            ('weekly_tokens', RecordType.TOKENS, RecordPeriod.WEEKLY),
            ('weekly_time', RecordType.TIME, RecordPeriod.WEEKLY),
        ]
        crowns: list[CrownHolder] = []
        for crown_type, record_type, record_period in crown_combos:
            # Only show crowns where the record was set during this week
            new_record = (
                db.session.query(Record)
                .filter(
                    Record.customer_id == customer_id,
                    Record.record_type == record_type,
                    Record.record_period == record_period,
                    Record.record_scope == RecordScope.COMPANY,
                    Record.record_date >= week_start,
                    Record.record_date <= week_end,
                )
                .order_by(Record.value.desc())
                .first()
            )
            if new_record:
                crowns.append(
                    CrownHolder(
                        engineer_id=new_record.engineer_id,
                        display_name=engineer_names.get(new_record.engineer_id, 'Unknown'),
                        crown_type=crown_type,
                        value=new_record.value,
                        record_date=new_record.record_date,
                    )
                )

        # --- Medals: ranking medals with period_start in this week ---
        ranking_medal_rows = (
            db.session.query(Medal)
            .filter(
                Medal.customer_id == customer_id,
                Medal.medal_category == MedalCategory.RANKING,
                Medal.period_start >= week_start,
                Medal.period_start <= week_end,
            )
            .all()
        )
        medals_awarded = [
            MedalAwarded(
                engineer_id=m.engineer_id,
                display_name=engineer_names.get(m.engineer_id, 'Unknown'),
                medal_type=m.medal_type,
                metric_type=m.metric_type,
                period_type=m.period_type,
                value=m.value,
            )
            for m in ranking_medal_rows
        ]

        # --- Milestones: milestone medals created during this week ---
        week_start_utc, _ = get_day_bounds_utc(week_start)
        _, week_end_utc = get_day_bounds_utc(week_end)
        milestone_medal_rows = (
            db.session.query(Medal)
            .filter(
                Medal.customer_id == customer_id,
                Medal.medal_category == MedalCategory.MILESTONE,
                Medal.created_at >= week_start_utc,
                Medal.created_at < week_end_utc,
            )
            .all()
        )
        milestones_awarded = [
            MilestoneAwarded(
                engineer_id=m.engineer_id,
                display_name=engineer_names.get(m.engineer_id, 'Unknown'),
                medal_type=m.medal_type,
                value=m.value,
            )
            for m in milestone_medal_rows
        ]

        # --- Action medals (purple heart, etc.) created during this week ---
        from src.app.leaderboard.domains import ActionMedalAwarded
        from src.core.user.models import User

        action_medal_rows = (
            db.session.query(Medal, User.first_name, User.last_name)
            .outerjoin(User, Medal.awarded_by_user_id == User.id)
            .filter(
                Medal.customer_id == customer_id,
                Medal.medal_category == MedalCategory.ACTION,
                Medal.created_at >= week_start_utc,
                Medal.created_at < week_end_utc,
            )
            .all()
        )
        actions_awarded = [
            ActionMedalAwarded(
                engineer_id=m.engineer_id,
                display_name=engineer_names.get(m.engineer_id, 'Unknown'),
                medal_type=m.medal_type,
                citation=m.citation,
                awarded_by_display_name=f'{first} {last}' if first else None,
            )
            for m, first, last in action_medal_rows
        ]

        # --- Previous week totals for WoW comparison ---
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)
        prev_week_tokens = LeaderboardService._get_tokens_for_range_full(
            customer_id, prev_week_start, prev_week_end
        )
        prev_week_minutes = LeaderboardService._get_active_minutes_for_range(
            customer_id, prev_week_start, prev_week_end
        )

        return WeeklyRecapResponse(
            week_start=week_start,
            week_end=week_end,
            tokens_podium=tokens_podium,
            time_podium=time_podium,
            records=records,
            team_total_tokens=team_total_tokens,
            team_total_minutes=team_total_minutes,
            crowns=crowns,
            medals_awarded=medals_awarded,
            milestones_awarded=milestones_awarded,
            prev_week_tokens=prev_week_tokens,
            prev_week_minutes=prev_week_minutes,
            actions_awarded=actions_awarded,
        )

    @staticmethod
    def get_head_to_head(
        left_engineer_id: str,
        right_engineer_id: str,
        period_type: str = 'weekly',
    ) -> 'HeadToHeadResponse':
        """
        Get all-time head-to-head win counts between two engineers for a given period type.
        Counts wins by tokens and time for each period bucket.
        """
        from src.app.leaderboard.domains import HeadToHeadResponse
        from src.app.usage.models import UsageDaily

        # Determine the SQL date_trunc interval
        if period_type == 'daily':
            trunc_interval = 'day'
        elif period_type == 'weekly':
            trunc_interval = 'week'
        else:  # monthly
            trunc_interval = 'month'

        # Query token totals per period for both engineers
        rows = (
            db.session.query(
                func.date_trunc(trunc_interval, UsageDaily.date).label('period'),
                UsageDaily.engineer_id,
                func.sum(UsageDaily.total_tokens).label('tokens'),
            )
            .filter(UsageDaily.engineer_id.in_([left_engineer_id, right_engineer_id]))
            .group_by('period', UsageDaily.engineer_id)
            .all()
        )

        # Build per-period maps: {period: {engineer_id: tokens}}
        token_by_period: dict[str, dict[str, int]] = defaultdict(dict)
        for row in rows:
            token_by_period[str(row.period)][row.engineer_id] = int(row.tokens or 0)

        # Count token wins
        left_token_wins = 0
        right_token_wins = 0
        token_ties = 0
        for period_data in token_by_period.values():
            left_val = period_data.get(left_engineer_id, 0)
            right_val = period_data.get(right_engineer_id, 0)
            # Skip periods where both have 0
            if left_val == 0 and right_val == 0:
                continue
            if left_val > right_val:
                left_token_wins += 1
            elif right_val > left_val:
                right_token_wins += 1
            else:
                token_ties += 1

        # Calculate time wins using active minutes by day, then aggregate by period
        # Get the full date range from UsageDaily
        date_range = (
            db.session.query(
                func.min(UsageDaily.date).label('min_date'),
                func.max(UsageDaily.date).label('max_date'),
            )
            .filter(UsageDaily.engineer_id.in_([left_engineer_id, right_engineer_id]))
            .one()
        )

        left_time_wins = 0
        right_time_wins = 0
        time_ties = 0

        if date_range.min_date and date_range.max_date:
            start_utc, _ = get_day_bounds_utc(date_range.min_date)
            _, end_utc = get_day_bounds_utc(date_range.max_date)

            day_minutes = LeaderboardService._calculate_active_minutes_by_day_batch(
                [left_engineer_id, right_engineer_id], start_utc, end_utc
            )

            # Aggregate daily minutes into period buckets
            time_by_period: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for day, eng_data in day_minutes.items():
                if period_type == 'daily':
                    period_key = str(day)
                elif period_type == 'weekly':
                    # Monday-based week start
                    week_start = day - timedelta(days=day.weekday())
                    period_key = str(week_start)
                else:  # monthly
                    period_key = f'{day.year}-{day.month:02d}'

                for eng_id, minutes in eng_data.items():
                    time_by_period[period_key][eng_id] += minutes

            for period_data in time_by_period.values():
                left_val = period_data.get(left_engineer_id, 0)
                right_val = period_data.get(right_engineer_id, 0)
                if left_val == 0 and right_val == 0:
                    continue
                if left_val > right_val:
                    left_time_wins += 1
                elif right_val > left_val:
                    right_time_wins += 1
                else:
                    time_ties += 1

        total_periods = max(
            left_token_wins + right_token_wins + token_ties,
            left_time_wins + right_time_wins + time_ties,
        )

        return HeadToHeadResponse(
            period_type=period_type,
            left_engineer_id=left_engineer_id,
            right_engineer_id=right_engineer_id,
            left_token_wins=left_token_wins,
            right_token_wins=right_token_wins,
            token_ties=token_ties,
            left_time_wins=left_time_wins,
            right_time_wins=right_time_wins,
            time_ties=time_ties,
            total_periods=total_periods,
        )

    @staticmethod
    def get_badge_leaderboard(customer_id: str) -> 'BadgeLeaderboardResponse':
        """Get badge counts for all engineers in a customer, ranked by total."""
        from src.app.leaderboard.domains import BadgeLeaderboardEntry, BadgeLeaderboardResponse
        from src.app.medals.enums import MedalCategory
        from src.app.medals.models import Medal
        from src.app.records.enums import RecordPeriod, RecordScope
        from src.app.records.models import Record

        # Get all engineers
        engineers = db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()
        engineer_names = {e.id: e.display_name for e in engineers}

        # Get all medals for this customer
        medals = (
            db.session.query(Medal.engineer_id, Medal.medal_category, Medal.medal_type)
            .filter(Medal.customer_id == customer_id)
            .all()
        )

        # Milestone ordering (highest last so max() works)
        token_milestone_order = [
            'token_1m', 'token_10m', 'token_50m', 'token_100m',
            'token_250m', 'token_500m', 'token_1b', 'token_10b',
        ]
        time_milestone_order = [
            'time_10h', 'time_100h', 'time_500h', 'time_1000h',
            'time_2500h', 'time_5000h', 'time_10000h', 'time_25000h',
        ]
        token_milestone_rank = {m: i for i, m in enumerate(token_milestone_order)}
        time_milestone_rank = {m: i for i, m in enumerate(time_milestone_order)}

        # Count badges per engineer
        counts: dict[str, dict] = {
            e.id: {
                'gold': 0, 'silver': 0, 'bronze': 0,
                'token_milestone': None, 'time_milestone': None,
                'purple_hearts': 0,
            }
            for e in engineers
        }

        for engineer_id, medal_category, medal_type in medals:
            if engineer_id not in counts:
                continue
            if medal_category == MedalCategory.RANKING:
                if medal_type in ('gold', 'silver', 'bronze'):
                    counts[engineer_id][medal_type] += 1
            elif medal_category == MedalCategory.MILESTONE:
                if medal_type in token_milestone_rank:
                    current = counts[engineer_id]['token_milestone']
                    if current is None or token_milestone_rank[medal_type] > token_milestone_rank.get(current, -1):
                        counts[engineer_id]['token_milestone'] = medal_type
                elif medal_type in time_milestone_rank:
                    current = counts[engineer_id]['time_milestone']
                    if current is None or time_milestone_rank[medal_type] > time_milestone_rank.get(current, -1):
                        counts[engineer_id]['time_milestone'] = medal_type
            elif medal_category == MedalCategory.ACTION:
                counts[engineer_id]['purple_hearts'] += 1

        # Determine crown holders (derived from records)
        crown_holders: dict[str, dict[str, bool]] = {e.id: {'token_crown': False, 'time_crown': False} for e in engineers}
        for record_type_val, crown_key in [('tokens', 'token_crown'), ('time', 'time_crown')]:
            top_record = (
                db.session.query(Record)
                .filter(
                    Record.customer_id == customer_id,
                    Record.record_type == record_type_val,
                    Record.record_period == RecordPeriod.WEEKLY,
                    Record.record_scope == RecordScope.COMPANY,
                )
                .order_by(Record.value.desc())
                .first()
            )
            if top_record and top_record.engineer_id in crown_holders:
                crown_holders[top_record.engineer_id][crown_key] = True

        entries = []
        for engineer_id, c in counts.items():
            crowns = crown_holders.get(engineer_id, {})
            token_crown = crowns.get('token_crown', False)
            time_crown = crowns.get('time_crown', False)
            milestone_count = (1 if c['token_milestone'] else 0) + (1 if c['time_milestone'] else 0)
            crown_count = (1 if token_crown else 0) + (1 if time_crown else 0)
            total = c['gold'] + c['silver'] + c['bronze'] + milestone_count + crown_count + c['purple_hearts']
            entries.append(
                BadgeLeaderboardEntry(
                    engineer_id=engineer_id,
                    display_name=engineer_names.get(engineer_id, 'Unknown'),
                    gold=c['gold'],
                    silver=c['silver'],
                    bronze=c['bronze'],
                    token_milestone=c['token_milestone'],
                    time_milestone=c['time_milestone'],
                    token_crown=token_crown,
                    time_crown=time_crown,
                    purple_hearts=c['purple_hearts'],
                    total=total,
                )
            )

        entries.sort(key=lambda e: e.total, reverse=True)

        return BadgeLeaderboardResponse(entries=entries)
