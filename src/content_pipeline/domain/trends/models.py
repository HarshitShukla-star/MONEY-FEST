"""Immutable, platform-neutral trend detection domain values."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from content_pipeline.domain.models.json import FrozenJsonValue, freeze_json_value
from content_pipeline.domain.trends.exceptions import TrendValidationError
from content_pipeline.domain.trends.validation import (
    normalize_score,
    normalize_topic,
    require_identifier,
)


class TrendSource(StrEnum):
    """A platform-neutral origin for a detected trend signal."""

    YOUTUBE = "youtube"
    REDDIT = "reddit"
    GOOGLE_TRENDS = "google_trends"


@dataclass(frozen=True, slots=True)
class TrendCandidate:
    """A single scored trend signal, independent of the source platform."""

    topic: str
    source: TrendSource
    score: float
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    external_id: str | None = None
    details: Mapping[str, FrozenJsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source, TrendSource):
            raise TrendValidationError(
                "Source must be a supported TrendSource value"
            )
        observed_at = self.observed_at
        if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
            raise TrendValidationError("Observed time must be timezone-aware")
        details = freeze_json_value(self.details, "Trend details")
        if not isinstance(details, Mapping):
            raise TrendValidationError("Trend details must be an object")
        object.__setattr__(self, "topic", normalize_topic(self.topic))
        object.__setattr__(self, "score", normalize_score(self.score))
        object.__setattr__(self, "observed_at", observed_at.astimezone(UTC))
        object.__setattr__(
            self,
            "external_id",
            None
            if self.external_id is None
            else require_identifier(self.external_id, "External id"),
        )
        object.__setattr__(self, "details", details)


@dataclass(frozen=True, slots=True)
class TrendSnapshot:
    """An immutable, ranked collection of trend candidates from one scan."""

    candidates: tuple[TrendCandidate, ...]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, tuple) or not all(
            isinstance(item, TrendCandidate) for item in self.candidates
        ):
            raise TrendValidationError(
                "Candidates must be a tuple of TrendCandidate values"
            )
        generated_at = self.generated_at
        if not isinstance(generated_at, datetime) or generated_at.tzinfo is None:
            raise TrendValidationError("Generated time must be timezone-aware")
        ranked = tuple(
            sorted(self.candidates, key=lambda item: item.score, reverse=True)
        )
        object.__setattr__(self, "candidates", ranked)
        object.__setattr__(self, "generated_at", generated_at.astimezone(UTC))

    def top(self, limit: int) -> tuple[TrendCandidate, ...]:
        """Return the highest-scored candidates, bounded by ``limit``."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise TrendValidationError("Limit must be a positive integer")
        return self.candidates[:limit]
