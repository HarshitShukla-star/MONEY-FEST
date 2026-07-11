"""Immutable, platform-neutral metadata domain values."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from content_pipeline.domain.metadata.exceptions import MetadataValidationError
from content_pipeline.domain.metadata.utils import FrozenJsonValue, freeze_json_value
from content_pipeline.domain.metadata.validation import (
    normalize_category,
    normalize_hashtags,
    normalize_language,
    normalize_path,
    normalize_tags,
    require_identifier,
    validate_title,
)


class Visibility(StrEnum):
    """Audience visibility independent of a delivery platform."""

    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class MetadataStatus(StrEnum):
    """Lifecycle state of a metadata version."""

    DRAFT = "draft"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class PlatformMetadata:
    """A data-driven extension payload for one delivery platform."""

    platform: str
    fields: Mapping[str, FrozenJsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_platform = require_identifier(self.platform, "Platform").lower()
        if not normalized_platform.replace("_", "").isalnum():
            raise MetadataValidationError("Platform must be a non-empty identifier")
        frozen_fields = freeze_json_value(self.fields, "Platform metadata")
        if not isinstance(frozen_fields, Mapping):
            raise MetadataValidationError("Platform metadata fields must be an object")
        object.__setattr__(self, "platform", normalized_platform)
        object.__setattr__(self, "fields", frozen_fields)


@dataclass(frozen=True, slots=True)
class Metadata:
    """The canonical metadata contract shared by content pipeline modules."""

    title: str
    description: str
    language: str
    category: str
    visibility: Visibility
    video_path: Path
    project_id: str
    channel_id: str
    hashtags: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    thumbnail_path: Path | None = None
    scheduled_publish_at: datetime | None = None
    platform_metadata: tuple[PlatformMetadata, ...] = ()
    custom_fields: Mapping[str, FrozenJsonValue] = field(default_factory=dict)
    version: int = 1
    status: MetadataStatus = MetadataStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.description, str):
            raise MetadataValidationError("Description must be a string")
        if not isinstance(self.visibility, Visibility):
            raise MetadataValidationError(
                "Visibility must be a supported Visibility value"
            )
        if not isinstance(self.status, MetadataStatus):
            raise MetadataValidationError(
                "Status must be a supported MetadataStatus value"
            )
        if (
            isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version < 1
        ):
            raise MetadataValidationError("Version must be a positive integer")
        if not isinstance(self.platform_metadata, tuple) or not all(
            isinstance(item, PlatformMetadata) for item in self.platform_metadata
        ):
            raise MetadataValidationError(
                "Platform metadata must be a tuple of PlatformMetadata values"
            )
        platforms = tuple(item.platform for item in self.platform_metadata)
        if len(set(platforms)) != len(platforms):
            raise MetadataValidationError("Platform metadata entries must be unique")
        created_at = _normalize_datetime(self.created_at, "Created time")
        updated_at = _normalize_datetime(self.updated_at, "Updated time")
        if updated_at < created_at:
            raise MetadataValidationError(
                "Updated time must not be earlier than created time"
            )
        scheduled_publish_at = (
            None
            if self.scheduled_publish_at is None
            else _normalize_datetime(
                self.scheduled_publish_at, "Scheduled publish time"
            )
        )
        if self.status is MetadataStatus.SCHEDULED and scheduled_publish_at is None:
            raise MetadataValidationError(
                "Scheduled publish time is required when status is scheduled"
            )
        custom_fields = freeze_json_value(self.custom_fields, "Custom fields")
        if not isinstance(custom_fields, Mapping):
            raise MetadataValidationError("Custom fields must be an object")
        object.__setattr__(self, "title", validate_title(self.title))
        object.__setattr__(self, "language", normalize_language(self.language))
        object.__setattr__(self, "category", normalize_category(self.category))
        object.__setattr__(
            self, "video_path", normalize_path(self.video_path, "Video path")
        )
        object.__setattr__(
            self, "project_id", require_identifier(self.project_id, "Project id")
        )
        object.__setattr__(
            self, "channel_id", require_identifier(self.channel_id, "Channel id")
        )
        object.__setattr__(self, "hashtags", normalize_hashtags(self.hashtags))
        object.__setattr__(self, "tags", normalize_tags(self.tags))
        object.__setattr__(
            self,
            "thumbnail_path",
            None
            if self.thumbnail_path is None
            else normalize_path(self.thumbnail_path, "Thumbnail path"),
        )
        object.__setattr__(self, "custom_fields", custom_fields)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "scheduled_publish_at", scheduled_publish_at)

    def platform(self, name: str) -> PlatformMetadata | None:
        """Return metadata for a platform, if this version supplies an extension."""
        normalized = require_identifier(name, "Platform").lower()
        return next(
            (item for item in self.platform_metadata if item.platform == normalized),
            None,
        )

    def next_version(self, *, updated_at: datetime | None = None) -> "Metadata":
        """Create the next immutable version without mutating this historical value."""
        return replace(
            self,
            version=self.version + 1,
            updated_at=datetime.now(UTC) if updated_at is None else updated_at,
        )


def _normalize_datetime(value: datetime, field_name: str) -> datetime:
    """Return a UTC timestamp after enforcing timezone awareness."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise MetadataValidationError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
