"""FastAPI application entry point."""

from __future__ import annotations

from datetime import timedelta

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.events import router as events_router
from app.api.routes.files import router as files_router
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


def create_app(
    auth_repository: AuthRepository | None = None,
    refresh_sessions: RefreshSessionRepository | None = None,
    file_repository: FileRepository | None = None,
    object_storage: ObjectStorage | None = None,
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
    application.state.file_service = FileService(
        file_repository or create_file_repository(settings),
        object_storage or create_object_storage(settings),
        settings,
    )
    application.include_router(auth_router)
    application.include_router(files_router)
    application.include_router(events_router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report whether the API process is available."""
        return {"status": "ok", "service": "api-sfp"}

    return application


app = create_app()
