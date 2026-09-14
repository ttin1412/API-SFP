"""Tests for environment-backed settings."""

from app.config.settings import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.max_file_size == 52_428_800
    assert settings.quarantine_prefix == "quarantine/"
    assert settings.trusted_prefix == "trusted/"


def test_settings_read_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MAX_FILE_SIZE", "1024")

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.max_file_size == 1024
