"""Environment-backed application settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "local-development-secret-change-me"


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
    firestore_database: str = "(default)"
    auth_repository_backend: Literal["firestore", "memory"] = "firestore"
    gcs_bucket_name: str = ""
    quarantine_prefix: str = "quarantine/"
    trusted_prefix: str = "trusted/"
    max_file_size: int = Field(default=52_428_800, gt=0)
    queue_name: str = ""
    worker_endpoint: str = ""

    jwt_secret_key: str = Field(default=DEFAULT_JWT_SECRET, min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "secure-file-processing-api"
    jwt_audience: str = "secure-file-processing-client"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        """Only permit the HMAC algorithm supported by this service."""
        if value != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256")
        return value

    @model_validator(mode="after")
    def reject_development_secret_in_deployments(self) -> Settings:
        """Prevent a known signing secret from being used outside local/test."""
        if self.app_env.lower() not in {"local", "test"}:
            if self.jwt_secret_key == DEFAULT_JWT_SECRET:
                raise ValueError("JWT_SECRET_KEY must be changed for this APP_ENV")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""
    return Settings()
