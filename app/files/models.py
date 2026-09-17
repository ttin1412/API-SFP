"""File metadata domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class FileStatus(str, Enum):
    """States in the secure file-processing lifecycle."""

    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    SCANNING = "SCANNING"
    SAFE = "SAFE"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class FileMetadata:
    """Persistent metadata for one user-owned file."""

    id: str
    owner_id: str
    original_filename: str
    storage_key: str
    detected_mime_type: str | None
    declared_mime_type: str
    extension: str
    size: int
    sha256: str | None
    status: FileStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
