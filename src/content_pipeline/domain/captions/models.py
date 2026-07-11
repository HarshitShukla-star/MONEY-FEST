"""Immutable provider-neutral values used by caption generation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from content_pipeline.domain.captions.exceptions import CaptionValidationError
from content_pipeline.domain.models.json import FrozenJsonValue, freeze_json_value
from content_pipeline.domain.models.validation import (
    normalize_language,
    require_non_empty,
)


class CaptionTask(StrEnum):
    """Kinds of textual content that the framework can request."""

    TITLE = "title"
    CAPTION = "caption"
    DESCRIPTION = "description"
    HASHTAGS = "hashtags"


class ResponseFormat(StrEnum):
    """Provider-neutral representations accepted from a provider adapter."""

    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"


@dataclass(frozen=True, slots=True)
class PromptRequest:
    """Inputs used to build a provider-independent prompt."""

    task: CaptionTask
    subject: str
    language: str
    tone: str | None = None
    style: str | None = None
    target_length: int | None = None
    platform: str | None = None
    custom_variables: Mapping[str, FrozenJsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.task, CaptionTask):
            raise CaptionValidationError("Task must be a supported CaptionTask value")
        if self.target_length is not None and (
            isinstance(self.target_length, bool)
            or not isinstance(self.target_length, int)
            or self.target_length < 1
        ):
            raise CaptionValidationError("Target length must be a positive integer")
        custom_variables = freeze_json_value(
            self.custom_variables, "Custom variables", CaptionValidationError
        )
        if not isinstance(custom_variables, Mapping):
            raise CaptionValidationError("Custom variables must be an object")
        object.__setattr__(
            self,
            "subject",
            require_non_empty(self.subject, "Subject", CaptionValidationError),
        )
        object.__setattr__(
            self,
            "language",
            normalize_language(self.language, CaptionValidationError),
        )
        object.__setattr__(self, "tone", _optional_text(self.tone, "Tone"))
        object.__setattr__(self, "style", _optional_text(self.style, "Style"))
        object.__setattr__(
            self, "platform", _optional_identifier(self.platform, "Platform")
        )
        object.__setattr__(self, "custom_variables", custom_variables)


@dataclass(frozen=True, slots=True)
class CaptionPrompt:
    """A neutral prompt representation that any provider adapter can translate."""

    task: CaptionTask
    system_instruction: str
    user_instruction: str
    language: str
    platform: str | None = None


@dataclass(frozen=True, slots=True)
class CaptionGenerationOptions:
    """Stable generation configuration with no provider-specific settings."""

    response_format: ResponseFormat = ResponseFormat.TEXT
    maximum_characters: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.response_format, ResponseFormat):
            raise CaptionValidationError(
                "Response format must be a supported ResponseFormat value"
            )
        if self.maximum_characters is not None and (
            isinstance(self.maximum_characters, bool)
            or not isinstance(self.maximum_characters, int)
            or self.maximum_characters < 1
        ):
            raise CaptionValidationError(
                "Maximum characters must be a positive integer"
            )


@dataclass(frozen=True, slots=True)
class CaptionRequest:
    """The complete provider request, assembled before any provider is selected."""

    prompt: CaptionPrompt
    options: CaptionGenerationOptions = field(default_factory=CaptionGenerationOptions)

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, CaptionPrompt):
            raise CaptionValidationError("Prompt must be a CaptionPrompt")
        if not isinstance(self.options, CaptionGenerationOptions):
            raise CaptionValidationError("Options must be CaptionGenerationOptions")


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Raw provider output, deliberately free of provider SDK response types."""

    content: str | Mapping[str, FrozenJsonValue]
    provider_name: str
    model_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.content, (str, Mapping)):
            raise CaptionValidationError(
                "Provider response content must be text or an object"
            )
        if isinstance(self.content, Mapping):
            frozen_content = freeze_json_value(
                self.content, "Provider response content", CaptionValidationError
            )
            if not isinstance(frozen_content, Mapping):
                raise CaptionValidationError(
                    "Provider response content must be an object"
                )
            object.__setattr__(self, "content", frozen_content)
        object.__setattr__(
            self,
            "provider_name",
            require_non_empty(
                self.provider_name, "Provider name", CaptionValidationError
            ),
        )
        object.__setattr__(
            self, "model_name", _optional_text(self.model_name, "Model name")
        )


@dataclass(frozen=True, slots=True)
class CaptionResponse:
    """A normalized caption result consumed by business workflows."""

    task: CaptionTask
    text: str = ""
    hashtags: tuple[str, ...] = ()
    fields: Mapping[str, FrozenJsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.task, CaptionTask):
            raise CaptionValidationError("Task must be a supported CaptionTask value")
        if not isinstance(self.text, str):
            raise CaptionValidationError("Caption text must be a string")
        frozen_fields = freeze_json_value(
            self.fields, "Response fields", CaptionValidationError
        )
        if not isinstance(frozen_fields, Mapping):
            raise CaptionValidationError("Response fields must be an object")
        object.__setattr__(self, "fields", frozen_fields)


def _optional_text(value: str | None, field_name: str) -> str | None:
    """Normalize optional descriptive text."""
    if value is None:
        return None
    return require_non_empty(value, field_name, CaptionValidationError)


def _optional_identifier(value: str | None, field_name: str) -> str | None:
    """Normalize an optional platform-like identifier."""
    if value is None:
        return None
    normalized = require_non_empty(value, field_name, CaptionValidationError).lower()
    if not normalized.replace("_", "").isalnum():
        raise CaptionValidationError(f"{field_name} must be a non-empty identifier")
    return normalized
