"""Expected failures raised by the clip-cutting abstraction."""

from content_pipeline.exceptions import ApplicationError, ProviderError, ValidationError


class ClipError(ApplicationError):
    """Base exception for clip-cutting operations."""


class ClipValidationError(ValidationError):
    """Raised when a transcript, selection, or clip request is invalid."""


class ClipSelectionError(ClipError):
    """Raised when a segment selector returns an unusable plan."""


class ClipProviderError(ProviderError):
    """Raised by adapters after translating a transcription or cutting failure."""
