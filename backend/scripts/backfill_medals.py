"""
Backfill medals from historical UsageDaily data.

Run on production:
    python -m scripts.backfill_medals

This will scan all historical data and award:
- Weekly ranking medals (gold/silver/bronze for tokens and time)
- Milestone medals based on cumulative totals (with correct created_at dates)
"""

from loguru import logger
from sqlalchemy import func

from src.app.engineers.models import Engineer
from src.app.medals.service import MedalService
from src.common import context
from src.network.database import db
from src.setup import run as setup


def backfill_all():
    """Backfill medals for all customers."""
    with db():
        customer_ids = [row[0] for row in db.session.query(func.distinct(Engineer.customer_id)).all()]

    logger.info(f'Found {len(customer_ids)} customers to backfill')

    for customer_id in customer_ids:
        logger.info(f'Backfilling medals for customer {customer_id}')
        with db():
            result = MedalService.backfill_medals(customer_id)
        logger.info(
            f"  Customer {customer_id}: {result['weeks_processed']} weeks, "
            f"{result['medals_created']} medals created"
        )

    logger.info('Medal backfill complete for all customers')


def backfill_milestones_only():
    """Re-backfill milestone medals with correct created_at dates."""
    with db():
        customer_ids = [row[0] for row in db.session.query(func.distinct(Engineer.customer_id)).all()]

    logger.info(f'Found {len(customer_ids)} customers to backfill milestones')

    for customer_id in customer_ids:
        logger.info(f'Backfilling milestones for customer {customer_id}')
        with db():
            count = MedalService.backfill_milestones_with_dates(customer_id)
        logger.info(f'  Customer {customer_id}: {count} milestone medals created')

    logger.info('Milestone backfill complete for all customers')


if __name__ == '__main__':
    setup()
    context.initialize(
        user_type=context.AppContextUserType.MANUAL.value,
        user_id='backfill-script',
        breadcrumb='backfill_medals',
    )

    import sys
    if '--milestones-only' in sys.argv:
        backfill_milestones_only()
    else:
        backfill_all()
