"""Validation rules shared by framework-independent domain contracts."""

import re

from content_pipeline.exceptions import ValidationError

MAX_TITLE_LENGTH = 100
_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def validate_title(
    title: str, error_type: type[ValidationError] = ValidationError
) -> str:
    """Return a trimmed title that satisfies the shared title limit."""
    normalized = require_non_empty(title, "Title", error_type)
    if len(normalized) > MAX_TITLE_LENGTH:
        raise error_type(f"Title must not exceed {MAX_TITLE_LENGTH} characters")
    return normalized


def normalize_language(
    language: str, error_type: type[ValidationError] = ValidationError
) -> str:
    """Normalize a compact BCP 47 language tag."""
    normalized = require_non_empty(language, "Language", error_type)
    if not _LANGUAGE_PATTERN.fullmatch(normalized):
        raise error_type("Language must be a BCP 47 tag such as 'en', 'hi', or 'pt-BR'")
    parts = normalized.split("-")
    normalized_parts = [parts[0].lower()]
    for part in parts[1:]:
        normalized_parts.append(
            part.upper() if len(part) == 2 and part.isalpha() else part
        )
    return "-".join(normalized_parts)


def normalize_hashtags(
    hashtags: tuple[str, ...], error_type: type[ValidationError] = ValidationError
) -> tuple[str, ...]:
    """Normalize hashtags and reject case-insensitive duplicates."""
    if not isinstance(hashtags, tuple):
        raise error_type("Hashtags must be a tuple of strings")
    normalized: list[str] = []
    for hashtag in hashtags:
        if not isinstance(hashtag, str):
            raise error_type("Hashtags must contain only strings")
        value = hashtag.strip()
        if not value or value == "#" or any(char.isspace() for char in value):
            raise error_type("Hashtags must be non-empty single tokens")
        normalized.append(value if value.startswith("#") else f"#{value}")
    if len({item.casefold() for item in normalized}) != len(normalized):
        raise error_type("Hashtags must be unique")
    return tuple(normalized)


def require_non_empty(
    value: str, field_name: str, error_type: type[ValidationError] = ValidationError
) -> str:
    """Return a trimmed string or raise the supplied domain validation error."""
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise error_type(f"{field_name} must not be empty")
    return normalized
