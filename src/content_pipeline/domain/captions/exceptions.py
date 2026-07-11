"""Expected failures raised by the caption abstraction."""

from content_pipeline.exceptions import ApplicationError, ProviderError, ValidationError


class CaptionError(ApplicationError):
    """Base exception for caption operations."""


class CaptionValidationError(ValidationError):
    """Raised when a prompt, request, or parsed caption is invalid."""


class CaptionParseError(CaptionError):
    """Raised when a provider response cannot be interpreted safely."""


class CaptionProviderError(ProviderError):
    """Raised by future adapters after translating a provider failure."""
