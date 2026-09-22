"""Job queue contract and in-memory adapter."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from app.jobs.models import Job


class JobQueue(Protocol):
    """Queue a job for delivery to the worker."""

    def enqueue(self, job: Job) -> None: ...


class InMemoryJobQueue:
    """Idempotent queue used by tests and ephemeral development."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = RLock()

    def enqueue(self, job: Job) -> None:
        with self._lock:
            self._jobs.setdefault(job.id, job)

    @property
    def jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())
