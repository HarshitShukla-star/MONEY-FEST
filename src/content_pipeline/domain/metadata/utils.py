"""Compatibility re-exports for metadata JSON value helpers."""

from content_pipeline.domain.metadata.exceptions import MetadataValidationError
from content_pipeline.domain.models.json import (
    FrozenJsonValue,
    JsonValue,
    thaw_json_value,
)
from content_pipeline.domain.models.json import (
    freeze_json_value as _freeze_json_value,
)


def freeze_json_value(value: object, field_name: str) -> FrozenJsonValue:
    """Freeze a metadata extension while retaining metadata-specific errors."""
    return _freeze_json_value(value, field_name, MetadataValidationError)


__all__ = ["FrozenJsonValue", "JsonValue", "freeze_json_value", "thaw_json_value"]
