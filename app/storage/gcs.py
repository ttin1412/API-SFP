"""Google Cloud Storage signed URL adapter."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Callable

from google.cloud import storage


@lru_cache
def get_storage_client(project_id: str = "") -> storage.Client:
    """Create a cached client using Application Default Credentials."""
    return storage.Client(project=project_id or None)


class GCSStorage:
    """Generate V4 URLs that permit a PUT to one bucket object."""

    def __init__(
        self,
        bucket_name: str,
        *,
        client_factory: Callable[[], storage.Client],
        expiration: timedelta,
    ) -> None:
        self._bucket_name = bucket_name
        self._client_factory = client_factory
        self._expiration = expiration

    def generate_upload_url(
        self,
        *,
        storage_key: str,
        content_type: str,
    ) -> str:
        """Return a short-lived URL restricted to a PUT with this MIME type."""
        if not self._bucket_name:
            raise ValueError("GCS_BUCKET_NAME must be configured")

        blob = self._client_factory().bucket(self._bucket_name).blob(storage_key)
        return blob.generate_signed_url(
            version="v4",
            expiration=self._expiration,
            method="PUT",
            content_type=content_type,
        )
