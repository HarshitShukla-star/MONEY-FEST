"""Canonical, immutable clip-cutting contract for the content pipeline."""

from content_pipeline.domain.clips.exceptions import (
    ClipError,
    ClipProviderError,
    ClipSelectionError,
    ClipValidationError,
)
from content_pipeline.domain.clips.models import (
    ClipCandidateRequest,
    ClipPlan,
    ClipSelection,
    CutRequest,
    CutResult,
    Transcript,
    TranscriptSegment,
)

__all__ = [
    "ClipCandidateRequest",
    "ClipError",
    "ClipPlan",
    "ClipProviderError",
    "ClipSelection",
    "ClipSelectionError",
    "ClipValidationError",
    "CutRequest",
    "CutResult",
    "Transcript",
    "TranscriptSegment",
]
