"""HTTP schemas for job metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.jobs.models import Job, JobStatus, JobType


class JobResponse(BaseModel):
    """Public representation of an owned job."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    file_id: str
    type: JobType
    status: JobStatus
    retry_count: int
    error: Optional[str]  # noqa: UP045
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: Job) -> JobResponse:
        return cls.model_validate(job)
