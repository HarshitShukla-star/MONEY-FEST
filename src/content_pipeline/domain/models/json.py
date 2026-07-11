"""Shared JSON-compatible domain value helpers."""

from collections.abc import Mapping
from math import isfinite
from types import MappingProxyType

from content_pipeline.exceptions import ValidationError

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type FrozenJsonValue = (
    str
    | int
    | float
    | bool
    | None
    | tuple[FrozenJsonValue, ...]
    | Mapping[str, FrozenJsonValue]
)


def freeze_json_value(
    value: object,
    field_name: str,
    error_type: type[ValidationError] = ValidationError,
) -> FrozenJsonValue:
    """Validate a JSON-compatible value and make nested containers immutable."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise error_type(f"{field_name} must not contain NaN or infinity")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenJsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise error_type(f"{field_name} must use non-empty string keys")
            frozen[key] = freeze_json_value(item, f"{field_name}.{key}", error_type)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            freeze_json_value(item, f"{field_name}[]", error_type) for item in value
        )
    raise error_type(f"{field_name} must contain only JSON-compatible values")


def thaw_json_value(value: FrozenJsonValue) -> JsonValue:
    """Return a JSON-ready mutable representation of an immutable JSON value."""
    if isinstance(value, Mapping):
        return {key: thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json_value(item) for item in value]
    return value
