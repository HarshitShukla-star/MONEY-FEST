"""Framework-independent values owned by the channel-management use case."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


@dataclass(frozen=True, slots=True)
class _NotProvided:
    """Sentinel used to distinguish an omitted update from an explicit null."""


NOT_PROVIDED = _NotProvided()


@dataclass(frozen=True, slots=True)
class Channel:
    """A platform-neutral publishing destination."""

    id: str
    name: str
    platform: str
    enabled: bool
    is_default: bool
    credential_reference: str | None
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChannelUpdate:
    """An explicit partial update to a channel.

    Set a field to ``None`` only where the field permits it. Omitted fields retain
    their current values; this allows a credential reference to be intentionally
    cleared without ambiguity.
    """

    name: str | _NotProvided = NOT_PROVIDED
    platform: str | _NotProvided = NOT_PROVIDED
    enabled: bool | _NotProvided = NOT_PROVIDED
    credential_reference: str | None | _NotProvided = NOT_PROVIDED
    metadata: dict[str, JsonValue] | _NotProvided = NOT_PROVIDED
    tags: tuple[str, ...] | _NotProvided = NOT_PROVIDED
