import re
import uuid
from types import SimpleNamespace
from typing import Dict, List

import boto3
import requests
from botocore.client import Config
from botocore.exceptions import ClientError
from loguru import logger

from src import settings
from src.common.utils import split_every


def sanitize_disposition(disposition):
    """
    Sanitize the filename in a Content-Disposition header string to ensure all characters
    are representable in ISO-8859-1 encoding. Unsupported characters in the filename are
    replaced with a hyphen.

    :param disposition: Content-Disposition header string (str)
    :return: Sanitized Content-Disposition header string (str)
    """

    match = re.search(r'filename="([^"]+)"', disposition)
    if not match:
        return disposition

    original_filename = match.group(1)

    sanitized_filename = ''.join(c if ord(c) < 256 else '-' for c in original_filename)

    # Reconstruct the disposition with the sanitized filename
    sanitized_disposition = disposition.replace(original_filename, sanitized_filename)

    return sanitized_disposition


class S3Storage:
    def __init__(self):
        self.client = self._get_client()

    def _get_client(self):
        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION_NAME,
        )
        client = session.client('s3', config=Config(signature_version='s3v4'))
        return client

    def delete_by_prefix(self, prefix: str):
        paginator = self.client.get_paginator('list_objects_v2')
        response = paginator.paginate(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Prefix=prefix,
            MaxKeys=1000,
        )
        objects_to_delete = []
        for page in response:
            if 'Contents' in page:
                objects_to_delete.extend(page['Contents'])

        S3_MAX_DELETE_SIZE = 1000
        for chunk in split_every(objects_to_delete, S3_MAX_DELETE_SIZE):
            self.client.delete_objects(
                Delete={'Objects': [{'Key': s3_object['Key']} for s3_object in chunk]},
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            )
            logger.info(f'deleted {len(chunk)} objects with prefix: {prefix}')

    def create_presigned_put(self, object_name, expiration=3600):
        """Generate a presigned URL to share an S3 object

        :param bucket_name: string
        :param object_name: string
        :param expiration: Time in seconds for the presigned URL to remain valid
        :return: Presigned URL as string. If error, returns None.
        """

        # Generate a presigned URL for the S3 object
        try:
            response = self.client.generate_presigned_url(
                'put_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': object_name},
                ExpiresIn=expiration,
            )
        except ClientError as e:
            logger.error(e)
            return

        # The response contains the presigned URL
        return response

    def create_presigned_post(self, object_name, fields=None, conditions=None, expiration=3600):
        """Generate a presigned URL S3 POST request to upload a file

        :param bucket_name: string
        :param object_name: string
        :param fields: Dictionary of prefilled form fields
        :param conditions: List of conditions to include in the policy
        :param expiration: Time in seconds for the presigned URL to remain valid
        :return: Dictionary with the following keys:
            url: URL to post to
            fields: Dictionary of form fields and values to submit with the POST
        :return: None if error.
        """
        try:
            response = self.client.generate_presigned_post(
                settings.AWS_STORAGE_BUCKET_NAME,
                object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration,
            )
        except ClientError as e:
            logger.error(e)
            return

        # The response contains the presigned URL and required fields
        return response

    def generate_presigned_url(
        self,
        filename: str,
        expires_in: int = None,
        disposition: str = None,
        content_type: str = None,
    ) -> str:
        """
        Returns a signed url from the data store for the the object with no further permissions checks.
        :param filename: The full filename and path (Key) for this object in the Bucket.
        :param expires_in: The number of seconds the url is valid for. Default: 6 hours
        :return:
        """
        if expires_in is None:
            expires_in = 6 * 60 * 60  # 6 hours

        params = {
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': filename,
        }

        if disposition:
            params['ResponseContentDisposition'] = sanitize_disposition(disposition)

        if content_type:
            params['ResponseContentType'] = content_type

        url = self.client.generate_presigned_url(
            'get_object',
            Params=params,
            ExpiresIn=expires_in,
        )

        return url

    def upload_from_presigned_post(self, presigned_post, files):
        response = requests.post(presigned_post['url'], files=files, data=presigned_post['fields'])
        return response

    def create_multipart_upload(self, file_name: str) -> Dict[str, str]:  # fileName and uploadId to join parts
        response = self.client.create_multipart_upload(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file_name)
        return response

    def generate_presigned_url_for_part(self, upload_id: str, file_name: str, part_number: int) -> str:
        try:
            params = {
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': file_name,
                'UploadId': upload_id,
                'PartNumber': part_number,
            }
            presigned_url = self.client.generate_presigned_url('upload_part', Params=params, ExpiresIn=3600)
            return presigned_url
        except ClientError as e:
            logger.error(e)
            return None

    def complete_multipart_upload(self, file_name: str, upload_id: str, parts: List[Dict[str, int]]):
        try:
            response = self.client.complete_multipart_upload(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_name,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts},
            )
            return response
        except ClientError as e:
            logger.error(e)

    def bulk_copy(self, new_s3_key_by_old_s3_key: Dict[str, str]):
        for old_s3_key, new_s3_key in new_s3_key_by_old_s3_key.items():
            copy_source = {'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': old_s3_key}
            destination_key = new_s3_key
            try:
                self.client.copy_object(
                    CopySource=copy_source, Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=destination_key
                )
                logger.info(f'Copied {old_s3_key} to {new_s3_key}')
            except Exception as e:
                logger.error(f'Failed to copy {old_s3_key}: {e}')

    def get_object(self, object_name: str) -> bytes:
        """
        Download an object from S3 and return its content as bytes.

        :param object_name: The S3 key of the object to download
        :return: The object content as bytes
        :raises: ClientError if the object doesn't exist or access is denied
        """
        try:
            response = self.client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=object_name)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f'Failed to download object {object_name}: {e}')
            raise


class MockS3Storage:
    """
    Used to prevent tests from generating documents
    """

    def __init__(self):
        self.uploads = {}

    @classmethod
    def get_url_for_key(cls, object_name: str):
        return f'offline-file-store/{object_name}'

    def delete_by_prefix(self, prefix: str):
        pass

    def bulk_copy(self, new_s3_key_by_old_s3_key: Dict[str, str]):
        pass

    def create_presigned_put(self, object_name, expiration=3600):
        return {
            'url': f'offline-file-store/{object_name}',
            'fields': {
                'key': object_name,
                'AWSAccessKeyId': settings.AWS_ACCESS_KEY_ID,
                'policy': 'eyJleHBpcmF0aW9uIjogIjIwMjItMDctMThUMTY6MDg6MzJaIiwgImNvbmRpdGlvbnMiOiBbWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDAsIDEwNDg1NzYwMDBdLCB7ImJ1Y2tldCI6ICJ0YXAtc2FuZGJveC1kb2N1bWVudHMifSwgeyJrZXkiOiAidzkvb2NoUUEyLVc5LWNvbHQtcmllc3MtMjAyMi0wNy0xOFQxNTowODozMi45NjA0OTVaLnBkZiJ9XX0=',
                'signature': 'wIrg8qsnvk2O79U629qTkCJf7LQ=',
            },
        }

    def create_presigned_post(self, object_name, fields=None, conditions=None, expiration=3600):
        return {
            'url': f'offline-file-store/{object_name}',
            'fields': {
                'key': object_name,
                'AWSAccessKeyId': settings.AWS_ACCESS_KEY_ID,
                'policy': 'eyJleHBpcmF0aW9uIjogIjIwMjItMDctMThUMTY6MDg6MzJaIiwgImNvbmRpdGlvbnMiOiBbWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDAsIDEwNDg1NzYwMDBdLCB7ImJ1Y2tldCI6ICJ0YXAtc2FuZGJveC1kb2N1bWVudHMifSwgeyJrZXkiOiAidzkvb2NoUUEyLVc5LWNvbHQtcmllc3MtMjAyMi0wNy0xOFQxNTowODozMi45NjA0OTVaLnBkZiJ9XX0=',
                'signature': 'wIrg8qsnvk2O79U629qTkCJf7LQ=',
            },
        }

    def generate_presigned_url(
        self,
        filename: str,
        expires_in: int = None,
        disposition: str = None,
        content_type: str = None,
    ) -> str:
        return f'offline-file-store/{filename}'

    def upload_from_presigned_post(self, presigned_post, files):
        response = SimpleNamespace(text='', status_code=204)
        return response

    def create_multipart_upload(self, file_name: str) -> Dict[str, str]:
        upload_id = str(uuid.uuid4())
        self.uploads[upload_id] = {'file_name': file_name, 'parts': {}}
        return {'UploadId': upload_id, 'Key': file_name}

    def generate_presigned_url_for_part(self, upload_id: str, file_name: str, part_number: int) -> str:
        if upload_id not in self.uploads:
            raise ValueError('Invalid upload ID')
        return f'offline-file-store/{file_name}/part-{part_number}'

    def complete_multipart_upload(self, file_name: str, upload_id: str, parts: List[Dict[str, int]]):
        if upload_id not in self.uploads:
            raise ValueError('Invalid upload ID')
        self.uploads[upload_id]['parts'] = parts
        # Simulate successful upload completion
        return {'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file_name, 'ETag': 'etag'}

    def list_uploads(self):
        return self.uploads

    def get_object(self, object_name: str) -> bytes:
        """
        Mock implementation of get_object for testing.
        Returns dummy content for any object.

        :param object_name: The S3 key of the object to download
        :return: Mock object content as bytes
        """
        # Return some mock content for testing
        return f'Mock content for {object_name}'.encode('utf-8')


FileBackend = S3Storage
if settings.USE_MOCK_FILE_CLIENT:
    # Override with mock client
    FileBackend = MockS3Storage
