"""Object storage contracts used by the application layer."""

from typing import Protocol


class ObjectStorage(Protocol):
    """Generate narrowly scoped URLs for direct object uploads."""

    def generate_upload_url(
        self,
        *,
        storage_key: str,
        content_type: str,
    ) -> str: ...
