"""Tests for Cloud Storage signed upload URL generation."""

from datetime import timedelta

from app.storage.gcs import GCSStorage


class FakeBlob:
    def __init__(self) -> None:
        self.arguments: dict[str, object] = {}

    def generate_signed_url(self, **kwargs: object) -> str:
        self.arguments = kwargs
        return "https://storage.example.test/signed-upload"


class FakeBucket:
    def __init__(self, blob: FakeBlob) -> None:
        self.created_blob = blob
        self.object_name = ""

    def blob(self, object_name: str) -> FakeBlob:
        self.object_name = object_name
        return self.created_blob


class FakeClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self.created_bucket = bucket
        self.bucket_name = ""

    def bucket(self, bucket_name: str) -> FakeBucket:
        self.bucket_name = bucket_name
        return self.created_bucket


def test_generate_upload_url_is_scoped_to_object_content_type_and_put() -> None:
    blob = FakeBlob()
    bucket = FakeBucket(blob)
    client = FakeClient(bucket)
    adapter = GCSStorage(
        "uploads-bucket",
        client_factory=lambda: client,  # type: ignore[arg-type]
        expiration=timedelta(minutes=15),
    )

    result = adapter.generate_upload_url(
        storage_key="quarantine/user-1/file-1",
        content_type="image/jpeg",
    )

    assert result == "https://storage.example.test/signed-upload"
    assert client.bucket_name == "uploads-bucket"
    assert bucket.object_name == "quarantine/user-1/file-1"
    assert blob.arguments == {
        "version": "v4",
        "expiration": timedelta(minutes=15),
        "method": "PUT",
        "content_type": "image/jpeg",
    }
