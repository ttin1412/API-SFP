"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
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


def create_app(
    auth_repository: AuthRepository | None = None,
    refresh_sessions: RefreshSessionRepository | None = None,
) -> FastAPI:
    """Create and configure the API application."""
    settings = get_settings()
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
    application.include_router(auth_router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report whether the API process is available."""
        return {"status": "ok", "service": "api-sfp"}

    return application


app = create_app()
