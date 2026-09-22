"""Authenticated job metadata endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.dependencies import CurrentUser
from app.jobs.schemas import JobResponse
from app.jobs.service import JobNotFoundError, JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def get_job_service(request: Request) -> JobService:
    return request.app.state.job_service


Service = Annotated[JobService, Depends(get_job_service)]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, user: CurrentUser, service: Service) -> JobResponse:
    """Return a job only when its file belongs to the caller."""
    try:
        return JobResponse.from_job(service.get_job(job_id, user.id))
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
