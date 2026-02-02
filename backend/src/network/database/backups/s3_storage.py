import operator

from boto3 import resource as boto3_resource
from botocore.config import Config
from decouple import config


class S3BackupStorage:
    def __init__(
        self,
        bucket_name: str,
        access_key: str,
        secret_key: str,
    ):
        self.BUCKET_NAME = bucket_name
        self.ACCESS_KEY = access_key
        self.SECRET_KEY = secret_key

    @classmethod
    def for_current_environment(cls) -> 'S3BackupStorage':
        from src import settings

        return cls.for_environment(settings.ENVIRONMENT)

    @classmethod
    def for_environment(cls, environment: str) -> 'S3BackupStorage':
        backup_storage_factory_by_env = {
            'demo': cls.for_demo,
            'production': cls.for_production,
            'staging': cls.for_staging,
        }
        try:
            storage_factory = backup_storage_factory_by_env[environment]
        except KeyError:
            raise ValueError(f'Unrecognized backup environment: {environment}')

        return storage_factory()

    @classmethod
    def for_demo(cls) -> 'S3BackupStorage':
        return cls(
            bucket_name=config('DEMO_AWS_DB_BACKUPS_BUCKET_NAME'),
            access_key=config('DEMO_AWS_DB_BACKUPS_ACCESS_KEY_ID'),
            secret_key=config('DEMO_AWS_DB_BACKUPS_SECRET_ACCESS_KEY'),
        )

    @classmethod
    def for_staging(cls) -> 'S3BackupStorage':
        return cls(
            bucket_name=config('STAGING_AWS_DB_BACKUPS_BUCKET_NAME'),
            access_key=config('STAGING_AWS_DB_BACKUPS_ACCESS_KEY_ID'),
            secret_key=config('STAGING_AWS_DB_BACKUPS_SECRET_ACCESS_KEY'),
        )

    @classmethod
    def for_production(cls) -> 'S3BackupStorage':
        return cls(
            bucket_name=config('PRODUCTION_AWS_DB_BACKUPS_BUCKET_NAME'),
            access_key=config('PRODUCTION_AWS_DB_BACKUPS_ACCESS_KEY_ID'),
            secret_key=config('PRODUCTION_AWS_DB_BACKUPS_SECRET_ACCESS_KEY'),
        )

    @property
    def bucket(self):
        s3 = boto3_resource(
            's3',
            aws_access_key_id=self.ACCESS_KEY,
            aws_secret_access_key=self.SECRET_KEY,
            config=Config(signature_version='s3v4'),
        )

        return s3.Bucket(self.BUCKET_NAME)

    def write_file(self, name, path, acl=None):
        """Write the specified file."""
        self.bucket.meta.client.upload_file(path, self.bucket.name, name)
        return self.get_file_url(self.get_latest_in_directory()[-1])

    def get_file_url(self, filepath):
        """Returns URL for specified file"""
        return self.bucket.meta.client.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': self.bucket.name, 'Key': filepath},
        )

    def delete_files(self, files):
        if files:
            for f in files:
                self.__delete_file_from_bucket(f)

    def __delete_file_from_bucket(self, key):
        self.bucket.meta.client.delete_object(
            Bucket=self.bucket.name,
            Key=key,
        )

    def list_directory(self, marker='', prefix='', min_file_size=None):
        """List all stored files for the specified folder"""
        files_list = self.bucket.objects.filter(Marker=marker, Prefix=prefix)
        files_dict = {}
        for file_ in files_list:
            # Skip files smaller than minimum
            if min_file_size and file_.size < min_file_size:
                continue
            files_dict[file_.last_modified] = file_.key

        return sorted(files_dict.items(), key=operator.itemgetter(0))

    def list_directory_with_sizes(self, marker='', prefix='', min_file_size=None, limit=None):
        """List all stored files with their sizes for the specified folder"""
        # For performance, if we want recent backups, we can use a smarter approach
        # by filtering to recent dates if we have many files
        files_info = []

        # Use pagination to avoid loading everything at once
        paginator = self.bucket.meta.client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=self.bucket.name,
            Prefix=prefix,
            PaginationConfig={'PageSize': 1000},  # Process in chunks
        )

        for page in page_iterator:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                # Skip files smaller than minimum
                if min_file_size and obj['Size'] < min_file_size:
                    continue
                files_info.append((obj['LastModified'], obj['Key'], obj['Size']))

        # Sort by date (newest first) then apply limit
        files_info.sort(key=operator.itemgetter(0), reverse=True)

        if limit:
            files_info = files_info[:limit]

        return files_info

    def get_latest_in_directory(self, marker='', prefix=''):
        """Returns last modified backup for specified folder"""
        return self.list_directory(marker=marker, prefix=prefix)[-1]
