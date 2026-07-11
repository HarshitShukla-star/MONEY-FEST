"""Expected failures raised by the metadata contract."""

from content_pipeline.exceptions import ApplicationError, ValidationError


class MetadataError(ApplicationError):
    """Base exception for metadata operations."""


class MetadataValidationError(ValidationError):
    """Raised when metadata violates a durable domain invariant."""


class MetadataSerializationError(MetadataError):
    """Raised when metadata cannot be safely encoded or decoded."""
