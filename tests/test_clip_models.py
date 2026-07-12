"""Tests for immutable clip-cutting domain values."""

from datetime import datetime
from pathlib import Path

import pytest

from content_pipeline.domain.clips import (
    ClipCandidateRequest,
    ClipPlan,
    ClipSelection,
    ClipValidationError,
    CutRequest,
    CutResult,
    Transcript,
    TranscriptSegment,
)


def test_transcript_segment_normalizes_and_validates_time_range() -> None:
    segment = TranscriptSegment(start_seconds=1, end_seconds=3, text="  hello  ")

    assert segment.start_seconds == 1.0
    assert segment.end_seconds == 3.0
    assert segment.text == "hello"
    assert segment.duration_seconds == 2.0


def test_transcript_segment_rejects_end_before_start() -> None:
    with pytest.raises(ClipValidationError, match="End time"):
        TranscriptSegment(start_seconds=5, end_seconds=2, text="hi")


def test_transcript_orders_segments_and_computes_text_between() -> None:
    second = TranscriptSegment(start_seconds=5, end_seconds=8, text="second")
    first = TranscriptSegment(start_seconds=0, end_seconds=4, text="first")

    transcript = Transcript(
        segments=(second, first), language="en", duration_seconds=10
    )

    assert transcript.segments == (first, second)
    assert transcript.text_between(0, 4) == "first"
    assert transcript.text_between(0, 10) == "first second"


def test_transcript_rejects_overlapping_segments() -> None:
    overlapping = (
        TranscriptSegment(start_seconds=0, end_seconds=5, text="a"),
        TranscriptSegment(start_seconds=3, end_seconds=8, text="b"),
    )

    with pytest.raises(ClipValidationError, match="overlap"):
        Transcript(segments=overlapping, language="en", duration_seconds=10)


def test_transcript_rejects_segments_beyond_duration() -> None:
    segments = (TranscriptSegment(start_seconds=0, end_seconds=12, text="a"),)

    with pytest.raises(ClipValidationError, match="beyond the source duration"):
        Transcript(segments=segments, language="en", duration_seconds=10)


def test_clip_candidate_request_normalizes_bounds() -> None:
    request = ClipCandidateRequest(
        maximum_clips=3,
        minimum_duration_seconds=15,
        maximum_duration_seconds=60,
        topic_hint="  finance tips  ",
    )

    assert request.maximum_clips == 3
    assert request.topic_hint == "finance tips"


def test_clip_candidate_request_rejects_non_positive_clip_count() -> None:
    with pytest.raises(ClipValidationError, match="Maximum clips"):
        ClipCandidateRequest(
            maximum_clips=0, minimum_duration_seconds=5, maximum_duration_seconds=10
        )


def test_clip_selection_normalizes_fields() -> None:
    selection = ClipSelection(
        start_seconds=1,
        end_seconds=10,
        title="  A great moment  ",
        reason="  strong hook  ",
        score=0.75,
    )

    assert selection.title == "A great moment"
    assert selection.reason == "strong hook"
    assert selection.duration_seconds == 9.0


def test_clip_selection_rejects_out_of_range_score() -> None:
    with pytest.raises(ClipValidationError, match="Score"):
        ClipSelection(
            start_seconds=0, end_seconds=5, title="t", reason="r", score=1.5
        )


def test_clip_plan_ranks_selections_by_score_and_requires_aware_datetime() -> None:
    low = ClipSelection(
        start_seconds=0, end_seconds=5, title="low", reason="r", score=0.2
    )
    high = ClipSelection(
        start_seconds=6, end_seconds=10, title="high", reason="r", score=0.9
    )

    plan = ClipPlan(selections=(low, high))

    assert plan.selections == (high, low)

    with pytest.raises(ClipValidationError, match="timezone-aware"):
        ClipPlan(selections=(low,), generated_at=datetime(2024, 1, 1))


def test_cut_request_rejects_matching_source_and_output() -> None:
    selection = ClipSelection(
        start_seconds=0, end_seconds=5, title="t", reason="r", score=0.5
    )
    video = Path("video.mp4")

    with pytest.raises(ClipValidationError, match="differ"):
        CutRequest(source_video=video, selection=selection, output_video=video)


def test_cut_result_exposes_duration() -> None:
    result = CutResult(
        output_video=Path("out.mp4"), start_seconds=2, end_seconds=7
    )

    assert result.duration_seconds == 5.0
