"""Validation policies for the platform-neutral visual-effects contract."""

from math import isfinite

from content_pipeline.domain.effects.exceptions import EffectValidationError
from content_pipeline.domain.models.validation import require_non_empty

MAX_TEXT_LENGTH = 200


def require_text(value: str, field_name: str) -> str:
    """Return a trimmed required string using effects-specific errors."""
    return require_non_empty(value, field_name, EffectValidationError)


def normalize_overlay_text(value: str) -> str:
    """Validate a non-empty, bounded overlay caption."""
    normalized = require_text(value, "Overlay text")
    if len(normalized) > MAX_TEXT_LENGTH:
        raise EffectValidationError(
            f"Overlay text must not exceed {MAX_TEXT_LENGTH} characters"
        )
    return normalized


def normalize_timestamp(value: float, field_name: str) -> float:
    """Validate a finite, non-negative timestamp in seconds."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EffectValidationError(f"{field_name} must be a number")
    if not isfinite(value):
        raise EffectValidationError(f"{field_name} must be finite")
    if value < 0:
        raise EffectValidationError(f"{field_name} must not be negative")
    return float(value)


def normalize_time_range(start: float, end: float) -> tuple[float, float]:
    """Validate that ``start`` precedes ``end`` and return normalized values."""
    normalized_start = normalize_timestamp(start, "Start time")
    normalized_end = normalize_timestamp(end, "End time")
    if normalized_end <= normalized_start:
        raise EffectValidationError("End time must be greater than start time")
    return normalized_start, normalized_end


def normalize_intensity(value: float) -> float:
    """Validate an effect intensity in the inclusive-exclusive range (0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EffectValidationError("Intensity must be a number")
    if not isfinite(value) or value <= 0 or value > 1:
        raise EffectValidationError("Intensity must be a number in the range (0, 1]")
    return float(value)


def normalize_positive_number(value: float, field_name: str) -> float:
    """Validate a finite, strictly positive number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EffectValidationError(f"{field_name} must be a number")
    if not isfinite(value) or value <= 0:
        raise EffectValidationError(f"{field_name} must be a positive number")
    return float(value)


def normalize_font_size(value: int) -> int:
    """Validate a bounded integer font size."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EffectValidationError("Font size must be an integer")
    if not (8 <= value <= 200):
        raise EffectValidationError("Font size must be between 8 and 200")
    return value
