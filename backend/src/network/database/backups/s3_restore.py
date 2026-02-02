import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List

import requests

from .base import BaseDbBackup
from .pg import PGBackup
from .s3_storage import S3BackupStorage

logger = logging.getLogger(__name__)


@dataclass
class S3BackupInfo:
    filename: str
    key: str
    last_modified: datetime
    size_mb: float
    is_cached: bool = False


class S3DatabaseBackupRestore(BaseDbBackup):
    def restore_latest_backup(self, environment: str):
        file_path, remove_old_files = self.download_latest_backup(environment)
        try:
            PGBackup().restore(file_path)
        finally:
            if remove_old_files:
                for file in remove_old_files:
                    # Cleanup file path
                    remove_file_path = os.path.join(self.backup_dir, file)
                    os.remove(remove_file_path)

    def download_latest_backup(self, environment: str) -> tuple[str, list[str]]:
        """
        Grabs the latest DB backup from S3 if it is different than
        what is cached locally
        """
        engine = S3BackupStorage.for_environment(environment)

        try:
            _, last_backup_path = engine.get_latest_in_directory()
        except IndexError:
            raise Exception('There are no backups available 💀.')
        url = engine.get_file_url(last_backup_path)
        file_name = url.split('/')[-1].split('?')[0]
        logger.info(f'Found latest backup: {file_name} 🗄️')
        file_path = os.path.join(self.backup_dir, file_name)

        if os.path.exists(file_path):
            logger.info('Using cached backup 💾 (skipping download)')
            return file_path, []

        # Otherwise download new file
        logger.info('Downloading backup file from S3... (not cached)')
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Will raise if request was not OK

        other_backup_files = os.listdir(self.backup_dir)
        remove_old_files = [
            file
            for file in other_backup_files
            # ignore current file for caching
            if file != file_name
        ]

        with open(file_path, 'wb') as dump:
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    dump.write(chunk)
                    dump.flush()

        logger.info(f'Downloaded to {file_path} ✅')
        return file_path, remove_old_files

    def list_backups(self, environment: str, limit: int = 30) -> List[S3BackupInfo]:
        """List all available backups for the given environment."""
        engine = S3BackupStorage.for_environment(environment)

        # Get backups with sizes, already sorted by date (newest first)
        backups = engine.list_directory_with_sizes(min_file_size=1024, limit=limit)  # Min 1KB to filter out empty files

        backup_infos = []
        for last_modified, key, size_bytes in backups:
            filename = key.split('/')[-1]
            size_mb = size_bytes / (1024 * 1024) if size_bytes else 0

            # Check if this backup is cached locally
            cache_path = os.path.join(self.backup_dir, filename)
            is_cached = os.path.exists(cache_path)

            backup_infos.append(
                S3BackupInfo(
                    filename=filename, key=key, last_modified=last_modified, size_mb=size_mb, is_cached=is_cached
                )
            )

        return backup_infos

    def restore_specific_backup(self, environment: str, backup_key: str):
        """Restore a specific backup by its S3 key."""
        file_path, remove_old_files = self.download_specific_backup(environment, backup_key)
        try:
            PGBackup().restore(file_path)
        finally:
            if remove_old_files:
                for file in remove_old_files:
                    # Cleanup file path
                    remove_file_path = os.path.join(self.backup_dir, file)
                    os.remove(remove_file_path)

    def download_specific_backup(self, environment: str, backup_key: str) -> tuple[str, list[str]]:
        """Download a specific backup from S3."""
        engine = S3BackupStorage.for_environment(environment)

        url = engine.get_file_url(backup_key)
        file_name = backup_key.split('/')[-1]
        logger.info(f'Downloading backup: {file_name} 🗄️')
        file_path = os.path.join(self.backup_dir, file_name)

        if os.path.exists(file_path):
            logger.info('Using cached backup 💾 (skipping download)')
            return file_path, []

        # Download the file
        logger.info('Downloading backup file from S3... (not cached)')
        response = requests.get(url, stream=True)
        response.raise_for_status()

        other_backup_files = os.listdir(self.backup_dir)
        remove_old_files = [file for file in other_backup_files if file != file_name]

        with open(file_path, 'wb') as dump:
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    dump.write(chunk)
                    dump.flush()

        logger.info(f'Downloaded to {file_path} ✅')
        return file_path, remove_old_files
