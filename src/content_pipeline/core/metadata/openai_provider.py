"""OpenAI adapter for the provider-neutral metadata-generation port."""

import json
from collections.abc import Mapping
from typing import cast

from openai import OpenAI

from content_pipeline.config import Settings
from content_pipeline.core.metadata.provider import MetadataProvider
from content_pipeline.domain.metadata import (
    MetadataGenerationRequest,
    MetadataGenerationResult,
)
from content_pipeline.exceptions import ConfigurationError, ProviderError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)

_SYSTEM_INSTRUCTION = (
    "Generate concise social-video metadata from the supplied transcript. "
    "Return a JSON object with exactly these fields: title (string), "
    "description (string), and hashtags (array of strings)."
)


class OpenAIMetadataProvider(MetadataProvider):
    """Translate OpenAI Chat Completions output into metadata generation values."""

    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self._settings = settings
        if client is not None:
            self._client = client
            return
        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise ConfigurationError(
                "OPENAI_API_KEY is required for the OpenAI metadata provider"
            )
        self._client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def generate(self, request: MetadataGenerationRequest) -> MetadataGenerationResult:
        """Generate and validate only title, description, and hashtags."""
        try:
            completion = self._client.chat.completions.create(
                model=self._settings.openai_metadata_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_INSTRUCTION},
                    {"role": "user", "content": _prompt(request)},
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            result = _parse_result(content)
        except ProviderError:
            raise
        except Exception as exc:
            _LOGGER.error("openai_metadata_generation_failed")
            raise ProviderError("OpenAI metadata generation failed") from exc
        _LOGGER.info(
            "metadata_generated",
            extra={"provider": "openai", "model": self._settings.openai_metadata_model},
        )
        return result


def _prompt(request: MetadataGenerationRequest) -> str:
    """Render the neutral request without adding channel or upload context."""
    context = [f"Transcript:\n{request.transcript}"]
    if request.language is not None:
        context.append(f"Language: {request.language}")
    if request.tone is not None:
        context.append(f"Tone: {request.tone}")
    if request.target_platform is not None:
        context.append(f"Target platform: {request.target_platform}")
    return "\n\n".join(context)


def _parse_result(content: str | None) -> MetadataGenerationResult:
    """Convert a structured OpenAI message to the neutral result value."""
    if content is None:
        raise ProviderError("OpenAI returned an empty metadata response")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError("OpenAI returned malformed metadata JSON") from exc
    if not isinstance(payload, Mapping):
        raise ProviderError("OpenAI returned metadata JSON that is not an object")
    title = payload.get("title")
    description = payload.get("description")
    hashtags = payload.get("hashtags")
    if (
        not isinstance(title, str)
        or not isinstance(description, str)
        or not isinstance(hashtags, list)
        or not all(isinstance(hashtag, str) for hashtag in hashtags)
    ):
        raise ProviderError("OpenAI returned invalid metadata fields")
    return MetadataGenerationResult(
        title=title,
        description=description,
        hashtags=cast(tuple[str, ...], tuple(hashtags)),
    )
