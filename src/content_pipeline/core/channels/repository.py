"""Persistence port for channel data."""

from typing import Protocol

from content_pipeline.core.channels.models import Channel


class ChannelRepository(Protocol):
    """Storage contract consumed by :class:`ChannelManager`."""

    def get(self, channel_id: str) -> Channel | None:
        """Return a channel by id, or ``None`` when it is absent."""

    def save(self, channel: Channel) -> None:
        """Create or replace a channel by id."""

    def delete(self, channel_id: str) -> bool:
        """Delete a channel and report whether a record was removed."""

    def list_all(self) -> list[Channel]:
        """Return all channels in a deterministic order."""
