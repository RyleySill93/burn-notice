"""
Schedule tasks for burn-notice
'cron' specifications are in UTC

Jobs:
- Daily rollup at 8:05 AM UTC (12:05 AM PST) - aggregates yesterday's usage
- Leaderboard post at 5:00 PM UTC (9:00 AM PST) - posts to Slack
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from src.setup import run as setup


def run_daily_rollup():
    """Aggregate yesterday's usage into daily totals."""
    from src.app.usage.service import UsageService

    logger.info('Running daily rollup')
    count = UsageService.rollup_daily()
    logger.info(f'Daily rollup complete: {count} engineers processed')


def run_leaderboard_post():
    """Post leaderboard to Slack."""
    from src.app.leaderboard.service import LeaderboardService
    from src.platform.slack.service import SlackService

    logger.info('Posting leaderboard to Slack')
    leaderboard = LeaderboardService.get_leaderboard()
    success = SlackService.post_leaderboard(leaderboard)
    logger.info(f'Leaderboard post {"succeeded" if success else "failed"}')


def run_github_sync():
    """Sync GitHub data for all connected engineers."""
    from src.app.github.service import GitHubService

    logger.info('Running GitHub sync')
    github_service = GitHubService.factory()
    results = github_service.sync_all_engineers()
    logger.info(
        'GitHub sync complete',
        engineers_synced=results['engineers_synced'],
        engineers_failed=results['engineers_failed'],
        total_commits=results['total_commits'],
        total_prs=results['total_prs'],
    )


def run_github_rollup():
    """Aggregate GitHub data into daily rollups."""
    from src.app.github.service import GitHubService

    logger.info('Running GitHub daily rollup')
    github_service = GitHubService.factory()
    count = github_service.rollup_daily()
    logger.info(f'GitHub rollup complete: {count} engineers processed')


def run_record_check():
    """Check for new records after daily rollup."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from src.app.engineers.models import Engineer
    from src.app.records.service import RecordService
    from src.network.database import db

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    logger.info('Checking for new records', for_date=str(yesterday))

    customer_ids = [row[0] for row in db.session.query(func.distinct(Engineer.customer_id)).all()]

    total_records = 0
    for customer_id in customer_ids:
        new_records = RecordService.process_records_for_date(customer_id, yesterday)
        total_records += len(new_records)

    logger.info(f'Record check complete: {total_records} new records set')


def run_weekly_medals():
    """Award weekly ranking medals. Runs Sundays after record check."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from src.app.engineers.models import Engineer
    from src.app.medals.enums import PeriodType
    from src.app.medals.service import MedalService
    from src.network.database import db

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    # Only run if yesterday was Sunday (end of week)
    if yesterday.weekday() != 6:
        logger.info('Skipping weekly medals - yesterday was not Sunday')
        return

    logger.info('Awarding weekly medals', for_date=str(yesterday))
    customer_ids = [row[0] for row in db.session.query(func.distinct(Engineer.customer_id)).all()]

    total_medals = 0
    for customer_id in customer_ids:
        new_medals = MedalService.process_medals_for_period(customer_id, PeriodType.WEEKLY, yesterday)
        total_medals += len(new_medals)

    logger.info(f'Weekly medals complete: {total_medals} medals awarded')


def run_milestone_check():
    """Check all engineers for milestone medals. Runs daily after rollup."""
    from sqlalchemy import func

    from src.app.engineers.models import Engineer
    from src.app.medals.service import MedalService
    from src.network.database import db

    logger.info('Checking for milestone medals')
    customer_ids = [row[0] for row in db.session.query(func.distinct(Engineer.customer_id)).all()]

    total_milestones = 0
    for customer_id in customer_ids:
        new_medals = MedalService.process_milestones_for_customer(customer_id)
        total_milestones += len(new_medals)

    logger.info(f'Milestone check complete: {total_milestones} milestones awarded')


if __name__ == '__main__':
    # Initialize application (DB, etc.)
    setup()

    scheduler = BlockingScheduler()

    # Daily rollup at 8:05 AM UTC (12:05 AM PST)
    scheduler.add_job(
        run_daily_rollup,
        'cron',
        hour=8,
        minute=5,
        id='daily_rollup',
        name='Daily Usage Rollup',
    )

    # Leaderboard post at 5:00 PM UTC (9:00 AM PST)
    scheduler.add_job(
        run_leaderboard_post,
        'cron',
        hour=17,
        minute=0,
        id='leaderboard_post',
        name='Post Leaderboard to Slack',
    )

    # GitHub sync every 2 hours
    scheduler.add_job(
        run_github_sync,
        'cron',
        hour='*/2',
        minute=0,
        id='github_sync',
        name='GitHub Data Sync',
    )

    # GitHub daily rollup at 8:10 AM UTC (12:10 AM PST)
    scheduler.add_job(
        run_github_rollup,
        'cron',
        hour=8,
        minute=10,
        id='github_rollup',
        name='GitHub Daily Rollup',
    )

    # Record check at 8:15 AM UTC (12:15 AM PST) - after daily rollup
    scheduler.add_job(
        run_record_check,
        'cron',
        hour=8,
        minute=15,
        id='record_check',
        name='Record Check',
    )

    # Weekly medals at 8:20 AM UTC (12:20 AM PST) - after record check, runs daily but only acts on Mondays (checks if yesterday was Sunday)
    scheduler.add_job(
        run_weekly_medals,
        'cron',
        hour=8,
        minute=20,
        id='weekly_medals',
        name='Weekly Medal Awards',
    )

    # Milestone check at 8:25 AM UTC (12:25 AM PST) - after daily rollup
    scheduler.add_job(
        run_milestone_check,
        'cron',
        hour=8,
        minute=25,
        id='milestone_check',
        name='Milestone Medal Check',
    )

    logger.info('Scheduler starting with jobs:')
    logger.info('  - Daily rollup: 08:05 UTC (00:05 PST)')
    logger.info('  - Leaderboard post: 17:00 UTC (09:00 PST)')
    logger.info('  - GitHub sync: Every 2 hours')
    logger.info('  - GitHub rollup: 08:10 UTC (00:10 PST)')
    logger.info('  - Record check: 08:15 UTC (00:15 PST)')
    logger.info('  - Weekly medals: 08:20 UTC (00:20 PST)')
    logger.info('  - Milestone check: 08:25 UTC (00:25 PST)')

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info('Scheduler stopped')
        scheduler.shutdown()
