"""Job domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class JobType(str, Enum):
    """Kinds of asynchronous work supported by the platform."""

    SECURITY_SCAN = "SECURITY_SCAN"


class JobStatus(str, Enum):
    """Lifecycle states shared by the API and worker."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Job:
    """Persistent metadata for one asynchronous file-processing job."""

    id: str
    file_id: str
    type: JobType
    status: JobStatus
    retry_count: int
    error: str | None
    created_at: datetime
    updated_at: datetime
