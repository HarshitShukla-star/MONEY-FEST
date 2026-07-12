"""Immutable, provider-neutral values for transcript-driven clip cutting."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from content_pipeline.domain.clips.exceptions import ClipValidationError
from content_pipeline.domain.clips.validation import (
    normalize_reason,
    normalize_score,
    normalize_time_range,
    normalize_title,
    require_text,
)


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """A single timed span of transcribed speech."""

    start_seconds: float
    end_seconds: float
    text: str

    def __post_init__(self) -> None:
        start, end = normalize_time_range(self.start_seconds, self.end_seconds)
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "text", require_text(self.text, "Segment text"))

    @property
    def duration_seconds(self) -> float:
        """Return the segment's duration in seconds."""
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True, slots=True)
class Transcript:
    """An immutable, time-ordered transcript of a single source video."""

    segments: tuple[TranscriptSegment, ...]
    language: str
    duration_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.segments, tuple) or not all(
            isinstance(item, TranscriptSegment) for item in self.segments
        ):
            raise ClipValidationError(
                "Segments must be a tuple of TranscriptSegment values"
            )
        object.__setattr__(self, "language", require_text(self.language, "Language"))
        duration = self.duration_seconds
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or duration <= 0
        ):
            raise ClipValidationError("Duration must be a positive number")
        object.__setattr__(self, "duration_seconds", float(duration))
        ordered = tuple(
            sorted(self.segments, key=lambda item: item.start_seconds)
        )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.start_seconds < previous.end_seconds:
                raise ClipValidationError("Transcript segments must not overlap")
        if ordered and ordered[-1].end_seconds > self.duration_seconds:
            raise ClipValidationError(
                "Transcript segments must not extend beyond the source duration"
            )
        object.__setattr__(self, "segments", ordered)

    def text_between(self, start_seconds: float, end_seconds: float) -> str:
        """Join the text of every segment that overlaps a time range."""
        start, end = normalize_time_range(start_seconds, end_seconds)
        matched = (
            segment.text
            for segment in self.segments
            if segment.start_seconds < end and segment.end_seconds > start
        )
        return " ".join(matched)


@dataclass(frozen=True, slots=True)
class ClipCandidateRequest:
    """Bounds and hints used when asking a selector for candidate clips."""

    maximum_clips: int
    minimum_duration_seconds: float
    maximum_duration_seconds: float
    topic_hint: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.maximum_clips, bool) or not isinstance(
            self.maximum_clips, int
        ) or self.maximum_clips < 1:
            raise ClipValidationError("Maximum clips must be a positive integer")
        minimum, maximum = normalize_time_range(
            self.minimum_duration_seconds, self.maximum_duration_seconds
        )
        object.__setattr__(self, "minimum_duration_seconds", minimum)
        object.__setattr__(self, "maximum_duration_seconds", maximum)
        object.__setattr__(
            self,
            "topic_hint",
            None
            if self.topic_hint is None
            else require_text(self.topic_hint, "Topic hint"),
        )


@dataclass(frozen=True, slots=True)
class ClipSelection:
    """A single candidate clip chosen from a transcript, not yet cut."""

    start_seconds: float
    end_seconds: float
    title: str
    reason: str
    score: float

    def __post_init__(self) -> None:
        start, end = normalize_time_range(self.start_seconds, self.end_seconds)
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "title", normalize_title(self.title))
        object.__setattr__(self, "reason", normalize_reason(self.reason))
        object.__setattr__(self, "score", normalize_score(self.score))

    @property
    def duration_seconds(self) -> float:
        """Return the selection's duration in seconds."""
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True, slots=True)
class ClipPlan:
    """An immutable, ranked set of clip selections from one planning pass."""

    selections: tuple[ClipSelection, ...]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.selections, tuple) or not all(
            isinstance(item, ClipSelection) for item in self.selections
        ):
            raise ClipValidationError(
                "Selections must be a tuple of ClipSelection values"
            )
        generated_at = self.generated_at
        if not isinstance(generated_at, datetime) or generated_at.tzinfo is None:
            raise ClipValidationError("Generated time must be timezone-aware")
        ranked = tuple(
            sorted(self.selections, key=lambda item: item.score, reverse=True)
        )
        object.__setattr__(self, "selections", ranked)
        object.__setattr__(self, "generated_at", generated_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class CutRequest:
    """A request to materialize one selection from a local source video."""

    source_video: Path
    selection: ClipSelection
    output_video: Path

    def __post_init__(self) -> None:
        if not isinstance(self.source_video, Path) or self.source_video == Path("."):
            raise ClipValidationError("Source video must be a non-empty file path")
        if not isinstance(self.selection, ClipSelection):
            raise ClipValidationError("Selection must be a ClipSelection")
        if not isinstance(self.output_video, Path) or self.output_video == Path("."):
            raise ClipValidationError("Output video must be a non-empty file path")
        if self.output_video == self.source_video:
            raise ClipValidationError("Output video must differ from the source video")


@dataclass(frozen=True, slots=True)
class CutResult:
    """The normalized outcome of cutting one clip from a source video."""

    output_video: Path
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.output_video, Path) or self.output_video == Path("."):
            raise ClipValidationError("Output video must be a non-empty file path")
        start, end = normalize_time_range(self.start_seconds, self.end_seconds)
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)

    @property
    def duration_seconds(self) -> float:
        """Return the produced clip's duration in seconds."""
        return self.end_seconds - self.start_seconds
