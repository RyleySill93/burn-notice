import uuid

from fastapi import APIRouter, Depends, status

from src.common.exceptions import APIException
from src.common.nanoid import NanoIdType
from src.core.authentication import AuthenticatedUser, AuthenticatedUserGuard
from src.network.database.repository.exceptions import RepositoryObjectNotFound
from src.platform.files.domains import (
    CompleteMultipartUploadRequest,
    CreateFileUploadPayload,
    FileWithUrl,
    GeneratePresignedUrlsRequest,
    PresignedUrlsResponse,
)
from src.platform.files.service import FileService

router = APIRouter()


@router.post('/upload')
def create_file_upload(
    payload: CreateFileUploadPayload,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    file_service: FileService = Depends(FileService),
) -> dict:
    # docstodo - create inactive file first. Make frontend activate file once we've confirmed teh s3 upload
    file, presigned_post = file_service.create_presigned_post(
        file_name=payload.file_name,
        uploaded_by_id=user.id,
        file_size=payload.file_size,
    )

    get_url = file_service.get_signed_url_for_file_id(file.id)

    return {
        's3Headers': presigned_post,
        'url': file.url,
        'fileId': file.id,
        'getUrl': get_url,
        'fileName': file.file_name,
        'size': file.size,
    }


@router.post('/multipart/init')
def create_multipart_upload(
    payload: CreateFileUploadPayload,
    file_service: FileService = Depends(FileService),
) -> dict:
    upload_id, key = file_service.create_multipart_upload(payload.file_name)
    return {'uploadId': upload_id, 'fileName': key}


@router.post('/multipart/parts')
def generate_presigned_urls_for_parts(
    payload: GeneratePresignedUrlsRequest,
    file_service: FileService = Depends(FileService),
) -> PresignedUrlsResponse:
    urls = file_service.generate_presigned_urls_for_parts(payload.upload_id, payload.file_name, payload.num_parts)
    return PresignedUrlsResponse(urls=urls)


@router.post('/multipart/complete')
def complete_multipart_upload(
    payload: CompleteMultipartUploadRequest,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    file_service: FileService = Depends(FileService),
) -> dict:
    file = file_service.complete_multipart_upload(
        file_name=payload.file_name,
        upload_id=payload.upload_id,
        parts=payload.parts,
        uploaded_by_id=user.id,
        is_public=False,
        size=payload.file_size,
    )

    get_url = file_service.get_signed_url_for_file_id(file.id)

    return {
        'url': file.url,
        'fileId': file.id,
        'getUrl': get_url,
        'fileName': file.file_name,
        'size': file.size,
    }


@router.delete('/delete-file/{file_id}')
def delete_file(
    file_id: NanoIdType,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    file_service: FileService = Depends(FileService),
) -> None:
    file_service.delete(file_id=file_id)


@router.post('/list-files-for-ids')
def list_files_for_ids(
    file_ids: list[uuid.UUID],
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    file_service: FileService = Depends(FileService),
) -> list[FileWithUrl]:
    # todo - permissioning this endpoint to an entity would be very difficult
    # Limit to 100 file IDs to prevent abuse
    if len(file_ids) > 100:
        raise APIException(
            code=status.HTTP_400_BAD_REQUEST,
            message='Maximum file request limit hit',
        )

    # docstodo - permissioning this endpoint
    return file_service.list_with_urls_for_ids(file_ids=file_ids)


@router.post('/get-file-with-url/{file_id}')
def get_file_with_url(
    file_id: uuid.UUID,
    user: AuthenticatedUser = AuthenticatedUserGuard(),
    file_service: FileService = Depends(FileService),
) -> FileWithUrl:
    # todo - permissioning this endpoint to an entity would be very difficult
    try:
        return file_service.get_with_url(file_id=file_id)
    except RepositoryObjectNotFound:
        # Return 403 instead of 404 to avoid leaking information
        raise APIException(
            code=status.HTTP_403_FORBIDDEN,
            message='Permission denied',
        )
