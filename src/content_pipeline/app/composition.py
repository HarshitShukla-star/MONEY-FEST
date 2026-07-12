"""Composition root: wires domain-neutral use cases to concrete adapters.

Nothing in ``core`` or ``domain`` knows about environment variables, OAuth
clients, or which providers are active. This module is the one place that is
allowed to make those choices, per the dependency direction documented in
``docs/architecture.md`` (config/logging/utils/delivery -> core -> domain).
"""

from pathlib import Path

from content_pipeline.app.oauth import (
    build_youtube_client,
    build_youtube_client_with_api_key,
)
from content_pipeline.config import Settings
from content_pipeline.core.channels import ChannelManager, JsonChannelRepository
from content_pipeline.core.clips.cutter import ClipCutter
from content_pipeline.core.clips.openai_selector import OpenAISegmentSelector
from content_pipeline.core.clips.service import ClipCuttingService
from content_pipeline.core.clips.whisper_provider import WhisperTranscriptionProvider
from content_pipeline.core.metadata.openai_provider import OpenAIMetadataProvider
from content_pipeline.core.trends.service import TrendScanService
from content_pipeline.core.trends.youtube_provider import YouTubeTrendProvider
from content_pipeline.core.uploads.service import UploadService
from content_pipeline.core.uploads.youtube_provider import YouTubeUploadProvider
from content_pipeline.exceptions import ConfigurationError

_DEFAULT_CHANNEL_STORE = Path("data/channels.json")


def build_channel_manager(
    settings: Settings, *, store_path: Path | None = None
) -> ChannelManager:
    """Build the channel manager backed by the local JSON channel store."""
    repository = JsonChannelRepository(store_path or _DEFAULT_CHANNEL_STORE)
    return ChannelManager(repository)


def build_trend_service(
    settings: Settings, *, youtube_api_key: str | None = None, region_code: str = "US"
) -> TrendScanService:
    """Build a trend scan service backed by the YouTube trending chart.

    Prefers a plain API key (no user consent required, since the trending
    chart is public data); falls back to the stored OAuth token when no API
    key is supplied.
    """
    client = (
        build_youtube_client_with_api_key(youtube_api_key)
        if youtube_api_key
        else build_youtube_client(settings)
    )
    provider = YouTubeTrendProvider(client, region_code=region_code)
    return TrendScanService((provider,))


def build_clip_cutting_service(settings: Settings) -> ClipCuttingService:
    """Build the clip cutting service from OpenAI Whisper and selection adapters."""
    return ClipCuttingService(
        transcription_provider=WhisperTranscriptionProvider(settings),
        segment_selector=OpenAISegmentSelector(settings),
        cutter=ClipCutter(),
    )


def build_metadata_provider(settings: Settings) -> OpenAIMetadataProvider:
    """Build the OpenAI-backed metadata (title/description/hashtags) provider."""
    return OpenAIMetadataProvider(settings)


def build_upload_service(settings: Settings, channels: ChannelManager) -> UploadService:
    """Build the upload service using an OAuth-authenticated YouTube client."""
    client = build_youtube_client(settings)
    return UploadService(YouTubeUploadProvider(client), channels)


def require_openai_key(settings: Settings) -> None:
    """Fail fast with a clear message when the OpenAI key is missing."""
    key = settings.openai_api_key
    if key is None or not key.get_secret_value().strip():
        raise ConfigurationError("OPENAI_API_KEY must be configured")
