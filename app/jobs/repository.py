"""Job persistence contracts and implementations."""

from __future__ import annotations

from threading import RLock
from typing import Callable, Protocol

from google.cloud import firestore
from google.cloud.firestore_v1 import DocumentSnapshot

from app.jobs.models import Job, JobStatus, JobType


class JobRepository(Protocol):
    """Persistence required by job dispatch and lookup services."""

    def create_if_absent(self, job: Job) -> Job: ...

    def get(self, job_id: str) -> Job | None: ...


class InMemoryJobRepository:
    """Thread-safe repository for tests and ephemeral development."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = RLock()

    def create_if_absent(self, job: Job) -> Job:
        with self._lock:
            existing = self._jobs.get(job.id)
            if existing is not None:
                return existing
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)


class FirestoreJobRepository:
    """Persist jobs with deterministic document IDs for idempotency."""

    JOBS_COLLECTION = "jobs"

    def __init__(self, client_factory: Callable[[], firestore.Client]) -> None:
        self._client_factory = client_factory

    @property
    def client(self) -> firestore.Client:
        return self._client_factory()

    def create_if_absent(self, job: Job) -> Job:
        client = self.client
        document = client.collection(self.JOBS_COLLECTION).document(job.id)
        transaction = client.transaction()

        @firestore.transactional
        def create_in_transaction(
            active_transaction: firestore.Transaction,
        ) -> Job:
            snapshot = document.get(transaction=active_transaction)
            existing = self._from_snapshot(snapshot)
            if existing is not None:
                return existing
            active_transaction.create(document, self._to_document(job))
            return job

        return create_in_transaction(transaction)

    def get(self, job_id: str) -> Job | None:
        snapshot = self.client.collection(self.JOBS_COLLECTION).document(job_id).get()
        return self._from_snapshot(snapshot)

    @staticmethod
    def _to_document(job: Job) -> dict[str, object]:
        return {
            "file_id": job.file_id,
            "type": job.type.value,
            "status": job.status.value,
            "retry_count": job.retry_count,
            "error": job.error,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    @staticmethod
    def _from_snapshot(snapshot: DocumentSnapshot | None) -> Job | None:
        if snapshot is None or not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return Job(
            id=snapshot.id,
            file_id=data["file_id"],
            type=JobType(data["type"]),
            status=JobStatus(data["status"]),
            retry_count=data["retry_count"],
            error=data.get("error"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
