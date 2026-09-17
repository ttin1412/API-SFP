"""Tests for environment-backed settings."""

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.max_file_size == 52_428_800
    assert settings.quarantine_prefix == "quarantine/"
    assert settings.signed_upload_url_expire_minutes == 15
    assert settings.trusted_prefix == "trusted/"
    assert settings.auth_repository_backend == "firestore"
    assert settings.firestore_database == "(default)"


def test_settings_read_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MAX_FILE_SIZE", "1024")

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.max_file_size == 1024


def test_settings_reject_short_jwt_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret_key="too-short")


def test_settings_reject_development_secret_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production")
