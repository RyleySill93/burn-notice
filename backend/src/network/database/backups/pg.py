import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from os import environ, path, remove
from typing import List

from src import settings

from .base import BaseDbBackup

logger = logging.getLogger(__name__)


@dataclass
class PGDumpResult:
    filename: str
    output_path: str
    database: str

    def delete(self):
        remove(self.output_path)


class PGBackup(BaseDbBackup):
    PG_RESTORE = (
        'pg_restore -U {username} --clean --if-exists --no-acl --no-owner -v '
        '-j 8 -h {host} -p {port} -d {database_name} "{backup_file_path}"'
    )

    def __init__(
        self, include_app_audit: bool = False, include_system_audit: bool = False, include_vectors: bool = False
    ):
        super().__init__()
        self.include_app_audit = include_app_audit
        self.include_system_audit = include_system_audit
        self.include_vectors = include_vectors

    def _get_exclude_tables(self) -> List[str]:
        exclude_tables = []
        if not self.include_app_audit:
            exclude_tables.extend(['auditevent', 'auditlog'])
        if not self.include_system_audit:
            exclude_tables.append('audit.*')
        if not self.include_vectors:
            exclude_tables.append('vectorchunk')
        return exclude_tables

    def _build_pg_dump_command(
        self, database_host: str, database_user: str, database_name: str, output_path: str
    ) -> str:
        cmd = f'pg_dump -Fc --no-acl --no-owner -h {database_host} -U {database_user} {database_name}'

        exclude_tables = self._get_exclude_tables()
        for table in exclude_tables:
            cmd += f" --exclude-table-data='{table}'"

        cmd += f" > '{output_path}'"
        return cmd

    def dump(self, filename: str) -> PGDumpResult:
        database_name = settings.DB_NAME
        database_host = settings.DB_HOST
        database_user = settings.DB_USER
        environ['PGPASSWORD'] = settings.DB_PASSWORD
        output_path = path.join(self.backup_dir, filename)

        cmd = self._build_pg_dump_command(database_host, database_user, database_name, output_path)

        try:
            logger.info(f'Starting backup of {database_name} to {output_path}')
            start = datetime.now()
            subprocess.run(
                cmd,
                shell=True,  # nosec
                check=True,  # Raise on failure
                timeout=(5 * 60),  # 5 minutes
                universal_newlines=True,  # Decode the output
                stderr=subprocess.PIPE,  # Capture stderr
            )
            end = datetime.now()
        except subprocess.TimeoutExpired as error:
            try:
                remove(output_path)
            except FileNotFoundError:
                pass
            logger.error(f'Backup of {database_name} to {output_path} timed out')
            raise error
        except subprocess.CalledProcessError as error:
            try:
                remove(output_path)
            except FileNotFoundError:
                pass
            logger.error(
                f'Backup of {database_name} to {output_path} failed with code {error.returncode}: {error.stderr}'
            )
            raise error
        else:
            logger.info(f'Backup of {database_name} to {output_path} completed in {(end - start)}')
            return PGDumpResult(filename, str(output_path), database=database_name)

    def restore(self, file_path: str):
        database_host = settings.DB_HOST
        database_port = settings.DB_PORT
        database_user = settings.DB_USER
        database_name = settings.DB_NAME

        cmd = self.PG_RESTORE.format(
            username=database_user,
            host=database_host,
            port=database_port,
            database_name=database_name,
            backup_file_path=file_path,
        )

        try:
            logger.info(f'Restoring {database_name} from {file_path}')
            start = datetime.now()
            subprocess.run(
                cmd,
                shell=True,  # nosec
                executable='/bin/bash',
                stdout=None,
            )
            end = datetime.now()
        except subprocess.TimeoutExpired as error:
            logger.error(f'Restoring {database_name} from {file_path} timed out')
            raise error
        except subprocess.CalledProcessError as error:
            logger.error(
                f'Restoring {database_name} from {file_path} failed with code {error.returncode}: {error.stderr}'
            )
            raise error
        else:
            logger.info(f'Restored {database_name} from {file_path} in {(end - start)}')
