"""Validated configuration loaded from the environment."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from content_pipeline.exceptions import ConfigurationError


class Environment(StrEnum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """Typed runtime settings. Values are sourced only from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = Field(default="content-pipeline", min_length=1)
    app_env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    log_format: str = Field(default="json", pattern="^(json|text)$")
    app_secret_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(default="gemini-2.5-flash-lite", min_length=1)
    local_output_dir: Path = Field(default=Path("output"))
    youtube_oauth_client_secrets_path: Path | None = None
    youtube_oauth_token_path: Path | None = None

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """Enforce settings that must not be omitted in production."""
        if self.app_env is Environment.PRODUCTION and (
            self.app_secret_key is None
            or not self.app_secret_key.get_secret_value().strip()
        ):
            raise ValueError("APP_SECRET_KEY is required when APP_ENV=production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, validated settings instance.

    Raises:
        ConfigurationError: If environment values cannot be validated.
    """
    try:
        return Settings()
    except ValueError as exc:
        raise ConfigurationError("Invalid application configuration") from exc
