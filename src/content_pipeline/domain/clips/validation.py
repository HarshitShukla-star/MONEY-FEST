"""Validation policies for the platform-neutral clip-cutting contract."""

from math import isfinite

from content_pipeline.domain.clips.exceptions import ClipValidationError
from content_pipeline.domain.models.validation import require_non_empty

MAX_TITLE_LENGTH = 100
MAX_REASON_LENGTH = 500


def require_text(value: str, field_name: str) -> str:
    """Return a trimmed required string using clip-specific errors."""
    return require_non_empty(value, field_name, ClipValidationError)


def normalize_timestamp(value: float, field_name: str) -> float:
    """Validate a finite, non-negative timestamp in seconds."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClipValidationError(f"{field_name} must be a number")
    if not isfinite(value):
        raise ClipValidationError(f"{field_name} must be finite")
    if value < 0:
        raise ClipValidationError(f"{field_name} must not be negative")
    return float(value)


def normalize_time_range(
    start: float, end: float
) -> tuple[float, float]:
    """Validate that ``start`` precedes ``end`` and return normalized values."""
    normalized_start = normalize_timestamp(start, "Start time")
    normalized_end = normalize_timestamp(end, "End time")
    if normalized_end <= normalized_start:
        raise ClipValidationError("End time must be greater than start time")
    return normalized_start, normalized_end


def normalize_score(score: float) -> float:
    """Validate a score in the inclusive range [0, 1]."""
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ClipValidationError("Score must be a number")
    if not isfinite(score) or score < 0 or score > 1:
        raise ClipValidationError("Score must be a number between 0 and 1")
    return float(score)


def normalize_title(title: str) -> str:
    """Validate a non-empty, bounded clip title."""
    normalized = require_text(title, "Title")
    if len(normalized) > MAX_TITLE_LENGTH:
        raise ClipValidationError(
            f"Title must not exceed {MAX_TITLE_LENGTH} characters"
        )
    return normalized


def normalize_reason(reason: str) -> str:
    """Validate a non-empty, bounded selection rationale."""
    normalized = require_text(reason, "Reason")
    if len(normalized) > MAX_REASON_LENGTH:
        raise ClipValidationError(
            f"Reason must not exceed {MAX_REASON_LENGTH} characters"
        )
    return normalized
