"""JSON-backed implementation of the channel repository port."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from content_pipeline.core.channels.exceptions import ChannelPersistenceError
from content_pipeline.core.channels.models import Channel, JsonValue


class JsonChannelRepository:
    """Persist channels in one UTF-8 JSON file using atomic replacement."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, channel_id: str) -> Channel | None:
        """Return the stored channel with the requested id."""
        return next((item for item in self.list_all() if item.id == channel_id), None)

    def save(self, channel: Channel) -> None:
        """Create or replace a channel record."""
        channels = self.list_all()
        replaced = False
        updated: list[Channel] = []
        for existing in channels:
            if existing.id == channel.id:
                updated.append(channel)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(channel)
        self._write(updated)

    def delete(self, channel_id: str) -> bool:
        """Remove a channel record if it exists."""
        channels = self.list_all()
        remaining = [channel for channel in channels if channel.id != channel_id]
        if len(remaining) == len(channels):
            return False
        self._write(remaining)
        return True

    def list_all(self) -> list[Channel]:
        """Load all channels in ascending friendly-name order."""
        if not self._path.exists():
            return []
        try:
            with self._path.open(encoding="utf-8") as file:
                raw_data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ChannelPersistenceError(
                f"Unable to read channel store: {self._path}"
            ) from exc
        if not isinstance(raw_data, list):
            raise ChannelPersistenceError("Channel store must contain a JSON array")
        try:
            channels = [self._deserialize(item) for item in raw_data]
        except (KeyError, TypeError, ValueError) as exc:
            raise ChannelPersistenceError(
                "Channel store contains an invalid record"
            ) from exc
        return sorted(
            channels, key=lambda channel: (channel.name.casefold(), channel.id)
        )

    def _write(self, channels: list[Channel]) -> None:
        """Replace the store atomically after encoding every channel."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        encoded = [self._serialize(channel) for channel in channels]
        temporary_path: str | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self._path.parent, delete=False
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(encoded, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
            os.replace(temporary_path, self._path)
        except OSError as exc:
            raise ChannelPersistenceError(
                f"Unable to write channel store: {self._path}"
            ) from exc
        finally:
            if temporary_path is not None and Path(temporary_path).exists():
                Path(temporary_path).unlink(missing_ok=True)

    @staticmethod
    def _serialize(channel: Channel) -> dict[str, JsonValue]:
        return {
            "id": channel.id,
            "name": channel.name,
            "platform": channel.platform,
            "enabled": channel.enabled,
            "is_default": channel.is_default,
            "credential_reference": channel.credential_reference,
            "metadata": dict(channel.metadata),
            "created_at": channel.created_at.isoformat(),
            "updated_at": channel.updated_at.isoformat(),
            "tags": list(channel.tags),
        }

    @staticmethod
    def _deserialize(data: object) -> Channel:
        if not isinstance(data, dict):
            raise TypeError("Channel record must be an object")
        metadata = data["metadata"]
        tags = data["tags"]
        if (
            not isinstance(metadata, dict)
            or not all(isinstance(key, str) for key in metadata)
            or not isinstance(tags, list)
            or not all(isinstance(tag, str) for tag in tags)
        ):
            raise TypeError("Channel metadata and tags have invalid types")
        channel_id = data["id"]
        name = data["name"]
        platform = data["platform"]
        enabled = data["enabled"]
        is_default = data["is_default"]
        credential_reference = data["credential_reference"]
        if (
            not isinstance(channel_id, str)
            or not isinstance(name, str)
            or not isinstance(platform, str)
            or not isinstance(enabled, bool)
            or not isinstance(is_default, bool)
            or credential_reference is not None
            and not isinstance(credential_reference, str)
        ):
            raise TypeError("Channel record contains invalid field types")
        return Channel(
            id=channel_id,
            name=name,
            platform=platform,
            enabled=enabled,
            is_default=is_default,
            credential_reference=credential_reference,
            metadata=metadata,
            created_at=JsonChannelRepository._parse_datetime(data["created_at"]),
            updated_at=JsonChannelRepository._parse_datetime(data["updated_at"]),
            tags=tuple(tags),
        )

    @staticmethod
    def _parse_datetime(value: object) -> datetime:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            raise ValueError("Channel timestamps must include a timezone")
        return parsed.astimezone(UTC)
