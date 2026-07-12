"""Provider-neutral trend detection services and adapters."""

from content_pipeline.core.trends.provider import AbstractTrendProvider, TrendProvider
from content_pipeline.core.trends.service import TrendScanService
from content_pipeline.core.trends.youtube_provider import YouTubeTrendProvider

__all__ = [
    "AbstractTrendProvider",
    "TrendProvider",
    "TrendScanService",
    "YouTubeTrendProvider",
]
