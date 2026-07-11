"""Storage-independent JSON and dictionary serialization for metadata."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from content_pipeline.domain.metadata.exceptions import MetadataSerializationError
from content_pipeline.domain.metadata.models import (
    Metadata,
    MetadataStatus,
    PlatformMetadata,
    Visibility,
)
from content_pipeline.domain.metadata.utils import (
    FrozenJsonValue,
    JsonValue,
    thaw_json_value,
)

SCHEMA_VERSION = 1


class MetadataSerializer:
    """Translate canonical metadata to and from JSON-compatible values."""

    @staticmethod
    def to_dict(metadata: Metadata) -> dict[str, JsonValue]:
        """Convert a metadata value into a versioned, JSON-compatible dictionary."""
        return {
            "schema_version": SCHEMA_VERSION,
            "title": metadata.title,
            "description": metadata.description,
            "hashtags": list(metadata.hashtags),
            "tags": list(metadata.tags),
            "language": metadata.language,
            "category": metadata.category,
            "visibility": metadata.visibility.value,
            "thumbnail_path": (
                None
                if metadata.thumbnail_path is None
                else str(metadata.thumbnail_path)
            ),
            "video_path": str(metadata.video_path),
            "project_id": metadata.project_id,
            "channel_id": metadata.channel_id,
            "created_at": metadata.created_at.isoformat(),
            "updated_at": metadata.updated_at.isoformat(),
            "scheduled_publish_at": (
                None
                if metadata.scheduled_publish_at is None
                else metadata.scheduled_publish_at.isoformat()
            ),
            "platform_metadata": {
                item.platform: thaw_json_value(item.fields)
                for item in metadata.platform_metadata
            },
            "version": metadata.version,
            "status": metadata.status.value,
            "custom_fields": thaw_json_value(metadata.custom_fields),
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> Metadata:
        """Construct a metadata value from a dictionary produced by :meth:`to_dict`."""
        if not isinstance(data, Mapping):
            raise MetadataSerializationError("Metadata document must be an object")
        schema_version = data.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise MetadataSerializationError(
                f"Unsupported metadata schema version: {schema_version!r}"
            )
        try:
            platform_data = _require_mapping(data, "platform_metadata")
            platform_metadata = tuple(
                PlatformMetadata(
                    platform=platform,
                    fields=cast(
                        Mapping[str, FrozenJsonValue], _require_mapping_value(fields)
                    ),
                )
                for platform, fields in platform_data.items()
                if isinstance(platform, str)
            )
            if len(platform_metadata) != len(platform_data):
                raise TypeError("Platform metadata keys must be strings")
            return Metadata(
                title=_require_string(data, "title"),
                description=_require_string(data, "description"),
                hashtags=_require_string_tuple(data, "hashtags"),
                tags=_require_string_tuple(data, "tags"),
                language=_require_string(data, "language"),
                category=_require_string(data, "category"),
                visibility=Visibility(_require_string(data, "visibility")),
                thumbnail_path=_optional_path(data, "thumbnail_path"),
                video_path=Path(_require_string(data, "video_path")),
                project_id=_require_string(data, "project_id"),
                channel_id=_require_string(data, "channel_id"),
                created_at=_parse_datetime(data, "created_at"),
                updated_at=_parse_datetime(data, "updated_at"),
                scheduled_publish_at=_optional_datetime(data, "scheduled_publish_at"),
                platform_metadata=platform_metadata,
                version=_require_integer(data, "version"),
                status=MetadataStatus(_require_string(data, "status")),
                custom_fields=cast(
                    Mapping[str, FrozenJsonValue],
                    _require_mapping(data, "custom_fields"),
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MetadataSerializationError(
                "Metadata document contains invalid fields"
            ) from exc

    @staticmethod
    def to_json(metadata: Metadata, *, indent: int | None = 2) -> str:
        """Export metadata as UTF-8-safe JSON without performing storage I/O."""
        return json.dumps(
            MetadataSerializer.to_dict(metadata), ensure_ascii=False, indent=indent
        )

    @staticmethod
    def from_json(value: str) -> Metadata:
        """Import metadata from JSON without coupling it to a file store."""
        try:
            data = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise MetadataSerializationError("Metadata JSON is malformed") from exc
        if not isinstance(data, dict):
            raise MetadataSerializationError("Metadata JSON must contain an object")
        return MetadataSerializer.from_dict(data)


def _require_string(data: Mapping[str, object], field_name: str) -> str:
    value = data[field_name]
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    return value


def _require_string_tuple(
    data: Mapping[str, object], field_name: str
) -> tuple[str, ...]:
    value = data[field_name]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field_name} must be an array of strings")
    return tuple(value)


def _require_mapping(
    data: Mapping[str, object], field_name: str
) -> Mapping[str, object]:
    return _require_mapping_value(data[field_name])


def _require_mapping_value(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise TypeError("Value must be an object with string keys")
    return value


def _require_integer(data: Mapping[str, object], field_name: str) -> int:
    value = data[field_name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _optional_path(data: Mapping[str, object], field_name: str) -> Path | None:
    value = data[field_name]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or null")
    return Path(value)


def _parse_datetime(data: Mapping[str, object], field_name: str) -> datetime:
    value = _require_string(data, field_name)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _optional_datetime(data: Mapping[str, object], field_name: str) -> datetime | None:
    value = data[field_name]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a timestamp or null")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)
