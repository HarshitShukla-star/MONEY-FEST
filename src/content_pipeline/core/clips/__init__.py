"""Provider-neutral, transcript-driven clip-cutting services and adapters."""

from content_pipeline.core.clips.cutter import ClipCutter
from content_pipeline.core.clips.provider import (
    AbstractSegmentSelector,
    AbstractTranscriptionProvider,
    SegmentSelector,
    TranscriptionProvider,
)
from content_pipeline.core.clips.service import ClipCuttingService

__all__ = [
    "AbstractSegmentSelector",
    "AbstractTranscriptionProvider",
    "ClipCuttingService",
    "ClipCutter",
    "SegmentSelector",
    "TranscriptionProvider",
]
