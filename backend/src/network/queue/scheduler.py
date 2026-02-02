"""
Schedule tasks for burn_notice
'cron' specifications are in UTC
"""

from apscheduler.schedulers.blocking import BlockingScheduler

if __name__ == '__main__':
    scheduler = BlockingScheduler()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
