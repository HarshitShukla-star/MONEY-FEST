"""Tests for validated environment configuration."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from content_pipeline.config.settings import Settings


@pytest.fixture(autouse=True)
def clear_application_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep configuration tests independent of the developer machine environment."""
    for name in (
        "APP_NAME",
        "APP_ENV",
        "DEBUG",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "APP_SECRET_KEY",
        "OPENAI_API_KEY",
        "OPENAI_METADATA_MODEL",
        "YOUTUBE_OAUTH_CLIENT_SECRETS_PATH",
        "YOUTUBE_OAUTH_TOKEN_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def test_production_requires_secret_key() -> None:
    with pytest.raises(PydanticValidationError, match="APP_SECRET_KEY"):
        Settings(app_env="production")


def test_production_rejects_a_blank_secret_key() -> None:
    with pytest.raises(PydanticValidationError, match="APP_SECRET_KEY"):
        Settings(app_env="production", app_secret_key="   ")


def test_development_uses_safe_defaults() -> None:
    settings = Settings()

    assert settings.app_env == "development"
    assert settings.log_format == "json"
    assert settings.openai_metadata_model == "gpt-5-mini"
