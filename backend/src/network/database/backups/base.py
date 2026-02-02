import os

from src import settings


class BaseDbBackup:
    def __init__(self):
        self._backup_dir = os.path.join(settings.TEMP_DIR, 'db-backups')
        if not os.path.exists(self._backup_dir):
            os.makedirs(self._backup_dir)

    @property
    def backup_dir(self):
        return self._backup_dir
