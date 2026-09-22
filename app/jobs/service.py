"""Job creation, dispatch, and owner-scoped lookup services."""

from __future__ import annotations

from datetime import datetime, timezone

from app.files.repository import FileRepository
from app.jobs.models import Job, JobStatus, JobType
from app.jobs.repository import JobRepository
from app.queue.base import JobQueue


class JobNotFoundError(Exception):
    """Raised when a job does not exist or is not owned by the caller."""


class JobService:
    """Create idempotent scan jobs and dispatch them to the worker queue."""

    def __init__(
        self,
        repository: JobRepository,
        file_repository: FileRepository,
        queue: JobQueue,
    ) -> None:
        self.repository = repository
        self.file_repository = file_repository
        self.queue = queue

    def dispatch_security_scan(self, file_id: str) -> Job:
        """Persist and enqueue exactly one logical scan job per file."""
        now = datetime.now(timezone.utc)
        candidate = Job(
            id=self.security_scan_job_id(file_id),
            file_id=file_id,
            type=JobType.SECURITY_SCAN,
            status=JobStatus.QUEUED,
            retry_count=0,
            error=None,
            created_at=now,
            updated_at=now,
        )
        job = self.repository.create_if_absent(candidate)

        # Always retry enqueueing. The queue uses the same deterministic ID and
        # treats an existing task as success, closing the persist/enqueue gap.
        self.queue.enqueue(job)
        return job

    def get_job(self, job_id: str, owner_id: str) -> Job:
        job = self.repository.get(job_id)
        if (
            job is None
            or self.file_repository.get_for_owner(job.file_id, owner_id) is None
        ):
            raise JobNotFoundError
        return job

    @staticmethod
    def security_scan_job_id(file_id: str) -> str:
        return f"security-scan-{file_id}"
