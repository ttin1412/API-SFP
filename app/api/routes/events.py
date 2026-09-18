"""Internal endpoints for Google Cloud event delivery."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.files.service import FileService, InvalidUploadEventError

router = APIRouter(prefix="/api/v1/events", tags=["events"])


class StorageObjectData(BaseModel):
    """Relevant fields from Cloud Storage object event data."""

    bucket: str = Field(min_length=1)
    name: str = Field(min_length=1)


def get_file_service(request: Request) -> FileService:
    return request.app.state.file_service


Service = Annotated[FileService, Depends(get_file_service)]
CloudEventType = Annotated[str, Header(alias="ce-type")]


@router.post("/storage", status_code=status.HTTP_204_NO_CONTENT)
def storage_event(
    payload: StorageObjectData,
    event_type: CloudEventType,
    service: Service,
) -> Response:
    """Apply a Cloud Storage object-finalized event to file metadata."""
    try:
        service.handle_upload_finalized(
            event_type=event_type,
            bucket=payload.bucket,
            storage_key=payload.name,
        )
    except InvalidUploadEventError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
