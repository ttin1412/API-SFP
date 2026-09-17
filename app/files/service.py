"""File metadata application services."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePath

from app.config.settings import Settings
from app.files.models import FileMetadata, FileStatus
from app.files.repository import FileRepository

MIME_TYPE_PATTERN = re.compile(r"^[^\s/;]+/[^\s/;]+$")


class FileNotFoundError(Exception):
    """Raised when a file does not exist or is not owned by the caller."""


class InvalidFileMetadataError(Exception):
    """Raised when declared upload metadata violates policy."""


class FileService:
    """Create and access file metadata within an owner's security boundary."""

    def __init__(self, repository: FileRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

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
