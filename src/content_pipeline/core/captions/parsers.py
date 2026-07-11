"""Provider-neutral response parser contracts and built-in format parsers."""

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Protocol, cast

from content_pipeline.domain.captions import (
    CaptionParseError,
    CaptionRequest,
    CaptionResponse,
    CaptionTask,
    ProviderResponse,
)
from content_pipeline.domain.models.json import FrozenJsonValue


class ResponseParser(Protocol):
    """Port that converts a raw provider response into a normalized result."""

    def parse(
        self, request: CaptionRequest, response: ProviderResponse
    ) -> CaptionResponse:
        """Parse one raw provider response."""


class AbstractResponseParser(ABC):
    """Optional base class for future response formats."""

    @abstractmethod
    def parse(
        self, request: CaptionRequest, response: ProviderResponse
    ) -> CaptionResponse:
        """Parse one raw provider response."""


class PlainTextResponseParser(AbstractResponseParser):
    """Parse plain text responses, including simple hashtag lists."""

    def parse(
        self, request: CaptionRequest, response: ProviderResponse
    ) -> CaptionResponse:
        """Convert text into a result; final constraints belong to CaptionValidator."""
        if not isinstance(response.content, str):
            raise CaptionParseError("Plain-text parser requires text response content")
        if request.prompt.task is CaptionTask.HASHTAGS:
            hashtags = tuple(
                item.strip()
                for item in response.content.replace(",", " ").split()
                if item.strip()
            )
            return CaptionResponse(task=request.prompt.task, hashtags=hashtags)
        return CaptionResponse(task=request.prompt.task, text=response.content)


class JsonResponseParser(AbstractResponseParser):
    """Parse a JSON object encoded as a provider text response."""

    def parse(
        self, request: CaptionRequest, response: ProviderResponse
    ) -> CaptionResponse:
        """Decode text JSON before delegating to the structured parser."""
        if not isinstance(response.content, str):
            raise CaptionParseError("JSON parser requires text response content")
        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise CaptionParseError("Provider returned malformed JSON") from exc
        return _parse_object(request, payload)


class StructuredResponseParser(AbstractResponseParser):
    """Parse an already-structured provider response object."""

    def parse(
        self, request: CaptionRequest, response: ProviderResponse
    ) -> CaptionResponse:
        """Normalize a mapping returned directly by an adapter."""
        if not isinstance(response.content, Mapping):
            raise CaptionParseError(
                "Structured parser requires object response content"
            )
        return _parse_object(request, response.content)


def _parse_object(request: CaptionRequest, payload: object) -> CaptionResponse:
    """Validate the stable structured response shape."""
    if not isinstance(payload, Mapping):
        raise CaptionParseError("Structured response must be an object")
    text = payload.get("text", "")
    hashtags = payload.get("hashtags", [])
    fields = payload.get("fields", {})
    if not isinstance(text, str):
        raise CaptionParseError("Structured response field 'text' must be a string")
    if not isinstance(hashtags, list) or not all(
        isinstance(item, str) for item in hashtags
    ):
        raise CaptionParseError(
            "Structured response field 'hashtags' must be an array of strings"
        )
    if not isinstance(fields, Mapping) or not all(
        isinstance(key, str) for key in fields
    ):
        raise CaptionParseError("Structured response field 'fields' must be an object")
    return CaptionResponse(
        task=request.prompt.task,
        text=text,
        hashtags=tuple(hashtags),
        fields=cast(Mapping[str, FrozenJsonValue], fields),
    )
