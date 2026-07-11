"""Application service for managing publishing destinations."""

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from content_pipeline.core.channels.exceptions import (
    ChannelNotFoundError,
    ChannelStateError,
    ChannelValidationError,
    DuplicateChannelError,
)
from content_pipeline.core.channels.models import (
    Channel,
    ChannelUpdate,
    JsonValue,
    _NotProvided,
)
from content_pipeline.core.channels.platforms import (
    PlatformRegistry,
    default_platform_registry,
)
from content_pipeline.core.channels.repository import ChannelRepository


class ChannelManager:
    """Owns channel invariants independently of a persistence implementation."""

    def __init__(
        self,
        repository: ChannelRepository,
        platforms: PlatformRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._platforms = platforms or default_platform_registry()
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_channel(
        self,
        name: str,
        platform: str,
        *,
        channel_id: str | None = None,
        enabled: bool = True,
        credential_reference: str | None = None,
        metadata: dict[str, JsonValue] | None = None,
        tags: tuple[str, ...] = (),
    ) -> Channel:
        """Create, validate, and persist a new publishing destination."""
        identifier = channel_id or str(uuid4())
        normalized_name = self._validate_name(name)
        self._validate_identifier(identifier)
        self._validate_enabled(enabled)
        self._ensure_unique(identifier, normalized_name)
        now = self._clock()
        channel = Channel(
            id=identifier,
            name=normalized_name,
            platform=self._platforms.validate(platform),
            enabled=enabled,
            is_default=False,
            credential_reference=self._validate_credential_reference(
                credential_reference
            ),
            metadata=self._validate_metadata(metadata or {}),
            created_at=now,
            updated_at=now,
            tags=self._validate_tags(tags),
        )
        self._repository.save(channel)
        return channel

    def load_channel(self, channel_id: str) -> Channel:
        """Load one channel or raise an explicit not-found error."""
        channel = self._repository.get(channel_id)
        if channel is None:
            raise ChannelNotFoundError(f"Channel not found: {channel_id}")
        return channel

    def save_channel(self, channel: Channel) -> Channel:
        """Validate and persist a complete externally supplied channel value."""
        self._validate_channel(channel, excluding_id=channel.id)
        self._repository.save(channel)
        return channel

    def update_channel(self, channel_id: str, update: ChannelUpdate) -> Channel:
        """Apply a typed partial update and persist the resulting channel."""
        if not isinstance(update, ChannelUpdate):
            raise ChannelValidationError("Update must be a ChannelUpdate")
        current = self.load_channel(channel_id)
        name = (
            current.name
            if isinstance(update.name, _NotProvided)
            else self._validate_name(update.name)
        )
        platform = (
            current.platform
            if isinstance(update.platform, _NotProvided)
            else self._platforms.validate(update.platform)
        )
        enabled = (
            current.enabled
            if isinstance(update.enabled, _NotProvided)
            else self._validate_enabled(update.enabled)
        )
        credential_reference = (
            current.credential_reference
            if isinstance(update.credential_reference, _NotProvided)
            else self._validate_credential_reference(update.credential_reference)
        )
        metadata = (
            current.metadata
            if isinstance(update.metadata, _NotProvided)
            else self._validate_metadata(update.metadata)
        )
        tags = (
            current.tags
            if isinstance(update.tags, _NotProvided)
            else self._validate_tags(update.tags)
        )
        updated = replace(
            current,
            name=name,
            platform=platform,
            enabled=enabled,
            credential_reference=credential_reference,
            metadata=metadata,
            tags=tags,
            updated_at=self._clock(),
        )
        self._validate_channel(updated, excluding_id=current.id)
        self._repository.save(updated)
        return updated

    def delete_channel(self, channel_id: str) -> None:
        """Delete a channel or raise an explicit not-found error."""
        if not self._repository.delete(channel_id):
            raise ChannelNotFoundError(f"Channel not found: {channel_id}")

    def enable_channel(self, channel_id: str) -> Channel:
        """Enable a channel."""
        return self.update_channel(channel_id, ChannelUpdate(enabled=True))

    def disable_channel(self, channel_id: str) -> Channel:
        """Disable a non-default channel."""
        channel = self.load_channel(channel_id)
        if channel.is_default:
            raise ChannelStateError("The default channel must remain enabled")
        return self.update_channel(channel_id, ChannelUpdate(enabled=False))

    def list_channels(self) -> list[Channel]:
        """List all saved channels."""
        return self._repository.list_all()

    def get_default_channel(self) -> Channel | None:
        """Return the default channel, if one has been selected."""
        defaults = [channel for channel in self.list_channels() if channel.is_default]
        if len(defaults) > 1:
            raise ChannelStateError("More than one default channel is configured")
        return defaults[0] if defaults else None

    def set_default_channel(self, channel_id: str) -> Channel:
        """Make an enabled channel the sole default channel."""
        selected = self.load_channel(channel_id)
        if not selected.enabled:
            raise ChannelStateError("A disabled channel cannot be the default")
        for channel in self.list_channels():
            if channel.is_default and channel.id != selected.id:
                self._repository.save(
                    replace(channel, is_default=False, updated_at=self._clock())
                )
        updated = replace(selected, is_default=True, updated_at=self._clock())
        self._repository.save(updated)
        return updated

    def find_by_id(self, channel_id: str) -> Channel | None:
        """Find a channel by id without raising when it is absent."""
        return self._repository.get(channel_id)

    def find_by_platform(self, platform: str) -> list[Channel]:
        """Find channels registered for a platform."""
        normalized = self._platforms.validate(platform)
        return [
            channel
            for channel in self.list_channels()
            if channel.platform == normalized
        ]

    def find_by_name(self, name: str) -> list[Channel]:
        """Find channels whose friendly name contains a case-insensitive query."""
        query = self._validate_name(name).casefold()
        return [
            channel
            for channel in self.list_channels()
            if query in channel.name.casefold()
        ]

    def _ensure_unique(
        self, channel_id: str, name: str, excluding_id: str | None = None
    ) -> None:
        for channel in self.list_channels():
            if channel.id == channel_id and channel.id != excluding_id:
                raise DuplicateChannelError(f"Channel id already exists: {channel_id}")
            if (
                channel.name.casefold() == name.casefold()
                and channel.id != excluding_id
            ):
                raise DuplicateChannelError(f"Channel name already exists: {name}")

    def _validate_channel(
        self, channel: Channel, excluding_id: str | None = None
    ) -> None:
        self._validate_identifier(channel.id)
        self._ensure_unique(channel.id, self._validate_name(channel.name), excluding_id)
        self._platforms.validate(channel.platform)
        self._validate_enabled(channel.enabled)
        self._validate_enabled(channel.is_default)
        self._validate_credential_reference(channel.credential_reference)
        self._validate_metadata(channel.metadata)
        self._validate_tags(channel.tags)
        if channel.is_default and not channel.enabled:
            raise ChannelStateError("The default channel must be enabled")
        if channel.is_default:
            defaults = [
                item
                for item in self.list_channels()
                if item.is_default and item.id != channel.id
            ]
            if defaults:
                raise ChannelStateError("More than one default channel is configured")

    @staticmethod
    def _validate_identifier(channel_id: str) -> None:
        if not isinstance(channel_id, str) or not channel_id.strip():
            raise ChannelValidationError("Channel id must not be empty")

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str):
            raise ChannelValidationError("Channel name must not be empty")
        normalized = name.strip()
        if not normalized:
            raise ChannelValidationError("Channel name must not be empty")
        return normalized

    @staticmethod
    def _validate_credential_reference(reference: str | None) -> str | None:
        if reference is not None and (
            not isinstance(reference, str) or not reference.strip()
        ):
            raise ChannelValidationError("Credential reference must not be blank")
        return reference.strip() if reference is not None else None

    @staticmethod
    def _validate_enabled(value: bool) -> bool:
        if not isinstance(value, bool):
            raise ChannelValidationError("Channel enabled state must be a boolean")
        return value

    @staticmethod
    def _validate_metadata(metadata: object) -> dict[str, JsonValue]:
        if not isinstance(metadata, dict) or not all(
            isinstance(key, str) for key in metadata
        ):
            raise ChannelValidationError("Metadata must be an object with string keys")
        try:
            json.dumps(metadata, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ChannelValidationError("Metadata must be JSON serializable") from exc
        return cast(dict[str, JsonValue], dict(metadata))

    @staticmethod
    def _validate_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
        if not isinstance(tags, tuple) or not all(isinstance(tag, str) for tag in tags):
            raise ChannelValidationError("Channel tags must be a tuple of strings")
        normalized = tuple(tag.strip() for tag in tags)
        if any(not tag for tag in normalized):
            raise ChannelValidationError("Channel tags must not be blank")
        if len({tag.casefold() for tag in normalized}) != len(normalized):
            raise ChannelValidationError("Channel tags must be unique")
        return normalized
