import logging
from datetime import datetime

from src import settings

from .pg import PGBackup, PGDumpResult
from .s3_storage import S3BackupStorage

logger = logging.getLogger(__name__)


class S3DatabaseBackupUploader:
    def __init__(
        self, include_app_audit: bool = False, include_system_audit: bool = False, include_vectors: bool = False
    ):
        self.include_app_audit = include_app_audit
        self.include_system_audit = include_system_audit
        self.include_vectors = include_vectors

    def upload_new_backup(self):
        file_name = self._get_file_name()
        pg_dump = PGBackup(
            include_app_audit=self.include_app_audit,
            include_system_audit=self.include_system_audit,
            include_vectors=self.include_vectors,
        ).dump(file_name)
        self._upload_to_bucket(pg_dump)

    @classmethod
    def _get_file_name(cls):
        return f'backup.{settings.ENVIRONMENT}.{datetime.now():%Y-%m-%d-%H-%M-%S}.dump'

    @classmethod
    def _upload_to_bucket(cls, pg_dump: PGDumpResult):
        logger.info(f'Uploading ({pg_dump.filename}) to S3... ✅')
        engine = S3BackupStorage.for_current_environment()
        url = engine.write_file(pg_dump.filename, pg_dump.output_path)
        logger.info(f'🏰 file saved at {url} 🏰')
        logger.info(f'Cleaning up local backup file ({pg_dump.filename})...')
        pg_dump.delete()
