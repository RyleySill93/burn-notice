import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ruff: noqa: E402
from src import settings
from src.common.logs import configure_logging
from src.network.database.backups.local import LocalDatabaseBackup
from src.network.database.backups.s3_restore import S3DatabaseBackupRestore
from src.network.database.backups.selectors import confirm_restore, select_local_backup, select_s3_backup

configure_logging()
from loguru import logger

from management.reset_db import main as reset_db

try:
    from blessed import Terminal

    term = Terminal()
except ImportError:
    # Fallback if blessed is not installed
    class FallbackTerminal:
        def bold(self, text):
            return text

        def green(self, text):
            return text

        def yellow(self, text):
            return text

        def cyan(self, text):
            return text

    term = FallbackTerminal()


def main():
    parser = argparse.ArgumentParser(description='Restore database from backup')
    parser.add_argument(
        '--env', default='staging', help='Environment to restore from (default: staging, or "local" for local backups)'
    )
    parser.add_argument('--file', type=str, help='Specific backup file to restore (local backups only)')
    parser.add_argument('--list', action='store_true', help='List available backups (local backups only)')
    parser.add_argument('--latest', action='store_true', help='Restore from latest backup (local backups only)')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    # Determine if we should skip confirmation (local environment or force flag)
    skip_confirmation = args.force or settings.ENVIRONMENT == 'local'

    if args.env == 'local':
        # Handle local backup restore
        backup = LocalDatabaseBackup()

        if args.list:
            backups = backup.list_backups()
            if not backups:
                logger.info('No local backups found')
                return

            logger.info('Available local backups:')
            for i, backup_file in enumerate(backups):
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                logger.info(f'  [{i+1}] {backup_file.name} ({size_mb:.2f} MB)')
            return

        # Determine which backup to restore
        backup_path = None

        if args.file:
            backup_path = Path(args.file)
            if not backup_path.exists():
                # Try in backups directory
                backup_path = Path(backup.backup_dir) / args.file
                if not backup_path.exists():
                    logger.error(f'Backup file not found: {args.file}')
                    sys.exit(1)
        elif args.latest:
            backups = backup.list_backups()
            if not backups:
                logger.error('No local backups found')
                sys.exit(1)
            backup_path = backups[0]
        else:
            # Interactive selection
            backups = backup.list_backups()
            if not backups:
                logger.error('No local backups found')
                sys.exit(1)

            backup_path = select_local_backup(backups)
            if not backup_path:
                return

        # Confirm restore
        if not skip_confirmation:
            if not confirm_restore(backup_path.name, settings.DB_NAME):
                return

        try:
            # Terminate connections
            backup.terminate_connections()

            # Drop and recreate database
            backup.drop_and_create_database()

            # Restore backup
            backup.restore_backup(str(backup_path))

            print(term.bold(term.green('\n✅ Database restored successfully!')))
            print(f'📁 Restored from: {term.cyan(backup_path.name)}')
            print(
                term.yellow('\n💡 Note: You may need to run migrations if the backup is from an older schema version')
            )

        except Exception as e:
            logger.error(f'❌ Restore failed: {e}')
            sys.exit(1)

    else:
        # Handle S3 backup restore
        if settings.ENVIRONMENT == 'production':
            raise Exception('🛑 STOP! 🛑 You likely did not mean to do this on production...')

        restore = S3DatabaseBackupRestore()

        if args.list:
            try:
                backups = restore.list_backups(args.env)
                if not backups:
                    logger.info(f'No backups found for environment: {args.env}')
                    return

                logger.info(f'Available {args.env} backups:')
                for i, backup_info in enumerate(backups):
                    logger.info(
                        f"  [{i+1}] {backup_info.filename} ({backup_info.size_mb:.2f} MB) - {backup_info.last_modified.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
            except Exception as e:
                logger.error(f'Failed to list backups: {e}')
            return

        # Determine which backup to restore
        backup_to_restore = None

        if args.latest:
            # Use latest backup
            backup_to_restore = 'latest'
        else:
            # Interactive selection
            try:
                backups = restore.list_backups(args.env)
                if not backups:
                    logger.error(f'No backups found for environment: {args.env}')
                    sys.exit(1)

                backup_to_restore = select_s3_backup(backups, args.env)
                if not backup_to_restore:
                    return
            except Exception as e:
                logger.error(f'Error selecting backup: {e}')
                sys.exit(1)

        # Confirm restore
        if not skip_confirmation:
            backup_name = 'latest backup' if backup_to_restore == 'latest' else backup_to_restore.filename
            if not confirm_restore(backup_name, settings.DB_NAME):
                return

        reset_db()

        try:
            if backup_to_restore == 'latest':
                logger.info(f'Restoring latest backup from {args.env}')
                restore.restore_latest_backup(args.env)
                backup_name_display = 'latest backup'
            else:
                logger.info(f'Restoring backup {backup_to_restore.filename} from {args.env}')
                restore.restore_specific_backup(args.env, backup_to_restore.key)
                backup_name_display = backup_to_restore.filename

            print(term.bold(term.green('\n✅ Database restored successfully!')))
            print(f'📁 Restored from: {term.cyan(f"{args.env}/{backup_name_display}")}')
            print(
                term.yellow('\n💡 Note: You may need to run migrations if the backup is from an older schema version')
            )

        except Exception as e:
            logger.error(f'❌ Restore failed: {e}')
            sys.exit(1)


if __name__ == '__main__':
    main()
