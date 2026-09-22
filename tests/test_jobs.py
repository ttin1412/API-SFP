"""Tests for idempotent scan-job creation and Cloud Tasks delivery."""

from datetime import datetime, timezone

import pytest
from google.api_core.exceptions import AlreadyExists

from app.files.models import FileMetadata, FileStatus
from app.files.repository import InMemoryFileRepository
from app.jobs.models import Job, JobStatus, JobType
from app.jobs.repository import InMemoryJobRepository
from app.jobs.service import JobService
from app.queue.cloud_tasks import CloudTasksJobQueue


class RecordingQueue:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.calls: list[Job] = []
        self.fail_once = fail_once

    def enqueue(self, job: Job) -> None:
        self.calls.append(job)
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("enqueue response lost")


class FakeCloudTasksClient:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.requests: list[dict[str, object]] = []

    def queue_path(self, project: str, location: str, queue: str) -> str:
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, *, request: dict[str, object]) -> None:
        self.requests.append(request)
        if self.duplicate:
            raise AlreadyExists("task exists")


def make_file_repository() -> InMemoryFileRepository:
    repository = InMemoryFileRepository()
    now = datetime.now(timezone.utc)
    repository.create(
        FileMetadata(
            id="file-123",
            owner_id="owner-123",
            original_filename="photo.jpg",
            storage_key="quarantine/owner-123/file-123",
            detected_mime_type=None,
            declared_mime_type="image/jpeg",
            extension=".jpg",
            size=128,
            sha256=None,
            status=FileStatus.UPLOADED,
            rejection_reason=None,
            created_at=now,
            updated_at=now,
        )
    )
    return repository


def test_dispatch_is_idempotent_and_retries_the_enqueue_gap() -> None:
    repository = InMemoryJobRepository()
    queue = RecordingQueue(fail_once=True)
    service = JobService(repository, make_file_repository(), queue)

    with pytest.raises(RuntimeError, match="response lost"):
        service.dispatch_security_scan("file-123")

    persisted = repository.get("security-scan-file-123")
    retried = service.dispatch_security_scan("file-123")

    assert persisted is not None
    assert retried == persisted
    assert len(queue.calls) == 2
    assert queue.calls[0] == queue.calls[1]


def test_cloud_tasks_queue_uses_named_oidc_authenticated_task() -> None:
    client = FakeCloudTasksClient()
    queue = CloudTasksJobQueue(
        project_id="project-123",
        location="asia-southeast1",
        queue_name="security-scans",
        worker_endpoint="https://worker.example.test/jobs/security-scan",
        service_account_email="task-invoker@example.iam.gserviceaccount.com",
        client_factory=lambda: client,  # type: ignore[arg-type]
    )
    now = datetime.now(timezone.utc)
    job = Job(
        id="security-scan-file-123",
        file_id="file-123",
        type=JobType.SECURITY_SCAN,
        status=JobStatus.QUEUED,
        retry_count=0,
        error=None,
        created_at=now,
        updated_at=now,
    )

    queue.enqueue(job)

    request = client.requests[0]
    task = request["task"]
    assert isinstance(task, dict)
    assert task["name"].endswith("/tasks/security-scan-file-123")
    http_request = task["http_request"]
    assert isinstance(http_request, dict)
    assert http_request["body"] == (
        b'{"job_id":"security-scan-file-123","file_id":"file-123",'
        b'"type":"SECURITY_SCAN"}'
    )
    assert http_request["oidc_token"] == {
        "service_account_email": "task-invoker@example.iam.gserviceaccount.com",
        "audience": "https://worker.example.test/jobs/security-scan",
    }


def test_cloud_tasks_queue_treats_duplicate_task_as_success() -> None:
    client = FakeCloudTasksClient(duplicate=True)
    queue = CloudTasksJobQueue(
        project_id="project-123",
        location="asia-southeast1",
        queue_name="security-scans",
        worker_endpoint="https://worker.example.test/jobs/security-scan",
        client_factory=lambda: client,  # type: ignore[arg-type]
    )
    now = datetime.now(timezone.utc)
    job = Job(
        id="security-scan-file-123",
        file_id="file-123",
        type=JobType.SECURITY_SCAN,
        status=JobStatus.QUEUED,
        retry_count=0,
        error=None,
        created_at=now,
        updated_at=now,
    )

    queue.enqueue(job)

    assert len(client.requests) == 1
