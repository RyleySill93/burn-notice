"""
Schedule tasks for burn-notice
'cron' specifications are in UTC

Jobs:
- Daily rollup at 8:05 AM UTC (12:05 AM PST) - aggregates yesterday's usage
- Leaderboard post at 5:00 PM UTC (9:00 AM PST) - posts to Slack
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from src.setup import setup


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

    logger.info('Scheduler starting with jobs:')
    logger.info('  - Daily rollup: 08:05 UTC (00:05 PST)')
    logger.info('  - Leaderboard post: 17:00 UTC (09:00 PST)')

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info('Scheduler stopped')
        scheduler.shutdown()
