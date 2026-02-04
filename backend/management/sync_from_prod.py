#!/usr/bin/env python3
"""
Sync local database from production (Railway).

Usage:
    PROD_DATABASE_URL='postgresql://...' python management/sync_from_prod.py

Or set PROD_DATABASE_URL in your .env file.
"""

import os
import subprocess
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import settings
from src.common.logs import configure_logging

configure_logging()
from loguru import logger

if settings.ENVIRONMENT == 'production':
    logger.error('Cannot run this script in production environment')
    sys.exit(1)


def get_prod_url() -> str:
    """Get production DATABASE_URL from environment."""
    prod_url = os.environ.get('PROD_DATABASE_URL')
    if not prod_url:
        logger.error('PROD_DATABASE_URL environment variable is required')
        logger.info('Set it via: PROD_DATABASE_URL="postgresql://..." make sync-from-prod')
        sys.exit(1)
    return prod_url


def dump_production(prod_url: str, dump_file: str) -> None:
    """Dump production database to a file."""
    logger.info('Dumping production database...')

    # pg_dump with the connection URL
    cmd = [
        'pg_dump',
        prod_url,
        '--no-owner',
        '--no-acl',
        '--format=custom',
        f'--file={dump_file}',
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f'pg_dump failed: {result.stderr}')
        sys.exit(1)

    size_mb = os.path.getsize(dump_file) / (1024 * 1024)
    logger.info(f'Dump complete: {dump_file} ({size_mb:.1f} MB)')


def reset_local_db() -> None:
    """Reset local database schema."""
    logger.info('Resetting local database...')

    os.environ['PGPASSWORD'] = settings.DB_PASSWORD

    drop_create_sql = (
        f"SELECT pg_terminate_backend(pg_stat_activity.pid) "
        f"FROM pg_stat_activity WHERE pg_stat_activity.datname = '{settings.DB_NAME}' "
        f"AND pid <> pg_backend_pid(); "
        f"DROP SCHEMA IF EXISTS public CASCADE; "
        f"CREATE SCHEMA public; "
        f"GRANT ALL ON SCHEMA public TO {settings.DB_USER}; "
        f"GRANT ALL ON SCHEMA public TO public;"
    )

    cmd = [
        'psql',
        '-U', settings.DB_USER,
        '-d', settings.DB_NAME,
        '-h', settings.DB_HOST,
        '-p', str(settings.DB_PORT),
        '-c', drop_create_sql,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f'Reset failed: {result.stderr}')
        sys.exit(1)

    logger.info('Local database reset complete')


def restore_dump(dump_file: str) -> None:
    """Restore dump to local database."""
    logger.info('Restoring dump to local database...')

    os.environ['PGPASSWORD'] = settings.DB_PASSWORD

    cmd = [
        'pg_restore',
        '--no-owner',
        '--no-acl',
        '-U', settings.DB_USER,
        '-h', settings.DB_HOST,
        '-p', str(settings.DB_PORT),
        '-d', settings.DB_NAME,
        dump_file,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    # pg_restore may return non-zero for warnings, check stderr for actual errors
    if result.returncode != 0 and 'ERROR' in result.stderr:
        logger.error(f'Restore failed: {result.stderr}')
        sys.exit(1)

    logger.info('Restore complete')


def main():
    logger.info('Starting production database sync...')

    # Get production URL
    prod_url = get_prod_url()
    parsed = urlparse(prod_url)
    logger.info(f'Production host: {parsed.hostname}')

    # Create temp dump file
    dump_file = '/tmp/burn_notice_prod_dump.pgdump'

    try:
        # Dump production
        dump_production(prod_url, dump_file)

        # Reset local
        reset_local_db()

        # Restore to local
        restore_dump(dump_file)

        logger.info('✅ Sync from production complete!')
        logger.info('💡 You may need to run migrations if schemas differ: make migrate')

    finally:
        # Cleanup dump file
        if os.path.exists(dump_file):
            os.remove(dump_file)
            logger.info('Cleaned up temp dump file')


if __name__ == '__main__':
    main()
