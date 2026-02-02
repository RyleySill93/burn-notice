from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, text

from src.app.usage.domains import UsageCreate, UsageDailyCreate, UsageDailyRead, UsageRead
from src.app.usage.models import Usage, UsageDaily
from src.network.database import db


class UsageService:
    @staticmethod
    def record_usage(
        engineer_id: str,
        tokens_input: int,
        tokens_output: int,
        model: str | None = None,
        session_id: str | None = None,
    ) -> UsageRead:
        """Record a token usage event."""
        return Usage.create(
            UsageCreate(
                engineer_id=engineer_id,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                model=model,
                session_id=session_id,
            )
        )

    @staticmethod
    def rollup_daily(for_date: date | None = None) -> int:
        """Aggregate raw usage into daily rollups. Returns count of engineers processed."""
        if for_date is None:
            for_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        # Get aggregated data for the date
        results = (
            db.session.query(
                Usage.engineer_id,
                func.sum(Usage.tokens_input + Usage.tokens_output).label('total_tokens'),
                func.sum(Usage.tokens_input).label('tokens_input'),
                func.sum(Usage.tokens_output).label('tokens_output'),
                func.count(func.distinct(Usage.session_id)).label('session_count'),
            )
            .filter(func.date(Usage.created_at) == for_date)
            .group_by(Usage.engineer_id)
            .all()
        )

        for row in results:
            # Upsert daily record
            existing = UsageDaily.get_or_none(engineer_id=row.engineer_id, date=for_date)
            if existing:
                UsageDaily.update(
                    existing.id,
                    total_tokens=row.total_tokens or 0,
                    tokens_input=row.tokens_input or 0,
                    tokens_output=row.tokens_output or 0,
                    session_count=row.session_count or 0,
                )
            else:
                UsageDaily.create(
                    UsageDailyCreate(
                        engineer_id=row.engineer_id,
                        date=for_date,
                        total_tokens=row.total_tokens or 0,
                        tokens_input=row.tokens_input or 0,
                        tokens_output=row.tokens_output or 0,
                        session_count=row.session_count or 0,
                    )
                )

        return len(results)

    @staticmethod
    def get_daily_totals(for_date: date) -> list[UsageDailyRead]:
        """Get daily totals for a specific date."""
        return UsageDaily.list(date=for_date)

    @staticmethod
    def get_range_totals(start_date: date, end_date: date) -> dict[str, int]:
        """Get total tokens per engineer for a date range."""
        results = (
            db.session.query(
                UsageDaily.engineer_id,
                func.sum(UsageDaily.total_tokens).label('total'),
            )
            .filter(UsageDaily.date >= start_date, UsageDaily.date <= end_date)
            .group_by(UsageDaily.engineer_id)
            .all()
        )

        return {row.engineer_id: row.total or 0 for row in results}
