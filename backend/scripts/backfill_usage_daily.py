"""
Backfill UsageDaily from historical Usage records.

Run on production:
    python -m scripts.backfill_usage_daily

This will find all unrolled Usage records and aggregate them into UsageDaily.
"""

from datetime import date, datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import func

from src.app.usage.models import Usage
from src.app.usage.service import UsageService
from src.network.database import db
from src.setup import run as setup


def get_date_range_with_unrolled_usage() -> tuple[date | None, date | None]:
    """Find the min and max dates that have unrolled Usage records."""
    with db():
        result = db.session.query(
            func.min(func.date(Usage.created_at)),
            func.max(func.date(Usage.created_at)),
        ).filter(Usage.rolled_up_at.is_(None)).one()

        return result[0], result[1]


def backfill_all():
    """Backfill all historical Usage data into UsageDaily."""
    min_date, max_date = get_date_range_with_unrolled_usage()

    if not min_date or not max_date:
        logger.info("No unrolled usage records found. Nothing to backfill.")
        return

    # Don't rollup today - only up to yesterday
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    end_date = min(max_date, yesterday)

    logger.info(f"Backfilling UsageDaily from {min_date} to {end_date}")

    current_date = min_date
    total_engineers = 0
    days_processed = 0

    while current_date <= end_date:
        with db():
            count = UsageService.rollup_daily(for_date=current_date)
        if count > 0:
            logger.info(f"  {current_date}: {count} engineers rolled up")
            total_engineers += count
        days_processed += 1
        current_date += timedelta(days=1)

    logger.info(f"Backfill complete: {days_processed} days, {total_engineers} engineer-days processed")


if __name__ == "__main__":
    setup()
    backfill_all()
