"""FastAPI application entry point."""

from fastapi import FastAPI

from app.config.settings import get_settings


def create_app() -> FastAPI:
    """Create and configure the API application."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report whether the API process is available."""
        return {"status": "ok", "service": "api-sfp"}

    return application


app = create_app()
