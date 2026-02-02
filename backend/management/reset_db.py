import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ruff: noqa: E402
from src import settings
from src.common.logs import configure_logging

configure_logging()
from loguru import logger

from management.utils import run_terminal_cmd

if settings.ENVIRONMENT == 'production':
    raise Exception('🛑 STOP! 🛑 You likely did not mean to do this on production...')


def main():
    logger.info('Resetting database...')
    os.environ['PGPASSWORD'] = settings.DB_PASSWORD
    db_user = settings.DB_USER
    db_name = settings.DB_NAME

    drop_create_public_schema = (
        # Kill any open connections
        f'SELECT pg_terminate_backend(pg_stat_activity.pid)'
        f"FROM pg_stat_activity WHERE pg_stat_activity.datname = '{db_name}'"
        f'AND pid <> pg_backend_pid();'
        # Drop and recreate schema
        f'DROP SCHEMA IF EXISTS public CASCADE;'
        f'CREATE SCHEMA public;'
        f'GRANT ALL ON SCHEMA public TO {db_user};'
        f'GRANT ALL ON SCHEMA public TO public;'
    )

    reset_command = f'psql -U {settings.DB_USER} -d {settings.DB_NAME} -h {settings.DB_HOST} -p {settings.DB_PORT} -c "{drop_create_public_schema}"'
    print(reset_command)
    run_terminal_cmd(reset_command)


if __name__ == '__main__':
    main()
