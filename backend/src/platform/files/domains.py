import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import Field, computed_field

from src.common.domain import BaseDomain
from src.common.nanoid import NanoIdType
from src.platform.files.backend import FileBackend
from src.settings import AWS_STORAGE_BUCKET_NAME


class FileCreate(BaseDomain):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4)
    file_name: Optional[str] = None
    s3_key: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    is_public: Optional[bool] = None
    uploaded_by_id: Optional[NanoIdType] = None
    size: Optional[int] = None

    @classmethod
    def duplicate(cls, file_read):
        return cls(
            file_name=file_read.file_name,
            s3_key=file_read.s3_key,
            uploaded_at=file_read.uploaded_at,
            is_public=file_read.is_public,
            uploaded_by_id=file_read.uploaded_by_id,
            size=file_read.size,
        )


class FileRead(FileCreate):
    id: uuid.UUID
    file_name: str
    s3_key: str
    uploaded_at: datetime
    is_public: bool
    uploaded_by_id: Optional[NanoIdType] = None
    size: Optional[int] = None

    @property
    def url(self) -> str:
        if self.is_public:
            return f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{self.s3_key}'
        else:
            # @TODO This would really suck in bulk...
            return FileBackend().generate_presigned_url(self.s3_key)


class FileWithUrl(FileRead):
    @computed_field
    @property
    def get_url(self) -> str:
        # List of file extensions that most modern browsers can render inline
        renderable_types = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'pdf', 'html', 'txt', 'svg']
        file_name = self.file_name
        file_type = file_name.rpartition('.')[-1]
        if file_type in renderable_types:
            mime_types = {
                'jpg': 'image/jpeg;',
                'jpeg': 'image/jpeg;',
                'png': 'image/png;',
                'gif': 'image/gif;',
                'bmp': 'image/bmp;',
                'webp': 'image/webp;',
                'pdf': 'application/pdf;',
                'html': 'text/html;',
                'txt': 'text/plain;',
                'svg': 'image/svg+xml;',
            }
            content_disposition = f'inline; filename="{file_name}"'
            content_type = mime_types.get(file_type, 'binary/octet-stream;')
        else:
            # Download
            content_disposition = f'attachment; filename="{file_name}"'
            content_type = None

        return FileBackend().generate_presigned_url(
            self.s3_key, disposition=content_disposition, content_type=content_type
        )

    @classmethod
    def from_file(cls, file_read: FileRead):
        return cls(
            id=file_read.id,
            file_name=file_read.file_name,
            s3_key=file_read.s3_key,
            uploaded_at=file_read.uploaded_at,
            is_public=file_read.is_public,
            uploaded_by_id=file_read.uploaded_by_id,
            size=file_read.size,
        )


class Part(BaseDomain):
    e_tag: str
    part_number: int


class PresignedUrlsResponse(BaseDomain):
    urls: List[str]


class GeneratePresignedUrlsRequest(BaseDomain):
    upload_id: str
    file_name: str
    num_parts: int


class CompleteMultipartUploadRequest(BaseDomain):
    file_name: str
    upload_id: str
    parts: List[Part]
    file_size: int | None = None


class CreateFileUploadPayload(BaseDomain):
    file_name: str
    file_size: int | None = None
