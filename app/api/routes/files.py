"""Authenticated file metadata API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.dependencies import CurrentUser
from app.files.schemas import FileResponse, UploadURLRequest, UploadURLResponse
from app.files.service import (
    FileNotFoundError,
    FileService,
    InvalidFileMetadataError,
)

router = APIRouter(prefix="/api/v1/files", tags=["files"])


def get_file_service(request: Request) -> FileService:
    """Return the application-scoped file service."""
    return request.app.state.file_service


Service = Annotated[FileService, Depends(get_file_service)]


@router.post(
    "/upload-url",
    response_model=UploadURLResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_upload_url(
    payload: UploadURLRequest,
    user: CurrentUser,
    service: Service,
) -> UploadURLResponse:
    """Create pending metadata for a future direct-to-quarantine upload."""
    try:
        file, upload_url = service.create_upload_url(
            owner_id=user.id,
            filename=payload.filename,
            content_type=payload.content_type,
            size=payload.size,
        )
    except InvalidFileMetadataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return UploadURLResponse(
        file=FileResponse.from_file(file),
        upload_url=upload_url,
    )


@router.get("", response_model=list[FileResponse])
def list_files(user: CurrentUser, service: Service) -> list[FileResponse]:
    """List only metadata owned by the authenticated user."""
    return [FileResponse.from_file(file) for file in service.list_files(user.id)]


@router.get("/{file_id}", response_model=FileResponse)
def get_file(file_id: str, user: CurrentUser, service: Service) -> FileResponse:
    """Return owned file metadata without revealing other users' records."""
    try:
        return FileResponse.from_file(service.get_file(file_id, user.id))
    except FileNotFoundError as exc:
        raise _not_found() from exc


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str, user: CurrentUser, service: Service) -> Response:
    """Delete metadata only when it belongs to the authenticated user."""
    try:
        service.delete_file(file_id, user.id)
    except FileNotFoundError as exc:
        raise _not_found() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="File not found",
    )
