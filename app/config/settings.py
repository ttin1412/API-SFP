"""Environment-backed application settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "environments/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Secure File Processing API"
    app_version: str = "0.1.0"
    app_env: str = "local"
    debug: bool = Field(default=False, validation_alias="API_DEBUG")

    gcp_project_id: str = ""
    gcs_bucket_name: str = ""
    quarantine_prefix: str = "quarantine/"
    trusted_prefix: str = "trusted/"
    max_file_size: int = Field(default=52_428_800, gt=0)
    queue_name: str = ""
    worker_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""
    return Settings()
