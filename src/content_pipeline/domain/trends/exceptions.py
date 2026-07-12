"""Expected failures raised by the trend detection contract."""

from content_pipeline.exceptions import ApplicationError, ValidationError


class TrendError(ApplicationError):
    """Base exception for trend detection operations."""


class TrendValidationError(ValidationError):
    """Raised when a trend value violates a durable domain invariant."""
