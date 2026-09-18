"""File metadata application services."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePath

from app.config.settings import Settings
from app.files.models import FileMetadata, FileStatus
from app.files.repository import FileRepository
from app.storage.base import ObjectStorage

MIME_TYPE_PATTERN = re.compile(r"^[^\s/;]+/[^\s/;]+$")


class FileNotFoundError(Exception):
    """Raised when a file does not exist or is not owned by the caller."""


class InvalidFileMetadataError(Exception):
    """Raised when declared upload metadata violates policy."""


class InvalidUploadEventError(Exception):
    """Raised when a storage event is not a valid quarantine upload."""


class FileService:
    """Create and access file metadata within an owner's security boundary."""

    def __init__(
        self,
        repository: FileRepository,
        storage: ObjectStorage,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings

    def create_upload_url(
        self,
        *,
        owner_id: str,
        filename: str,
        content_type: str,
        size: int,
    ) -> tuple[FileMetadata, str]:
        """Create pending metadata and a direct-to-quarantine upload URL."""
        file = self.create_pending_upload(
            owner_id=owner_id,
            filename=filename,
            content_type=content_type,
            size=size,
        )
        upload_url = self.storage.generate_upload_url(
            storage_key=file.storage_key,
            content_type=file.declared_mime_type,
        )
        return file, upload_url

    def create_pending_upload(
        self,
        *,
        owner_id: str,
        filename: str,
        content_type: str,
        size: int,
    ) -> FileMetadata:
        normalized_filename = filename.strip()
        self._validate_filename(normalized_filename)
        normalized_content_type = content_type.strip().lower()
        if not MIME_TYPE_PATTERN.fullmatch(normalized_content_type):
            raise InvalidFileMetadataError("Invalid content type")
        if size > self.settings.max_file_size:
            raise InvalidFileMetadataError("File exceeds the maximum allowed size")

        extension = PurePath(normalized_filename).suffix.lower()
        if extension not in self.settings.supported_file_extensions:
            raise InvalidFileMetadataError("Unsupported file extension")

        file_id = self.repository.new_file_id()
        now = datetime.now(timezone.utc)
        quarantine_prefix = self.settings.quarantine_prefix.strip("/")
        file = FileMetadata(
            id=file_id,
            owner_id=owner_id,
            original_filename=normalized_filename,
            storage_key=f"{quarantine_prefix}/{owner_id}/{file_id}",
            detected_mime_type=None,
            declared_mime_type=normalized_content_type,
            extension=extension,
            size=size,
            sha256=None,
            status=FileStatus.PENDING_UPLOAD,
            rejection_reason=None,
            created_at=now,
            updated_at=now,
        )
        return self.repository.create(file)

    def list_files(self, owner_id: str) -> list[FileMetadata]:
        return self.repository.list_for_owner(owner_id)

    def get_file(self, file_id: str, owner_id: str) -> FileMetadata:
        file = self.repository.get_for_owner(file_id, owner_id)
        if file is None:
            raise FileNotFoundError
        return file

    def delete_file(self, file_id: str, owner_id: str) -> None:
        if not self.repository.delete_for_owner(file_id, owner_id):
            raise FileNotFoundError

    def handle_upload_finalized(
        self,
        *,
        event_type: str,
        bucket: str,
        storage_key: str,
    ) -> FileMetadata | None:
        """Handle an authenticated Cloud Storage finalized event idempotently."""
        if event_type != "google.cloud.storage.object.v1.finalized":
            raise InvalidUploadEventError("Unsupported Cloud Storage event type")
        if not self.settings.gcs_bucket_name:
            raise InvalidUploadEventError("GCS_BUCKET_NAME must be configured")
        if bucket != self.settings.gcs_bucket_name:
            raise InvalidUploadEventError("Unexpected Cloud Storage bucket")

        quarantine_prefix = self.settings.quarantine_prefix.strip("/")
        object_prefix = f"{quarantine_prefix}/"
        relative_key = storage_key.removeprefix(object_prefix)
        parts = relative_key.split("/")
        if (
            not quarantine_prefix
            or not storage_key.startswith(object_prefix)
            or len(parts) != 2
            or not parts[0]
            or not parts[1]
        ):
            raise InvalidUploadEventError("Invalid quarantine object name")

        file_id = parts[1]
        return self.repository.mark_uploaded(
            file_id,
            storage_key,
            datetime.now(timezone.utc),
        )

    @staticmethod
    def _validate_filename(filename: str) -> None:
        if (
            not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or any(ord(character) < 32 for character in filename)
        ):
            raise InvalidFileMetadataError("Invalid filename")
