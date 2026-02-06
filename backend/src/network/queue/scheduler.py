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

    logger.info('Scheduler starting with jobs:')
    logger.info('  - Daily rollup: 08:05 UTC (00:05 PST)')
    logger.info('  - Leaderboard post: 17:00 UTC (09:00 PST)')
    logger.info('  - GitHub sync: Every 2 hours')
    logger.info('  - GitHub rollup: 08:10 UTC (00:10 PST)')

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info('Scheduler stopped')
        scheduler.shutdown()
