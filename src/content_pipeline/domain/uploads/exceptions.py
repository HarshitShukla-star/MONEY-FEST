"""Expected failures for the provider-independent upload workflow."""

from content_pipeline.exceptions import UploadError, ValidationError


class UploadValidationError(ValidationError):
    """Raised when an upload request violates an application invariant."""


class UploadProviderError(UploadError):
    """Raised when an injected upload provider cannot complete an upload."""
