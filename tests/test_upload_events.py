"""Integration tests for Cloud Storage upload event handling."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth.repository import InMemoryAuthRepository
from app.config.settings import Settings
from app.files.models import FileMetadata, FileStatus
from app.files.repository import InMemoryFileRepository
from app.main import create_app

EVENT_HEADERS = {"ce-type": "google.cloud.storage.object.v1.finalized"}


class FakeObjectStorage:
    def generate_upload_url(self, *, storage_key: str, content_type: str) -> str:
        return "https://storage.example.test/upload"


def make_client() -> tuple[TestClient, InMemoryFileRepository, FileMetadata]:
    repository = InMemoryFileRepository()
    now = datetime.now(timezone.utc)
    file = FileMetadata(
        id="file-123",
        owner_id="user-123",
        original_filename="photo.jpg",
        storage_key="quarantine/user-123/file-123",
        detected_mime_type=None,
        declared_mime_type="image/jpeg",
        extension=".jpg",
        size=128,
        sha256=None,
        status=FileStatus.PENDING_UPLOAD,
        rejection_reason=None,
        created_at=now,
        updated_at=now,
    )
    repository.create(file)
    app = create_app(
        auth_repository=InMemoryAuthRepository(),
        file_repository=repository,
        object_storage=FakeObjectStorage(),
        settings=Settings(
            auth_repository_backend="memory",
            gcs_bucket_name="uploads-test",
        ),
    )
    return TestClient(app), repository, file


def test_finalized_event_marks_pending_file_uploaded_idempotently() -> None:
    client, repository, pending = make_client()
    event = {
        "bucket": "uploads-test",
        "name": pending.storage_key,
        "generation": "123",
    }

    first = client.post("/api/v1/events/storage", headers=EVENT_HEADERS, json=event)
    uploaded = repository.get_for_owner(pending.id, pending.owner_id)
    second = client.post("/api/v1/events/storage", headers=EVENT_HEADERS, json=event)

    assert first.status_code == 204
    assert second.status_code == 204
    assert uploaded is not None
    assert uploaded.status == FileStatus.UPLOADED
    assert uploaded.updated_at > pending.updated_at
    assert repository.get_for_owner(pending.id, pending.owner_id) == uploaded


def test_event_rejects_wrong_bucket_type_and_object_path() -> None:
    client, repository, pending = make_client()

    wrong_bucket = client.post(
        "/api/v1/events/storage",
        headers=EVENT_HEADERS,
        json={"bucket": "other", "name": pending.storage_key},
    )
    wrong_type = client.post(
        "/api/v1/events/storage",
        headers={"ce-type": "google.cloud.storage.object.v1.deleted"},
        json={"bucket": "uploads-test", "name": pending.storage_key},
    )
    wrong_path = client.post(
        "/api/v1/events/storage",
        headers=EVENT_HEADERS,
        json={"bucket": "uploads-test", "name": "trusted/user-123/file-123"},
    )

    assert wrong_bucket.status_code == 400
    assert wrong_type.status_code == 400
    assert wrong_path.status_code == 400
    assert repository.get_for_owner(pending.id, pending.owner_id) == pending


def test_event_does_not_update_a_nonmatching_metadata_key() -> None:
    client, repository, pending = make_client()

    response = client.post(
        "/api/v1/events/storage",
        headers=EVENT_HEADERS,
        json={
            "bucket": "uploads-test",
            "name": "quarantine/attacker/file-123",
        },
    )

    assert response.status_code == 204
    assert repository.get_for_owner(pending.id, pending.owner_id) == pending
