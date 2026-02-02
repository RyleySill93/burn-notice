import logging
import uuid
from io import BytesIO
from typing import List, Optional, Tuple

import requests

from src.common.exceptions import InternalException
from src.common.nanoid import NanoIdType, generate_custom_nanoid
from src.common.utils import make_lazy
from src.core.user import UserRead, UserService
from src.platform.files.backend import FileBackend
from src.platform.files.domains import FileCreate, FileRead, FileWithUrl, Part
from src.platform.files.models import File


class FileWithUser(FileRead):
    uploaded_by: UserRead

    @classmethod
    def factory(
        cls,
        file_read: FileRead,
        uploaded_by: UserRead,
    ):
        return cls(
            id=file_read.id,
            file_name=file_read.file_name,
            s3_key=file_read.s3_key,
            uploaded_at=file_read.uploaded_at,
            is_public=file_read.is_public,
            uploaded_by_id=file_read.uploaded_by_id,
            uploaded_by=uploaded_by,
            size=file_read.size,
        )


logger = logging.getLogger(__name__)


class FileUploadFailed(InternalException): ...


class FileService:
    def __init__(self, user_service=None):
        # Avoid making a call to S3 on instantiation
        self.storage = make_lazy(FileBackend)
        self.user_service = user_service

    @classmethod
    def factory(cls) -> 'FileService':
        return cls(user_service=UserService.factory())

    def get_for_id(self, file_id: uuid.UUID) -> FileRead:
        return File.get(id=file_id)

    def get_with_url(self, file_id: uuid.UUID) -> FileWithUrl:
        file = File.get(id=file_id)
        return FileWithUrl.from_file(file)

    def list_with_urls_for_ids(self, file_ids: list[uuid.UUID]) -> list[FileWithUrl]:
        return [FileWithUrl.from_file(file) for file in File.list(File.id.in_(file_ids))]

    def list_for_ids(self, file_ids: list[uuid.UUID]) -> list[FileRead]:
        return File.list(File.id.in_(file_ids))

    def delete(self, file_id: uuid.UUID):
        File.delete(File.id == file_id)
        # @TODO should delete this from S3

    def bulk_delete(self, file_ids: list[uuid.UUID]):
        File.delete(File.id.in_(file_ids))

    def bulk_create_files(self, file_creates: list[FileCreate]) -> None:
        File.bulk_create(file_creates)

    def create(self, file_create: list[FileCreate]) -> None:
        File.create(file_create)

    def copy_files(self, files: List[FileRead | FileWithUser]) -> dict[uuid.UUID, uuid.UUID]:
        copied_files = []
        new_s3_key_by_old_s3_key = {}
        new_file_id_by_old_file_id = {}
        for file in files:
            file_id = uuid.uuid4()
            s3_key = self._make_s3_file_path(
                file_id=file_id,
                file_name=file.file_name,
                uploaded_by_id=file.uploaded_by_id,
            )
            copied_file = FileCreate(
                id=file_id,
                file_name=file.file_name,
                s3_key=s3_key,
                uploaded_by_id=file.uploaded_by_id,
                is_public=file.is_public,
                size=file.size,
                uploaded_at=file.uploaded_at,
            )
            copied_files.append(copied_file)
            new_s3_key_by_old_s3_key[file.s3_key] = s3_key
            new_file_id_by_old_file_id[file.id] = file_id
        self.storage.bulk_copy(new_s3_key_by_old_s3_key)
        File.bulk_create(copied_files)
        return new_file_id_by_old_file_id

    def create_presigned_post(
        self,
        file_name: str,
        max_size: int = 100 * 1024 * 1024,  # 100MB
        uploaded_by_id: Optional[NanoIdType] = None,
        expiration: Optional[int] = 3600,
        is_public: bool = False,
        is_temporary: bool = False,
        file_size: int | None = None,
    ) -> Tuple[FileRead, str]:
        conditions = [
            ['content-length-range', 0, max_size],
        ]
        fields = {}
        file_id = uuid.uuid4()

        s3_key = self._make_s3_file_path(
            file_id=file_id,
            file_name=file_name,
            is_temporary=is_temporary,
            uploaded_by_id=uploaded_by_id,
        )

        if is_public:
            conditions.append({'acl': 'public-read'})
            fields['acl'] = 'public-read'

        post_url = self.storage.create_presigned_post(
            object_name=s3_key,
            expiration=expiration,
            conditions=conditions,
            fields=fields,
        )

        file_create = FileCreate(
            id=file_id,
            file_name=file_name,
            s3_key=s3_key,
            uploaded_by_id=uploaded_by_id,
            is_public=is_public,
            size=file_size,
        )

        file_model = File.create(file_create)
        file = self.get_for_id(file_model.id)

        return file, post_url

    def _make_s3_file_path(
        self,
        file_name: str,
        file_id: uuid.UUID | None = None,
        uploaded_by_id: str | None = None,
        is_temporary: bool = False,
    ) -> str:
        """
        Default entropy for files stored in s3
        :param file_name:
        :return:
        """
        if is_temporary:
            name = f'temporary/{generate_custom_nanoid(5)}-{file_name}'

        else:
            uploaded_by = uploaded_by_id or 'system'
            name = f'linked/{uploaded_by}/{file_id}/{file_name}'

        return name

    def upload(
        self,
        content: BytesIO,
        file_name: str,
        uploaded_by_id: Optional[NanoIdType] = None,
        is_temporary: bool = False,
        is_public: bool = False,
    ) -> FileRead:
        # make sure the buffer is rewound
        content.seek(0)

        file, presigned_post = self.create_presigned_post(
            file_name=file_name,
            uploaded_by_id=uploaded_by_id,
            is_temporary=is_temporary,
            max_size=1000 * 1024 * 1024,  # 1GB
            is_public=is_public,
        )
        files = {'file': (file_name, content.read())}

        response = self.storage.upload_from_presigned_post(presigned_post, files)

        if response.status_code != 204:
            logger.error(response.text)
            raise FileUploadFailed(f'Failed to upload - Status: {response.status_code}')

        logger.info(f'uploaded file key: {file.s3_key}')
        return file

    def upload_light(
        self,
        content: BytesIO,
        file_name: str,
        s3_key: str,
    ) -> None:
        """
        Uploads a file to S3 without creating a record in the database
        """
        # make sure the buffer is rewound
        content.seek(0)

        presigned_post = self.storage.create_presigned_post(
            object_name=s3_key,
        )
        files = {'file': (file_name, content.read())}

        response = self.storage.upload_from_presigned_post(presigned_post, files)

        if response.status_code != 204:
            logger.error(response.text)
            raise FileUploadFailed(f'Failed to upload - Status: {response.status_code}')

        logger.info(f'uploaded file key: {s3_key}')

    def get_signed_url_for_file_id(
        self,
        file_id: uuid.UUID,
        ttl_seconds: int = None,
        disposition: str = None,
        content_type: str = None,
    ) -> str:
        """
        Returns a signed url from the data store for the File with no further permissions checks.
        :param file: The file
        :param ttl_seconds: The number of seconds the url is valid for. Default: 6 hours
        """
        file = File.get(id=file_id)
        return self.storage.generate_presigned_url(
            file.s3_key,
            expires_in=ttl_seconds,
            disposition=disposition,
            content_type=content_type,
        )

    def download(self, file_id: uuid.UUID) -> BytesIO:
        """
        Download a file from S3 and return its content as a BytesIO object.

        :param file_id: The UUID of the file to download
        :return: BytesIO object containing the file content
        :raises: RepositoryObjectNotFound if file doesn't exist
        :raises: ClientError if S3 download fails
        """
        file = File.get(id=file_id)
        content = self.storage.get_object(file.s3_key)
        return BytesIO(content)

    def upload_from_url(
        self,
        url: str,
        file_name: str,
        uploaded_by_id: Optional[NanoIdType] = None,
        is_public: bool = False,
        is_temporary: bool = False,
    ) -> FileRead:
        with requests.get(url, stream=True) as req_file:
            file = self.upload(
                content=BytesIO(req_file.content),
                file_name=file_name,
                uploaded_by_id=uploaded_by_id,
                is_public=is_public,
                is_temporary=is_temporary,
            )

        return file

    def delete_by_prefix(self, prefix: str):
        File.delete(File.s3_key.startswith(prefix))
        self.storage.delete_by_prefix(prefix=prefix)

    def get_with_details_for_id(self, file_id: uuid.UUID) -> FileWithUser:
        file_read = self.get_for_id(file_id)
        return FileWithUser.factory(
            file_read=file_read,
            uploaded_by=self.user_service.get_user_for_id(file_read.uploaded_by_id),
        )

    def list_with_details_for_id(self, file_ids: list[uuid.UUID]) -> list[FileWithUser]:
        file_reads = File.list(File.id.in_(file_ids))
        uploaded_by_ids = [file_read.uploaded_by_id for file_read in file_reads]
        users = self.user_service.list_users_for_ids(uploaded_by_ids)
        user_by_id = {user.id: user for user in users}
        return [
            FileWithUser.factory(
                file_read=file_read,
                uploaded_by=user_by_id.get(file_read.uploaded_by_id),
            )
            for file_read in file_reads
        ]

    def create_multipart_upload(self, file_name: str) -> Tuple[str, str]:
        response = self.storage.create_multipart_upload(file_name)
        return response['UploadId'], response['Key']

    def generate_presigned_urls_for_parts(self, upload_id: str, file_name: str, num_parts: int) -> List[str]:
        urls = []
        for part_number in range(1, num_parts + 1):
            presigned_url = self.storage.generate_presigned_url_for_part(upload_id, file_name, part_number)
            urls.append(presigned_url)
        return urls

    def complete_multipart_upload(
        self,
        file_name: str,
        upload_id: str,
        parts: List[Part],
        uploaded_by_id: Optional[NanoIdType] = None,
        is_public: bool = False,
        size: int | None = None,
    ):
        aws_parts = [{'ETag': part.e_tag, 'PartNumber': part.part_number} for part in parts]
        response = self.storage.complete_multipart_upload(file_name, upload_id, aws_parts)

        s3_key = response['Key']
        file_id = uuid.uuid4()

        file_create = FileCreate(
            id=file_id,
            file_name=file_name,
            s3_key=s3_key,
            uploaded_by_id=uploaded_by_id,
            is_public=is_public,
            size=size,
        )

        file_model = File.create(file_create)
        file = self.get_for_id(file_model.id)

        return file
