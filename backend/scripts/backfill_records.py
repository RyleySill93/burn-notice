"""
Backfill records from historical UsageDaily data.

Run on production:
    python -m scripts.backfill_records

This will scan all historical data and establish baseline records
for daily/weekly/monthly tokens and time burned.
"""

from loguru import logger
from sqlalchemy import func

from src.app.engineers.models import Engineer
from src.app.records.service import RecordService
from src.common import context
from src.network.database import db
from src.setup import run as setup


def backfill_all():
    """Backfill records for all customers."""
    with db():
        customer_ids = [row[0] for row in db.session.query(func.distinct(Engineer.customer_id)).all()]

    logger.info(f'Found {len(customer_ids)} customers to backfill')

    for customer_id in customer_ids:
        logger.info(f'Backfilling records for customer {customer_id}')
        with db():
            result = RecordService.backfill_records(customer_id)
        logger.info(
            f"  Customer {customer_id}: {result['days_processed']} days, "
            f"{result['records_created']} records created"
        )

    logger.info('Backfill complete for all customers')


if __name__ == '__main__':
    setup()
    context.initialize(
        user_type=context.AppContextUserType.MANUAL.value,
        user_id='backfill-script',
        breadcrumb='backfill_records',
    )
    backfill_all()
