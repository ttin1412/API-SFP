"""File metadata request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.files.models import FileMetadata, FileStatus


class UploadURLRequest(BaseModel):
    """Client-declared metadata used to prepare a direct upload."""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)


class FileResponse(BaseModel):
    """Public representation of user-owned file metadata."""

    id: str
    original_filename: str
    storage_key: str
    detected_mime_type: Optional[str]  # noqa: UP045
    declared_mime_type: str
    extension: str
    size: int
    sha256: Optional[str]  # noqa: UP045
    status: FileStatus
    rejection_reason: Optional[str]  # noqa: UP045
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_file(cls, file: FileMetadata) -> FileResponse:
        return cls(
            id=file.id,
            original_filename=file.original_filename,
            storage_key=file.storage_key,
            detected_mime_type=file.detected_mime_type,
            declared_mime_type=file.declared_mime_type,
            extension=file.extension,
            size=file.size,
            sha256=file.sha256,
            status=file.status,
            rejection_reason=file.rejection_reason,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )


class UploadURLResponse(BaseModel):
    """Metadata prepared for an upload; URL generation arrives in Phase 3."""

    file: FileResponse
    upload_url: Optional[str] = None  # noqa: UP045
