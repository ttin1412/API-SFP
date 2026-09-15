"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.auth.repository import AuthRepository, InMemoryAuthRepository
from app.auth.service import AuthService
from app.config.settings import get_settings


def create_app(auth_repository: AuthRepository | None = None) -> FastAPI:
    """Create and configure the API application."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    application.state.auth_service = AuthService(
        auth_repository or InMemoryAuthRepository(), settings
    )
    application.include_router(auth_router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report whether the API process is available."""
        return {"status": "ok", "service": "api-sfp"}

    return application


app = create_app()
