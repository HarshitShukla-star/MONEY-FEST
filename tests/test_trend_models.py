"""Tests for the immutable trend detection domain contract."""

from datetime import UTC, datetime

import pytest

from content_pipeline.domain.trends import (
    TrendCandidate,
    TrendSnapshot,
    TrendSource,
    TrendValidationError,
)


def _candidate(topic: str = "ai automation", score: float = 10.0) -> TrendCandidate:
    return TrendCandidate(topic=topic, source=TrendSource.YOUTUBE, score=score)


def test_candidate_normalizes_topic_whitespace() -> None:
    candidate = _candidate(topic="  ai automation  ")
    assert candidate.topic == "ai automation"


def test_candidate_rejects_empty_topic() -> None:
    with pytest.raises(TrendValidationError):
        _candidate(topic="   ")


def test_candidate_rejects_negative_score() -> None:
    with pytest.raises(TrendValidationError):
        _candidate(score=-1.0)


def test_candidate_rejects_naive_datetime() -> None:
    with pytest.raises(TrendValidationError):
        TrendCandidate(
            topic="ai automation",
            source=TrendSource.YOUTUBE,
            score=1.0,
            observed_at=datetime(2026, 1, 1),  # noqa: DTZ001 - intentional naive value
        )


def test_candidate_normalizes_timezone_to_utc() -> None:
    candidate = TrendCandidate(
        topic="ai automation",
        source=TrendSource.YOUTUBE,
        score=1.0,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert candidate.observed_at.tzinfo is UTC


def test_candidate_rejects_unsupported_source() -> None:
    with pytest.raises(TrendValidationError):
        TrendCandidate(topic="ai automation", source="youtube", score=1.0)  # type: ignore[arg-type]


def test_snapshot_ranks_candidates_by_score_descending() -> None:
    low = _candidate(topic="low", score=1.0)
    high = _candidate(topic="high", score=99.0)
    mid = _candidate(topic="mid", score=50.0)
    snapshot = TrendSnapshot(candidates=(low, high, mid))
    assert [c.topic for c in snapshot.candidates] == ["high", "mid", "low"]


def test_snapshot_top_returns_bounded_slice() -> None:
    snapshot = TrendSnapshot(
        candidates=tuple(_candidate(topic=f"t{i}", score=float(i)) for i in range(5))
    )
    top = snapshot.top(2)
    assert len(top) == 2
    assert top[0].topic == "t4"


def test_snapshot_top_rejects_non_positive_limit() -> None:
    snapshot = TrendSnapshot(candidates=(_candidate(),))
    with pytest.raises(TrendValidationError):
        snapshot.top(0)


def test_snapshot_rejects_non_candidate_entries() -> None:
    with pytest.raises(TrendValidationError):
        TrendSnapshot(candidates=("not a candidate",))  # type: ignore[arg-type]
