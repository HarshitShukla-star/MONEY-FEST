"""Tests for the OpenAI metadata-generation adapter without network access."""

from types import SimpleNamespace
from typing import cast

import pytest
from openai import OpenAI

from content_pipeline.config import Settings
from content_pipeline.core.metadata import MetadataProvider, OpenAIMetadataProvider
from content_pipeline.domain.metadata import (
    MetadataGenerationRequest,
    MetadataGenerationResult,
    MetadataValidationError,
)
from content_pipeline.exceptions import ConfigurationError, ProviderError


class RecordingOpenAIClient:
    """Minimal mock of the SDK client used by the adapter."""

    def __init__(self, content: str | None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def _settings(*, model: str = "gpt-5-mini") -> Settings:
    """Construct settings independently of host environment values."""
    return Settings(debug=False, openai_metadata_model=model)


def test_openai_provider_translates_a_mocked_sdk_response() -> None:
    client = RecordingOpenAIClient(
        '{"title": "  Useful tip  ", "description": "Try this workflow.", '
        '"hashtags": ["automation", "#python"]}'
    )
    provider: MetadataProvider = OpenAIMetadataProvider(
        _settings(model="test-model"), cast(OpenAI, client)
    )

    result = provider.generate(
        MetadataGenerationRequest(
            transcript="A transcript about automation.",
            language="pt-br",
            tone="friendly",
            target_platform="YouTube",
        )
    )

    assert result == MetadataGenerationResult(
        title="Useful tip",
        description="Try this workflow.",
        hashtags=("#automation", "#python"),
    )
    assert client.calls[0]["model"] == "test-model"
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    messages = cast(list[dict[str, str]], client.calls[0]["messages"])
    assert "Transcript" in messages[1]["content"]
    assert "Target platform: youtube" in messages[1]["content"]


def test_openai_provider_translates_sdk_and_response_failures() -> None:
    failing_client = RecordingOpenAIClient(None, RuntimeError("SDK error"))
    provider = OpenAIMetadataProvider(_settings(), cast(OpenAI, failing_client))

    with pytest.raises(ProviderError, match="OpenAI metadata generation failed"):
        provider.generate(MetadataGenerationRequest("Transcript"))

    malformed_provider = OpenAIMetadataProvider(
        _settings(), cast(OpenAI, RecordingOpenAIClient("not json"))
    )
    with pytest.raises(ProviderError, match="malformed metadata JSON"):
        malformed_provider.generate(MetadataGenerationRequest("Transcript"))


def test_openai_provider_requires_configured_key_only_when_creating_sdk_client() -> (
    None
):
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        OpenAIMetadataProvider(_settings())


def test_metadata_generation_values_reuse_metadata_validation() -> None:
    with pytest.raises(MetadataValidationError, match="Transcript"):
        MetadataGenerationRequest("  ")
    with pytest.raises(MetadataValidationError, match="BCP 47"):
        MetadataGenerationRequest("Transcript", language="English")
    with pytest.raises(MetadataValidationError, match="unique"):
        MetadataGenerationResult("Title", "Description", ("News", "#news"))
