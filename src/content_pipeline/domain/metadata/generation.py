"""Provider-neutral inputs and results for AI-assisted metadata generation."""

from dataclasses import dataclass

from content_pipeline.domain.metadata.exceptions import MetadataValidationError
from content_pipeline.domain.metadata.validation import (
    normalize_hashtags,
    normalize_language,
    require_identifier,
    validate_title,
)


@dataclass(frozen=True, slots=True)
class MetadataGenerationRequest:
    """AI-only inputs used to derive publishable text from a transcript."""

    transcript: str
    language: str | None = None
    tone: str | None = None
    target_platform: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transcript",
            require_identifier(self.transcript, "Transcript"),
        )
        object.__setattr__(
            self,
            "language",
            None if self.language is None else normalize_language(self.language),
        )
        object.__setattr__(self, "tone", _optional_text(self.tone, "Tone"))
        object.__setattr__(
            self,
            "target_platform",
            _optional_platform(self.target_platform),
        )


@dataclass(frozen=True, slots=True)
class MetadataGenerationResult:
    """Generated text that a later business layer can merge into ``Metadata``."""

    title: str
    description: str
    hashtags: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", validate_title(self.title))
        object.__setattr__(
            self,
            "description",
            require_identifier(self.description, "Description"),
        )
        object.__setattr__(self, "hashtags", normalize_hashtags(self.hashtags))


def _optional_text(value: str | None, field_name: str) -> str | None:
    """Normalize an optional descriptive input."""
    if value is None:
        return None
    return require_identifier(value, field_name)


def _optional_platform(value: str | None) -> str | None:
    """Normalize an optional platform identifier without selecting a channel."""
    if value is None:
        return None
    normalized = require_identifier(value, "Target platform").lower()
    if not normalized.replace("_", "").isalnum():
        raise MetadataValidationError("Target platform must be a non-empty identifier")
    return normalized
