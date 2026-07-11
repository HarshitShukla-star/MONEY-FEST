"""Channel management use case and its local persistence adapter."""

from content_pipeline.core.channels.json_repository import JsonChannelRepository
from content_pipeline.core.channels.models import Channel, ChannelUpdate
from content_pipeline.core.channels.platforms import (
    PlatformRegistry,
    default_platform_registry,
)
from content_pipeline.core.channels.repository import ChannelRepository
from content_pipeline.core.channels.service import ChannelManager

__all__ = [
    "Channel",
    "ChannelManager",
    "ChannelRepository",
    "ChannelUpdate",
    "JsonChannelRepository",
    "PlatformRegistry",
    "default_platform_registry",
]
