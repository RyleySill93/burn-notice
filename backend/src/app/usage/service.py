from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func

from src.app.engineers.models import Engineer
from src.app.usage.domains import BackfillResponse, UsageCreate, UsageDailyCreate, UsageDailyRead, UsageRead
from src.app.usage.models import TelemetryEvent, Usage, UsageDaily
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
    def rollup_daily(for_date: date | None = None, customer_id: str | None = None) -> int:
        """
        Aggregate raw usage into daily rollups. Returns count of engineers processed.

        Only processes Usage records that haven't been rolled up yet (rolled_up_at IS NULL).
        After processing, marks the Usage records with rolled_up_at timestamp.
        """
        if for_date is None:
            for_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        rollup_time = datetime.now(timezone.utc)

        # Build query for aggregated data - only unrolled records
        query = db.session.query(
            Usage.engineer_id,
            func.sum(Usage.tokens_input + Usage.tokens_output).label('total_tokens'),
            func.sum(Usage.tokens_input).label('tokens_input'),
            func.sum(Usage.tokens_output).label('tokens_output'),
            func.count(func.distinct(Usage.session_id)).label('session_count'),
        ).filter(
            func.date(Usage.created_at) == for_date,
            Usage.rolled_up_at.is_(None),  # Only unrolled records
        )

        # Filter by customer if specified
        if customer_id:
            query = query.join(Engineer, Usage.engineer_id == Engineer.id).filter(Engineer.customer_id == customer_id)

        results = query.group_by(Usage.engineer_id).all()

        # Get cost data from TelemetryEvent for the same date
        cost_query = (
            db.session.query(
                TelemetryEvent.engineer_id,
                func.coalesce(func.sum(TelemetryEvent.cost_usd), 0.0).label('cost_usd'),
            )
            .filter(func.date(TelemetryEvent.created_at) == for_date)
            .group_by(TelemetryEvent.engineer_id)
        )
        cost_by_engineer = {row.engineer_id: row.cost_usd for row in cost_query.all()}

        for row in results:
            cost_usd = cost_by_engineer.get(row.engineer_id, 0.0)
            # Upsert daily record
            existing = UsageDaily.get_or_none(engineer_id=row.engineer_id, date=for_date)
            if existing:
                # Add to existing totals (in case of incremental rollup)
                UsageDaily.update(
                    existing.id,
                    total_tokens=existing.total_tokens + (row.total_tokens or 0),
                    tokens_input=existing.tokens_input + (row.tokens_input or 0),
                    tokens_output=existing.tokens_output + (row.tokens_output or 0),
                    session_count=existing.session_count + (row.session_count or 0),
                    cost_usd=existing.cost_usd + cost_usd,
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
                        cost_usd=cost_usd,
                    )
                )

        # Mark processed Usage records as rolled up
        if results:
            engineer_ids = [row.engineer_id for row in results]
            db.session.query(Usage).filter(
                func.date(Usage.created_at) == for_date,
                Usage.rolled_up_at.is_(None),
                Usage.engineer_id.in_(engineer_ids) if customer_id else True,
            ).update({Usage.rolled_up_at: rollup_time}, synchronize_session=False)
            db.session.commit()

        return len(results)

    @staticmethod
    def backfill_all() -> BackfillResponse:
        """Backfill all historical Usage data into UsageDaily."""
        from loguru import logger

        # Find date range with unrolled records
        result = db.session.query(
            func.min(func.date(Usage.created_at)),
            func.max(func.date(Usage.created_at)),
        ).filter(Usage.rolled_up_at.is_(None)).one()

        min_date, max_date = result[0], result[1]

        if not min_date or not max_date:
            logger.info("No unrolled usage records found")
            return BackfillResponse(
                start_date=None,
                end_date=None,
                days_processed=0,
                total_engineer_days=0,
            )

        # Don't rollup today - only up to yesterday
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        end_date = min(max_date, yesterday)

        logger.info(f"Backfilling UsageDaily from {min_date} to {end_date}")

        current_date = min_date
        total_engineers = 0
        days_processed = 0

        while current_date <= end_date:
            count = UsageService.rollup_daily(for_date=current_date)
            if count > 0:
                logger.info(f"  {current_date}: {count} engineers rolled up")
                total_engineers += count
            days_processed += 1
            current_date += timedelta(days=1)

        logger.info(f"Backfill complete: {days_processed} days, {total_engineers} engineer-days")

        return BackfillResponse(
            start_date=min_date,
            end_date=end_date,
            days_processed=days_processed,
            total_engineer_days=total_engineers,
        )

    @staticmethod
    def get_daily_totals(for_date: date, customer_id: str | None = None) -> list[UsageDailyRead]:
        """Get daily totals for a specific date."""
        if customer_id:
            return (
                db.session.query(UsageDaily)
                .join(Engineer)
                .filter(UsageDaily.date == for_date, Engineer.customer_id == customer_id)
                .all()
            )
        return UsageDaily.list(date=for_date)

    @staticmethod
    def get_range_totals(start_date: date, end_date: date, customer_id: str | None = None) -> dict[str, int]:
        """Get total tokens per engineer for a date range."""
        query = db.session.query(
            UsageDaily.engineer_id,
            func.sum(UsageDaily.total_tokens).label('total'),
        ).filter(UsageDaily.date >= start_date, UsageDaily.date <= end_date)

        if customer_id:
            query = query.join(Engineer).filter(Engineer.customer_id == customer_id)

        results = query.group_by(UsageDaily.engineer_id).all()

        return {row.engineer_id: row.total or 0 for row in results}
