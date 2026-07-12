"""Validation policies for the platform-neutral trend contract."""

from content_pipeline.domain.models.validation import require_non_empty
from content_pipeline.domain.trends.exceptions import TrendValidationError

MAX_TOPIC_LENGTH = 200


def require_identifier(value: str, field_name: str) -> str:
    """Return a trimmed required identifier using trend-specific errors."""
    return require_non_empty(value, field_name, TrendValidationError)


def normalize_topic(topic: str) -> str:
    """Validate a non-empty, bounded trend topic label."""
    normalized = require_identifier(topic, "Topic")
    if len(normalized) > MAX_TOPIC_LENGTH:
        raise TrendValidationError(
            f"Topic must not exceed {MAX_TOPIC_LENGTH} characters"
        )
    return normalized


def normalize_score(score: float) -> float:
    """Validate a non-negative trend score."""
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise TrendValidationError("Score must be a number")
    if score < 0:
        raise TrendValidationError("Score must not be negative")
    return float(score)
