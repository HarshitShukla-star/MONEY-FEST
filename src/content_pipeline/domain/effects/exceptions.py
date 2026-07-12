"""Expected failures raised by the visual-effects abstraction."""

from content_pipeline.exceptions import ApplicationError, ProviderError, ValidationError


class EffectError(ApplicationError):
    """Base exception for visual-effects operations."""


class EffectValidationError(ValidationError):
    """Raised when an effect plan or request is invalid."""


class EffectProviderError(ProviderError):
    """Raised by adapters after translating an effects-processing failure."""
