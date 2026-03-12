from datetime import date, timedelta

from loguru import logger
from sqlalchemy import func

from src.app.engineers.models import Engineer
from src.app.leaderboard.service import LeaderboardService, get_day_bounds_utc
from src.app.medals.domains import MedalCreate, MedalRead
from src.app.medals.enums import MedalCategory, MedalType, MetricType, PeriodType
from src.app.medals.models import Medal
from src.app.usage.models import UsageDaily
from src.network.database import db

# Milestone thresholds: (medal_type, metric_type, threshold_value)
MILESTONE_THRESHOLDS = [
    (MedalType.TOKEN_10M, MetricType.TOKENS, 10_000_000),
    (MedalType.TOKEN_100M, MetricType.TOKENS, 100_000_000),
    (MedalType.TOKEN_1B, MetricType.TOKENS, 1_000_000_000),
    (MedalType.TIME_100H, MetricType.TIME, 6_000),       # 100h in minutes
    (MedalType.TIME_1000H, MetricType.TIME, 60_000),     # 1000h in minutes
    (MedalType.TIME_10000H, MetricType.TIME, 600_000),   # 10000h in minutes
]

RANKING_MEDALS = [MedalType.GOLD, MedalType.SILVER, MedalType.BRONZE]


class MedalService:
    @staticmethod
    def award_ranking_medals(
        customer_id: str,
        period_type: str,
        period_start: date,
        period_end: date,
    ) -> list[MedalRead]:
        """Award gold/silver/bronze for top 3 by tokens and time in a period."""
        engineers = db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()
        if not engineers:
            return []

        engineer_ids = [e.id for e in engineers]

        # Get tokens totals for the period
        token_rows = (
            db.session.query(UsageDaily.engineer_id, func.coalesce(func.sum(UsageDaily.total_tokens), 0))
            .filter(
                UsageDaily.engineer_id.in_(engineer_ids),
                UsageDaily.date >= period_start,
                UsageDaily.date <= period_end,
            )
            .group_by(UsageDaily.engineer_id)
            .all()
        )
        token_rankings = sorted(token_rows, key=lambda r: r[1], reverse=True)

        # Get time totals for the period
        start_utc, _ = get_day_bounds_utc(period_start)
        _, end_utc = get_day_bounds_utc(period_end)
        active_by_engineer = LeaderboardService._calculate_active_minutes_batch(engineer_ids, start_utc, end_utc)
        time_rankings = sorted(active_by_engineer.items(), key=lambda r: r[1], reverse=True)

        new_medals: list[MedalRead] = []

        # Award token medals (top 3)
        for rank, (eng_id, tokens) in enumerate(token_rankings[:3]):
            if tokens <= 0:
                continue
            medal = Medal.create(
                MedalCreate(
                    engineer_id=eng_id,
                    customer_id=customer_id,
                    medal_category=MedalCategory.RANKING,
                    medal_type=RANKING_MEDALS[rank],
                    metric_type=MetricType.TOKENS,
                    period_type=period_type,
                    period_start=period_start,
                    value=float(tokens),
                )
            )
            new_medals.append(medal)

        # Award time medals (top 3)
        for rank, (eng_id, minutes) in enumerate(time_rankings[:3]):
            if minutes <= 0:
                continue
            medal = Medal.create(
                MedalCreate(
                    engineer_id=eng_id,
                    customer_id=customer_id,
                    medal_category=MedalCategory.RANKING,
                    medal_type=RANKING_MEDALS[rank],
                    metric_type=MetricType.TIME,
                    period_type=period_type,
                    period_start=period_start,
                    value=float(minutes),
                )
            )
            new_medals.append(medal)

        db.session.commit()

        logger.info(
            'Ranking medals awarded',
            customer_id=customer_id,
            period_type=period_type,
            period_start=str(period_start),
            medals_count=len(new_medals),
        )
        return new_medals

    @staticmethod
    def check_milestone_medals(customer_id: str, engineer_id: str) -> list[MedalRead]:
        """Check cumulative tokens/time against thresholds, award if not already held."""
        new_medals: list[MedalRead] = []

        # Get cumulative tokens
        cumulative_tokens = (
            db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
            .filter(UsageDaily.engineer_id == engineer_id)
            .scalar()
        ) or 0

        # Get cumulative active minutes
        start_utc, _ = get_day_bounds_utc(date(2020, 1, 1))  # far enough back
        _, end_utc = get_day_bounds_utc(date.today())
        cumulative_minutes = LeaderboardService._calculate_active_minutes(engineer_id, start_utc, end_utc)

        for medal_type, metric_type, threshold in MILESTONE_THRESHOLDS:
            value = cumulative_tokens if metric_type == MetricType.TOKENS else cumulative_minutes
            if value < threshold:
                continue

            # Check if already awarded
            existing = (
                db.session.query(Medal)
                .filter(
                    Medal.engineer_id == engineer_id,
                    Medal.customer_id == customer_id,
                    Medal.medal_category == MedalCategory.MILESTONE,
                    Medal.medal_type == medal_type,
                )
                .first()
            )
            if existing:
                continue

            medal = Medal.create(
                MedalCreate(
                    engineer_id=engineer_id,
                    customer_id=customer_id,
                    medal_category=MedalCategory.MILESTONE,
                    medal_type=medal_type,
                    metric_type=metric_type,
                    value=float(value),
                )
            )
            new_medals.append(medal)
            logger.info(
                'Milestone medal awarded',
                engineer_id=engineer_id,
                medal_type=str(medal_type),
                value=value,
                threshold=threshold,
            )

        if new_medals:
            db.session.commit()

        return new_medals

    @staticmethod
    def process_medals_for_period(customer_id: str, period_type: str, period_end: date) -> list[MedalRead]:
        """Orchestrator for ranking medals for a given period."""
        if period_type == PeriodType.WEEKLY:
            # Week is Mon-Sun, period_end is Sunday
            period_start = period_end - timedelta(days=6)
        elif period_type == PeriodType.MONTHLY:
            period_start = period_end.replace(day=1)
        else:
            return []

        return MedalService.award_ranking_medals(customer_id, period_type, period_start, period_end)

    @staticmethod
    def process_milestones_for_customer(customer_id: str) -> list[MedalRead]:
        """Check all engineers for milestone medals."""
        engineers = db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()
        new_medals: list[MedalRead] = []

        for engineer in engineers:
            medals = MedalService.check_milestone_medals(customer_id, engineer.id)
            new_medals.extend(medals)

        return new_medals

    @staticmethod
    def award_action_medal(
        customer_id: str,
        engineer_id: str,
        medal_type: str,
        citation: str,
        awarded_by_user_id: str,
    ) -> MedalRead:
        """Award an action medal (e.g. Purple Heart) to an engineer with a citation."""
        medal = Medal.create(
            MedalCreate(
                engineer_id=engineer_id,
                customer_id=customer_id,
                medal_category=MedalCategory.ACTION,
                medal_type=medal_type,
                metric_type=MetricType.TOKENS,  # not meaningful for action medals
                citation=citation,
                awarded_by_user_id=awarded_by_user_id,
                value=0,
            )
        )
        db.session.commit()
        logger.info(
            'Action medal awarded',
            engineer_id=engineer_id,
            medal_type=medal_type,
            awarded_by_user_id=awarded_by_user_id,
        )
        return medal

    @staticmethod
    def get_medals_for_engineer(engineer_id: str) -> list[MedalRead]:
        """Get all medals for an engineer."""
        medals = db.session.query(Medal).filter(Medal.engineer_id == engineer_id).all()
        return [Medal._to_domain(m) for m in medals]

    @staticmethod
    def get_medals_for_customer(customer_id: str) -> list[MedalRead]:
        """Get all medals for a customer."""
        medals = db.session.query(Medal).filter(Medal.customer_id == customer_id).all()
        return [Medal._to_domain(m) for m in medals]

    @staticmethod
    def get_medals_for_week(customer_id: str, week_start: date, week_end: date) -> list[MedalRead]:
        """Get medals awarded in a given week (ranking medals with matching period_start, plus milestones by created_at)."""
        # Ranking medals for this week
        ranking_medals = (
            db.session.query(Medal)
            .filter(
                Medal.customer_id == customer_id,
                Medal.medal_category == MedalCategory.RANKING,
                Medal.period_start >= week_start,
                Medal.period_start <= week_end,
            )
            .all()
        )

        # Milestone medals created during this week
        start_utc, _ = get_day_bounds_utc(week_start)
        _, end_utc = get_day_bounds_utc(week_end)
        milestone_medals = (
            db.session.query(Medal)
            .filter(
                Medal.customer_id == customer_id,
                Medal.medal_category == MedalCategory.MILESTONE,
                Medal.created_at >= start_utc,
                Medal.created_at < end_utc,
            )
            .all()
        )

        all_medals = ranking_medals + milestone_medals
        return [Medal._to_domain(m) for m in all_medals]

    @staticmethod
    def backfill_medals(customer_id: str) -> dict:
        """Iterate historical weeks/months, award ranking medals; check milestones for all engineers."""
        engineers = db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()

        # Find date range from UsageDaily
        min_date = (
            db.session.query(func.min(UsageDaily.date))
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(Engineer.customer_id == customer_id)
            .scalar()
        )
        max_date = (
            db.session.query(func.max(UsageDaily.date))
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(Engineer.customer_id == customer_id)
            .scalar()
        )

        if not min_date or not max_date:
            return {'weeks_processed': 0, 'months_processed': 0, 'medals_created': 0}

        medals_created = 0
        weeks_processed = 0
        months_processed = 0

        # Find first Monday on or before min_date
        first_monday = min_date - timedelta(days=min_date.weekday())
        current_monday = first_monday

        # Process complete weeks
        while current_monday + timedelta(days=6) <= max_date:
            week_end = current_monday + timedelta(days=6)
            new_medals = MedalService.award_ranking_medals(
                customer_id, PeriodType.WEEKLY, current_monday, week_end
            )
            medals_created += len(new_medals)
            weeks_processed += 1
            current_monday += timedelta(days=7)

        # Process complete months
        current_month_start = min_date.replace(day=1)
        while current_month_start <= max_date:
            # Find last day of month
            if current_month_start.month == 12:
                next_month = current_month_start.replace(year=current_month_start.year + 1, month=1)
            else:
                next_month = current_month_start.replace(month=current_month_start.month + 1)
            month_end = next_month - timedelta(days=1)

            if month_end <= max_date:
                new_medals = MedalService.award_ranking_medals(
                    customer_id, PeriodType.MONTHLY, current_month_start, month_end
                )
                medals_created += len(new_medals)
                months_processed += 1

            current_month_start = next_month

        # Check milestones for all engineers
        for engineer in engineers:
            new_medals = MedalService.check_milestone_medals(customer_id, engineer.id)
            medals_created += len(new_medals)

        logger.info(
            'Medal backfill complete',
            customer_id=customer_id,
            weeks_processed=weeks_processed,
            months_processed=months_processed,
            medals_created=medals_created,
        )
        return {
            'weeks_processed': weeks_processed,
            'months_processed': months_processed,
            'medals_created': medals_created,
        }
