"""Canonical, immutable trend detection contract for the content pipeline."""

from content_pipeline.domain.trends.exceptions import TrendError, TrendValidationError
from content_pipeline.domain.trends.models import (
    TrendCandidate,
    TrendSnapshot,
    TrendSource,
)
from content_pipeline.domain.trends.validation import MAX_TOPIC_LENGTH

__all__ = [
    "MAX_TOPIC_LENGTH",
    "TrendCandidate",
    "TrendError",
    "TrendSnapshot",
    "TrendSource",
    "TrendValidationError",
]
