"""Validation policies for the platform-neutral metadata contract."""

from collections.abc import Iterable
from pathlib import Path

from content_pipeline.domain.metadata.exceptions import MetadataValidationError
from content_pipeline.domain.models.validation import (
    MAX_TITLE_LENGTH,
    require_non_empty,
)
from content_pipeline.domain.models.validation import (
    normalize_hashtags as _normalize_hashtags,
)
from content_pipeline.domain.models.validation import (
    normalize_language as _normalize_language,
)
from content_pipeline.domain.models.validation import (
    validate_title as _validate_title,
)

MAX_CATEGORY_LENGTH = 100

__all__ = ["MAX_TITLE_LENGTH"]


class CategoryRegistry:
    """An optional application-owned category taxonomy.

    The core contract deliberately has no built-in platform taxonomy. Applications
    that need a closed category set may construct this registry at composition time.
    """

    def __init__(self, categories: Iterable[str]) -> None:
        normalized = {normalize_category(category) for category in categories}
        if not normalized:
            raise MetadataValidationError("Category registry must not be empty")
        self._categories = frozenset(normalized)

    def validate(self, category: str) -> str:
        """Return a registered category or raise a meaningful validation error."""
        normalized = normalize_category(category)
        if normalized not in self._categories:
            choices = ", ".join(sorted(self._categories))
            raise MetadataValidationError(
                f"Category '{normalized}' is not registered. "
                f"Allowed categories: {choices}"
            )
        return normalized

    @property
    def categories(self) -> frozenset[str]:
        """Return the immutable registered category set."""
        return self._categories


def require_identifier(value: str, field_name: str) -> str:
    """Return a trimmed required identifier."""
    return require_non_empty(value, field_name, MetadataValidationError)


def validate_title(title: str) -> str:
    """Validate a title using metadata-specific errors for compatibility."""
    return _validate_title(title, MetadataValidationError)


def normalize_language(language: str) -> str:
    """Normalize a language tag using metadata-specific errors for compatibility."""
    return _normalize_language(language, MetadataValidationError)


def normalize_category(category: str) -> str:
    """Validate a non-empty, bounded category label."""
    normalized = require_identifier(category, "Category")
    if len(normalized) > MAX_CATEGORY_LENGTH:
        raise MetadataValidationError(
            f"Category must not exceed {MAX_CATEGORY_LENGTH} characters"
        )
    return normalized


def normalize_path(path: Path, field_name: str) -> Path:
    """Validate a declared artifact path without requiring the artifact to exist yet."""
    if not isinstance(path, Path) or not str(path).strip() or path == Path("."):
        raise MetadataValidationError(f"{field_name} must be a non-empty file path")
    return path


def normalize_hashtags(hashtags: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize hashtags using metadata-specific errors for compatibility."""
    return _normalize_hashtags(hashtags, MetadataValidationError)


def normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize free-form tags and reject duplicates independently of casing."""
    if not isinstance(tags, tuple):
        raise MetadataValidationError("Tags must be a tuple of strings")
    normalized = tuple(require_identifier(tag, "Tag") for tag in tags)
    if len({item.casefold() for item in normalized}) != len(normalized):
        raise MetadataValidationError("Tags must be unique")
    return normalized
