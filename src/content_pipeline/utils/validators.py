"""Small reusable validation functions."""

from collections.abc import Iterable

from content_pipeline.exceptions import ValidationError


def require_non_empty(value: str, field_name: str) -> str:
    """Return a trimmed string or raise when it is blank."""
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field_name} must not be empty")
    return normalized


def require_membership(value: str, allowed: Iterable[str], field_name: str) -> str:
    """Validate that a string belongs to an allowed collection."""
    allowed_values = set(allowed)
    if value not in allowed_values:
        choices = ", ".join(sorted(allowed_values))
        raise ValidationError(f"{field_name} must be one of: {choices}")
    return value
