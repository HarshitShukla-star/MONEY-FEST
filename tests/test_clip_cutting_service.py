"""Tests for transcript-driven clip cutting orchestration."""

from pathlib import Path

import pytest

from content_pipeline.core.clips import ClipCuttingService
from content_pipeline.domain.clips import (
    ClipCandidateRequest,
    ClipPlan,
    ClipSelection,
    ClipSelectionError,
    ClipValidationError,
    CutRequest,
    CutResult,
    Transcript,
    TranscriptSegment,
)


class StubTranscriptionProvider:
    def __init__(self, transcript: Transcript) -> None:
        self._transcript = transcript
        self.calls: list[Path] = []

    def transcribe(self, source_video: Path) -> Transcript:
        self.calls.append(source_video)
        return self._transcript


class StubSegmentSelector:
    def __init__(self, plan: ClipPlan) -> None:
        self._plan = plan
        self.calls: list[Transcript] = []

    def select(self, transcript: Transcript, request: ClipCandidateRequest) -> ClipPlan:
        self.calls.append(transcript)
        return self._plan


class StubCutter:
    def __init__(self) -> None:
        self.requests: list[CutRequest] = []

    def cut(self, request: CutRequest) -> CutResult:
        self.requests.append(request)
        return CutResult(
            output_video=request.output_video,
            start_seconds=request.selection.start_seconds,
            end_seconds=request.selection.end_seconds,
        )


def _transcript() -> Transcript:
    return Transcript(
        segments=(TranscriptSegment(start_seconds=0, end_seconds=10, text="hi"),),
        language="en",
        duration_seconds=10,
    )


def _plan(count: int = 2) -> ClipPlan:
    selections = tuple(
        ClipSelection(
            start_seconds=i, end_seconds=i + 2, title=f"t{i}", reason="r", score=0.5
        )
        for i in range(count)
    )
    return ClipPlan(selections=selections)


def _request() -> ClipCandidateRequest:
    return ClipCandidateRequest(
        maximum_clips=2, minimum_duration_seconds=1, maximum_duration_seconds=5
    )


@pytest.fixture
def video(tmp_path: Path) -> Path:
    path = tmp_path / "source.mp4"
    path.touch()
    return path


def test_plan_transcribes_and_selects_candidates(video: Path) -> None:
    transcript = _transcript()
    plan = _plan()
    transcription = StubTranscriptionProvider(transcript)
    selector = StubSegmentSelector(plan)
    service = ClipCuttingService(transcription, selector, StubCutter())

    result = service.plan(video, _request())

    assert result is plan
    assert transcription.calls == [video.resolve()]
    assert selector.calls == [transcript]


def test_plan_with_transcript_returns_both_values_from_one_transcription(
    video: Path,
) -> None:
    transcript = _transcript()
    plan = _plan()
    transcription = StubTranscriptionProvider(transcript)
    selector = StubSegmentSelector(plan)
    service = ClipCuttingService(transcription, selector, StubCutter())

    returned_transcript, result = service.plan_with_transcript(video, _request())

    assert returned_transcript is transcript
    assert result is plan
    assert transcription.calls == [video.resolve()]


def test_plan_rejects_empty_selection_plans(video: Path) -> None:
    service = ClipCuttingService(
        StubTranscriptionProvider(_transcript()),
        StubSegmentSelector(_plan(0)),
        StubCutter(),
    )

    with pytest.raises(ClipSelectionError, match="No clip selections"):
        service.plan(video, _request())


def test_cut_all_materializes_every_selection(video: Path, tmp_path: Path) -> None:
    cutter = StubCutter()
    service = ClipCuttingService(
        StubTranscriptionProvider(_transcript()), StubSegmentSelector(_plan()), cutter
    )
    plan = _plan()

    results = service.cut_all(video, plan, tmp_path)

    assert len(results) == 2
    assert len(cutter.requests) == 2
    assert cutter.requests[0].output_video.name == "source_clip_01.mp4"
    assert cutter.requests[1].output_video.name == "source_clip_02.mp4"


def test_cut_all_rejects_a_missing_output_directory(
    video: Path, tmp_path: Path
) -> None:
    service = ClipCuttingService(
        StubTranscriptionProvider(_transcript()),
        StubSegmentSelector(_plan()),
        StubCutter(),
    )

    with pytest.raises(ClipValidationError, match="Output directory"):
        service.cut_all(video, _plan(), tmp_path / "missing")
