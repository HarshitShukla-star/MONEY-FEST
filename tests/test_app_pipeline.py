"""Behavioural tests for the end-to-end pipeline orchestrator."""

from pathlib import Path
from typing import cast

import pytest

from content_pipeline.app.pipeline import (
    ContentPipeline,
    PipelineRunRequest,
    topic_hint_from_snapshot,
)
from content_pipeline.core.channels import (
    Channel,
    ChannelManager,
    JsonChannelRepository,
)
from content_pipeline.core.clips import ClipCuttingService
from content_pipeline.core.effects import VideoEffectsProcessor
from content_pipeline.core.uploads import UploadProvider, UploadService
from content_pipeline.domain.clips import (
    ClipCandidateRequest,
    ClipPlan,
    ClipSelection,
    CutRequest,
    CutResult,
    Transcript,
    TranscriptSegment,
)
from content_pipeline.domain.effects import (
    EffectPlan,
    EffectResult,
    ZoomEffect,
    ZoomStyle,
)
from content_pipeline.domain.metadata import (
    MetadataGenerationRequest,
    MetadataGenerationResult,
)
from content_pipeline.domain.trends import TrendCandidate, TrendSnapshot, TrendSource
from content_pipeline.domain.uploads import (
    UploadRequest,
    UploadResponse,
    UploadResult,
    UploadStatus,
)
from content_pipeline.exceptions import ApplicationError


class StubTranscriptionProvider:
    def __init__(self, transcript: Transcript) -> None:
        self._transcript = transcript

    def transcribe(self, source_video: Path) -> Transcript:
        return self._transcript


class StubSegmentSelector:
    def __init__(self, plan: ClipPlan) -> None:
        self._plan = plan

    def select(self, transcript: Transcript, request: ClipCandidateRequest) -> ClipPlan:
        return self._plan


class TouchingCutter:
    """Creates a real (empty) file for each cut so upload validation can pass."""

    def cut(self, request: CutRequest) -> CutResult:
        request.output_video.touch()
        return CutResult(
            output_video=request.output_video,
            start_seconds=request.selection.start_seconds,
            end_seconds=request.selection.end_seconds,
        )


class StubMetadataProvider:
    def __init__(self) -> None:
        self.requests: list[MetadataGenerationRequest] = []

    def generate(self, request: MetadataGenerationRequest) -> MetadataGenerationResult:
        self.requests.append(request)
        return MetadataGenerationResult(
            title="Generated title",
            description="Generated description.",
            hashtags=("#a",),
        )


class RecordingUploadProvider:
    def __init__(self) -> None:
        self.calls: list[UploadRequest] = []

    def supports(self, platform: str) -> bool:
        return platform == "youtube"

    def upload(self, request: UploadRequest, channel: Channel) -> UploadResponse:
        self.calls.append(request)
        return UploadResponse(
            result=UploadResult.SUCCESS,
            status=UploadStatus.PUBLISHED,
            provider_name="youtube",
            external_id=f"video-{len(self.calls)}",
        )


class TouchingEffectsProcessor:
    """Creates a real (empty) output file, recording every request it saw."""

    def __init__(self) -> None:
        self.requests: list[object] = []

    def apply(self, request: object) -> EffectResult:
        self.requests.append(request)
        output_video = request.output_video  # type: ignore[attr-defined]
        output_video.touch()
        return EffectResult(output_video=output_video, applied=("zoom:zoom_in",))


def _transcript() -> Transcript:
    return Transcript(
        segments=(
            TranscriptSegment(
                start_seconds=0, end_seconds=10, text="First clip content."
            ),
            TranscriptSegment(
                start_seconds=10, end_seconds=20, text="Second clip content."
            ),
        ),
        language="en",
        duration_seconds=20,
    )


def _plan() -> ClipPlan:
    return ClipPlan(
        selections=(
            ClipSelection(
                start_seconds=0, end_seconds=10, title="Clip 1", reason="r", score=0.9
            ),
            ClipSelection(
                start_seconds=10, end_seconds=20, title="Clip 2", reason="r", score=0.8
            ),
        )
    )


@pytest.fixture
def channels(tmp_path: Path) -> ChannelManager:
    manager = ChannelManager(JsonChannelRepository(tmp_path / "channels.json"))
    manager.create_channel("Primary", "youtube", channel_id="chan-1")
    return manager


@pytest.fixture
def source_video(tmp_path: Path) -> Path:
    video = tmp_path / "source.mp4"
    video.touch()
    return video


def _clip_service() -> ClipCuttingService:
    return ClipCuttingService(
        cast(object, StubTranscriptionProvider(_transcript())),  # type: ignore[arg-type]
        cast(object, StubSegmentSelector(_plan())),  # type: ignore[arg-type]
        cast(object, TouchingCutter()),  # type: ignore[arg-type]
    )


def test_run_cuts_generates_metadata_and_uploads_every_clip(
    channels: ChannelManager, source_video: Path, tmp_path: Path
) -> None:
    metadata_provider = StubMetadataProvider()
    upload_provider = RecordingUploadProvider()
    pipeline = ContentPipeline(
        clip_service=_clip_service(),
        metadata_provider=cast(object, metadata_provider),  # type: ignore[arg-type]
        channels=channels,
        upload_service=UploadService(cast(UploadProvider, upload_provider), channels),
    )

    outcomes = pipeline.run(
        PipelineRunRequest(
            source_video=source_video,
            channel_id="chan-1",
            output_directory=tmp_path / "out",
        )
    )

    assert len(outcomes) == 2
    assert all(outcome.metadata.title == "Generated title" for outcome in outcomes)
    assert len(upload_provider.calls) == 2
    assert all(
        outcome.upload_response is not None
        and outcome.upload_response.result.value == "success"
        for outcome in outcomes
    )
    assert metadata_provider.requests[0].transcript == "First clip content."
    assert metadata_provider.requests[1].transcript == "Second clip content."


def test_run_applies_effects_before_upload_when_a_plan_is_given(
    channels: ChannelManager, source_video: Path, tmp_path: Path
) -> None:
    effects_processor = TouchingEffectsProcessor()
    upload_provider = RecordingUploadProvider()
    pipeline = ContentPipeline(
        clip_service=_clip_service(),
        metadata_provider=cast(object, StubMetadataProvider()),  # type: ignore[arg-type]
        channels=channels,
        upload_service=UploadService(cast(UploadProvider, upload_provider), channels),
        effects_processor=cast(VideoEffectsProcessor, effects_processor),
    )

    outcomes = pipeline.run(
        PipelineRunRequest(
            source_video=source_video,
            channel_id="chan-1",
            output_directory=tmp_path / "out",
            effects_plan=EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN)),
        )
    )

    assert len(effects_processor.requests) == 2
    assert all(
        outcome.metadata.video_path.name.endswith("_fx.mp4") for outcome in outcomes
    )


def test_run_skips_effects_when_no_plan_is_given(
    channels: ChannelManager, source_video: Path, tmp_path: Path
) -> None:
    effects_processor = TouchingEffectsProcessor()
    pipeline = ContentPipeline(
        clip_service=_clip_service(),
        metadata_provider=cast(object, StubMetadataProvider()),  # type: ignore[arg-type]
        channels=channels,
        effects_processor=cast(VideoEffectsProcessor, effects_processor),
    )

    outcomes = pipeline.run(
        PipelineRunRequest(
            source_video=source_video,
            channel_id="chan-1",
            output_directory=tmp_path / "out",
            publish=False,
        )
    )

    assert effects_processor.requests == []
    assert all(
        not outcome.metadata.video_path.name.endswith("_fx.mp4")
        for outcome in outcomes
    )


def test_run_skips_upload_when_publish_is_false(
    channels: ChannelManager, source_video: Path, tmp_path: Path
) -> None:
    pipeline = ContentPipeline(
        clip_service=_clip_service(),
        metadata_provider=cast(object, StubMetadataProvider()),  # type: ignore[arg-type]
        channels=channels,
    )

    outcomes = pipeline.run(
        PipelineRunRequest(
            source_video=source_video,
            channel_id="chan-1",
            output_directory=tmp_path / "out",
            publish=False,
        )
    )

    assert len(outcomes) == 2
    assert all(outcome.upload_response is None for outcome in outcomes)


def test_run_requires_an_upload_service_to_publish(
    channels: ChannelManager, source_video: Path, tmp_path: Path
) -> None:
    pipeline = ContentPipeline(
        clip_service=_clip_service(),
        metadata_provider=cast(object, StubMetadataProvider()),  # type: ignore[arg-type]
        channels=channels,
    )

    with pytest.raises(ApplicationError, match="upload service"):
        pipeline.run(
            PipelineRunRequest(
                source_video=source_video,
                channel_id="chan-1",
                output_directory=tmp_path / "out",
                publish=True,
            )
        )


def test_run_rejects_a_disabled_channel(
    channels: ChannelManager, source_video: Path, tmp_path: Path
) -> None:
    channels.disable_channel("chan-1")
    pipeline = ContentPipeline(
        clip_service=_clip_service(),
        metadata_provider=cast(object, StubMetadataProvider()),  # type: ignore[arg-type]
        channels=channels,
    )

    with pytest.raises(ApplicationError, match="disabled"):
        pipeline.run(
            PipelineRunRequest(
                source_video=source_video,
                channel_id="chan-1",
                output_directory=tmp_path / "out",
                publish=False,
            )
        )


def test_topic_hint_from_snapshot_returns_the_top_candidate() -> None:
    snapshot = TrendSnapshot(
        candidates=(
            TrendCandidate(topic="Low", source=TrendSource.YOUTUBE, score=1.0),
            TrendCandidate(topic="High", source=TrendSource.YOUTUBE, score=9.0),
        )
    )

    assert topic_hint_from_snapshot(snapshot) == "High"


def test_topic_hint_from_snapshot_returns_none_when_empty() -> None:
    assert topic_hint_from_snapshot(TrendSnapshot(candidates=())) is None
