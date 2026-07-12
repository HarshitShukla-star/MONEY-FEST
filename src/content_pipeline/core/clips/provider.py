"""Consumer-owned ports for transcription and clip-selection adapters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from content_pipeline.domain.clips import ClipCandidateRequest, ClipPlan, Transcript


class TranscriptionProvider(Protocol):
    """Produce a provider-neutral transcript for a local source video."""

    def transcribe(self, source_video: Path) -> Transcript:
        """Return a timed transcript for ``source_video``."""


class AbstractTranscriptionProvider(ABC):
    """Optional base class for transcription adapters sharing support code."""

    @abstractmethod
    def transcribe(self, source_video: Path) -> Transcript:
        """Return a timed transcript for ``source_video``."""


class SegmentSelector(Protocol):
    """Choose candidate clip time ranges from a transcript."""

    def select(
        self, transcript: Transcript, request: ClipCandidateRequest
    ) -> ClipPlan:
        """Return a ranked plan of clip selections drawn from ``transcript``."""


class AbstractSegmentSelector(ABC):
    """Optional base class for selector adapters sharing support code."""

    @abstractmethod
    def select(
        self, transcript: Transcript, request: ClipCandidateRequest
    ) -> ClipPlan:
        """Return a ranked plan of clip selections drawn from ``transcript``."""
