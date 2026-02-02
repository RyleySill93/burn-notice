import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ruff: noqa: E402

from src import settings
from src.common.logs import configure_logging
from src.network.database.backups.local import LocalDatabaseBackup
from src.network.database.backups.s3_restore import S3DatabaseBackupRestore
from src.network.database.backups.s3_upload import S3DatabaseBackupUploader

configure_logging()
from loguru import logger

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

        def bright_white(self, text):
            return text

    term = FallbackTerminal()


def main():
    parser = argparse.ArgumentParser(description='Run database backup')
    parser.add_argument('--include-app-audit', action='store_true', help='Include application audit tables')
    parser.add_argument('--include-system-audit', action='store_true', help='Include system audit tables')
    parser.add_argument('--include-vectors', action='store_true', help='Include vector tables')
    parser.add_argument(
        '--env', type=str, default=settings.ENVIRONMENT, help='Environment (default: current environment)'
    )
    parser.add_argument('--name', type=str, help='Custom backup name (local backups only)')
    parser.add_argument('--list', action='store_true', help='List available backups for the environment')
    args = parser.parse_args()

    # Handle listing backups
    if args.list:
        if args.env == 'local':
            backup = LocalDatabaseBackup()
            backups = backup.list_backups()
            if not backups:
                logger.info('No local backups found')
                return

            print(term.bold(term.green('\n✨ Available Local Backups\n')))
            print(term.cyan('─' * 80))
            for i, backup_file in enumerate(backups):
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                size_str = f'{size_mb:.1f} MB' if size_mb < 1024 else f'{size_mb/1024:.1f} GB'
                if i == 0:
                    print(term.bright_white(f'  [{i+1}] {backup_file.name:<50} {size_str:>10} ⭐'))
                else:
                    print(f'  [{i+1}] {backup_file.name:<50} {size_str:>10}')
            print(term.cyan('─' * 80))
        else:
            restore = S3DatabaseBackupRestore()
            try:
                backups = restore.list_backups(args.env)
                if not backups:
                    logger.info(f'No backups found for environment: {args.env}')
                    return

                print(term.bold(term.green(f'\n✨ Available {args.env.upper()} Backups\n')))
                print(term.cyan('─' * 100))
                for i, backup_info in enumerate(backups):
                    size_str = (
                        f'{backup_info.size_mb:.1f} MB'
                        if backup_info.size_mb < 1024
                        else f'{backup_info.size_mb/1024:.1f} GB'
                    )
                    timestamp = backup_info.last_modified.strftime('%Y-%m-%d %H:%M')
                    cache_indicator = ' 💾' if backup_info.is_cached else ''
                    if i == 0:
                        print(
                            term.bright_white(
                                f'  [{i+1}] {backup_info.filename:<45} {size_str:>10}  {timestamp} ⭐{cache_indicator}'
                            )
                        )
                    else:
                        print(f'  [{i+1}] {backup_info.filename:<45} {size_str:>10}  {timestamp}{cache_indicator}')
                print(term.cyan('─' * 100))
                print(term.blue('\n💾 = Cached locally (faster restore)'))
            except Exception as e:
                logger.error(f'Failed to list backups: {e}')
        return

    # Handle creating backups
    if args.env == 'local':
        logger.info('Running local database backup')
        backup = LocalDatabaseBackup(
            include_app_audit=args.include_app_audit,
            include_system_audit=args.include_system_audit,
            include_vectors=args.include_vectors,
        )
        result = backup.create_backup(custom_name=args.name)
        print(term.bold(term.green('\n✅ Backup completed successfully!')))
        print(f'📁 Location: {term.cyan(result.output_path)}')
        print(
            f"💾 Size: {term.yellow(f'{result.size_mb:.1f} MB' if result.size_mb < 1024 else f'{result.size_mb/1024:.1f} GB')}"
        )
    else:
        if settings.ENVIRONMENT == 'local':
            raise Exception('🛑 STOP! 🛑 Remote backups not supported from local environment...')

        logger.info('Running database backup to S3')
        S3DatabaseBackupUploader(
            include_app_audit=args.include_app_audit,
            include_system_audit=args.include_system_audit,
            include_vectors=args.include_vectors,
        ).upload_new_backup()


if __name__ == '__main__':
    main()
