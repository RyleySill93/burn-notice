import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from os import environ, path, remove
from pathlib import Path
from typing import List, Optional

from src import settings

from .base import BaseDbBackup

logger = logging.getLogger(__name__)


@dataclass
class LocalBackupResult:
    filename: str
    output_path: str
    database: str
    size_mb: float

    def delete(self):
        remove(self.output_path)


class LocalDatabaseBackup(BaseDbBackup):
    """Local database backup handler that stores backups in the project directory."""

    def __init__(
        self, include_app_audit: bool = False, include_system_audit: bool = False, include_vectors: bool = False
    ):
        # Override the base directory for local backups
        self._backup_dir = str(Path(__file__).parent.parent.parent.parent.parent.parent / 'backups')
        Path(self._backup_dir).mkdir(exist_ok=True)

        self.include_app_audit = include_app_audit
        self.include_system_audit = include_system_audit
        self.include_vectors = include_vectors

    def _get_exclude_tables(self) -> List[str]:
        """Get list of tables to exclude from backup."""
        exclude_tables = []

        if not self.include_app_audit:
            exclude_tables.extend(
                [
                    '--exclude-table=app_audit_*',
                    '--exclude-table=field_*_audit',
                    '--exclude-table=document_parse_*_audit',
                    '--exclude-table=data_extraction_*_audit',
                ]
            )

        if not self.include_system_audit:
            exclude_tables.extend(
                [
                    '--exclude-table=system_audit_*',
                    '--exclude-table=alembic_version_audit',
                    '--exclude-table=user_audit',
                    '--exclude-table=entity_audit',
                ]
            )

        if not self.include_vectors:
            exclude_tables.append('--exclude-table=vectorchunk')

        return exclude_tables

    def _build_pg_dump_command(self, output_path: str) -> List[str]:
        """Build pg_dump command with proper arguments."""
        cmd = [
            'pg_dump',
            f'--dbname=postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}',
            '--verbose',
            '--no-owner',
            '--no-acl',
            '--format=custom',
            '--file',
            output_path,
        ]

        # Add exclude tables
        cmd.extend(self._get_exclude_tables())

        return cmd

    def create_backup(self, custom_name: Optional[str] = None) -> LocalBackupResult:
        """Create a local backup of the database."""
        # Generate backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if custom_name:
            filename = f'{custom_name}_{timestamp}.dump'
        else:
            filename = f'{settings.DB_NAME}_backup_{timestamp}.dump'

        output_path = path.join(self.backup_dir, filename)

        # Build and run pg_dump command
        cmd = self._build_pg_dump_command(output_path)

        try:
            logger.info(f'Starting local backup of {settings.DB_NAME} to {output_path}')
            logger.info(f'Include app audit tables: {self.include_app_audit}')
            logger.info(f'Include system audit tables: {self.include_system_audit}')
            logger.info(f'Include vector tables: {self.include_vectors}')

            start = datetime.now()
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f'pg_dump failed: {result.stderr}')
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

            end = datetime.now()

            # Get file size
            size_bytes = Path(output_path).stat().st_size
            size_mb = size_bytes / (1024 * 1024)

            logger.info(f'Backup of {settings.DB_NAME} to {output_path} completed in {(end - start)}')
            logger.info(f'Backup size: {size_mb:.2f} MB')

            return LocalBackupResult(
                filename=filename, output_path=output_path, database=settings.DB_NAME, size_mb=size_mb
            )

        except subprocess.CalledProcessError as error:
            try:
                remove(output_path)
            except FileNotFoundError:
                pass
            logger.error(f'Backup of {settings.DB_NAME} to {output_path} failed')
            raise error

    def list_backups(self) -> List[Path]:
        """List all available local backup files."""
        backup_dir = Path(self.backup_dir)
        if not backup_dir.exists():
            return []

        backups = list(backup_dir.glob('*.dump'))
        return sorted(backups, key=lambda x: x.stat().st_mtime, reverse=True)

    def terminate_connections(self):
        """Terminate all active connections to the database."""
        logger.info('Terminating active database connections...')

        cmd = [
            'psql',
            f'postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/postgres',
            '-c',
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{settings.DB_NAME}' AND pid <> pg_backend_pid();",
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info('Active connections terminated')
        except subprocess.CalledProcessError as e:
            logger.warning(f'Failed to terminate connections: {e}')

    def drop_and_create_database(self):
        """Drop existing database and create a new one."""
        logger.info(f'Dropping database: {settings.DB_NAME}')

        # Drop database
        cmd_drop = [
            'dropdb',
            f'--host={settings.DB_HOST}',
            f'--port={settings.DB_PORT}',
            f'--username={settings.DB_USER}',
            '--if-exists',
            settings.DB_NAME,
        ]

        try:
            subprocess.run(cmd_drop, env={**environ, 'PGPASSWORD': settings.DB_PASSWORD}, check=True)
            logger.info('Database dropped successfully')
        except subprocess.CalledProcessError as e:
            logger.error(f'Failed to drop database: {e}')
            raise

        # Create database
        logger.info(f'Creating database: {settings.DB_NAME}')
        cmd_create = [
            'createdb',
            f'--host={settings.DB_HOST}',
            f'--port={settings.DB_PORT}',
            f'--username={settings.DB_USER}',
            '--owner',
            settings.DB_USER,
            '--encoding',
            'UTF8',
            '--template',
            'template1',
            settings.DB_NAME,
        ]

        try:
            subprocess.run(cmd_create, env={**environ, 'PGPASSWORD': settings.DB_PASSWORD}, check=True)

            # Set timezone
            cmd_tz = [
                'psql',
                f'postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}',
                '-c',
                f'ALTER DATABASE "{settings.DB_NAME}" SET timezone TO \'UTC\';',
            ]
            subprocess.run(cmd_tz, check=True)

            logger.info('Database created successfully')
        except subprocess.CalledProcessError as e:
            logger.error(f'Failed to create database: {e}')
            raise

    def restore_backup(self, backup_path: str):
        """Restore database from backup file."""
        logger.info(f'Restoring from backup: {backup_path}')

        cmd = [
            'pg_restore',
            f'--dbname=postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}',
            '--verbose',
            '--no-owner',
            '--no-acl',
            '--exit-on-error',
            str(backup_path),
        ]

        try:
            start = datetime.now()
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f'pg_restore failed: {result.stderr}')
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

            end = datetime.now()
            logger.info(f'Restored {settings.DB_NAME} from {backup_path} in {(end - start)}')

        except subprocess.CalledProcessError as error:
            logger.error(f'Error restoring backup: {error}')
            raise error
