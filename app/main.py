"""FastAPI application entry point."""

from __future__ import annotations

from datetime import timedelta

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.events import router as events_router
from app.api.routes.files import router as files_router
from app.api.routes.jobs import router as jobs_router
from app.auth.repository import (
    AuthRepository,
    FirestoreAuthRepository,
    InMemoryAuthRepository,
    InMemoryRefreshSessionRepository,
    RefreshSessionRepository,
)
from app.auth.service import AuthService
from app.config.settings import Settings, get_settings
from app.database.firestore import get_firestore_client
from app.files.repository import (
    FileRepository,
    FirestoreFileRepository,
    InMemoryFileRepository,
)
from app.files.service import FileService
from app.jobs.repository import (
    FirestoreJobRepository,
    InMemoryJobRepository,
    JobRepository,
)
from app.jobs.service import JobService
from app.queue.base import InMemoryJobQueue, JobQueue
from app.queue.cloud_tasks import CloudTasksJobQueue
from app.storage.base import ObjectStorage
from app.storage.gcs import GCSStorage, get_storage_client


def create_auth_repository(settings: Settings) -> AuthRepository:
    """Build the configured authentication persistence adapter."""
    if settings.auth_repository_backend == "memory":
        return InMemoryAuthRepository()
    return FirestoreAuthRepository(
        lambda: get_firestore_client(
            settings.gcp_project_id,
            settings.firestore_database,
        )
    )


def create_file_repository(settings: Settings) -> FileRepository:
    """Build the configured file metadata persistence adapter."""
    if settings.auth_repository_backend == "memory":
        return InMemoryFileRepository()
    return FirestoreFileRepository(
        lambda: get_firestore_client(
            settings.gcp_project_id,
            settings.firestore_database,
        )
    )


def create_object_storage(settings: Settings) -> ObjectStorage:
    """Build the Google Cloud Storage adapter used for signed uploads."""
    return GCSStorage(
        settings.gcs_bucket_name,
        client_factory=lambda: get_storage_client(settings.gcp_project_id),
        expiration=timedelta(minutes=settings.signed_upload_url_expire_minutes),
    )


def create_job_repository(settings: Settings) -> JobRepository:
    """Build the job persistence adapter for the selected environment."""
    if settings.auth_repository_backend == "memory":
        return InMemoryJobRepository()
    return FirestoreJobRepository(
        lambda: get_firestore_client(
            settings.gcp_project_id,
            settings.firestore_database,
        )
    )


def create_job_queue(settings: Settings) -> JobQueue:
    """Build the worker queue adapter for the selected environment."""
    if settings.auth_repository_backend == "memory":
        return InMemoryJobQueue()
    return CloudTasksJobQueue(
        project_id=settings.gcp_project_id,
        location=settings.queue_location,
        queue_name=settings.queue_name,
        worker_endpoint=settings.worker_endpoint,
        service_account_email=settings.worker_service_account_email,
        oidc_audience=settings.worker_oidc_audience,
    )


def create_app(
    auth_repository: AuthRepository | None = None,
    refresh_sessions: RefreshSessionRepository | None = None,
    file_repository: FileRepository | None = None,
    object_storage: ObjectStorage | None = None,
    job_repository: JobRepository | None = None,
    job_queue: JobQueue | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create and configure the API application."""
    settings = settings or get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    application.state.auth_service = AuthService(
        auth_repository or create_auth_repository(settings),
        refresh_sessions or InMemoryRefreshSessionRepository(),
        settings,
    )
    active_file_repository = file_repository or create_file_repository(settings)
    application.state.file_service = FileService(
        active_file_repository,
        object_storage or create_object_storage(settings),
        settings,
    )
    application.state.job_service = JobService(
        job_repository or create_job_repository(settings),
        active_file_repository,
        job_queue or create_job_queue(settings),
    )
    application.include_router(auth_router)
    application.include_router(files_router)
    application.include_router(events_router)
    application.include_router(jobs_router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report whether the API process is available."""
        return {"status": "ok", "service": "api-sfp"}

    return application


app = create_app()
