"""End-to-end workflow orchestration for one local source video.

This is the "application-level workflow orchestration" the README names as a
composition concern: it chains the independent, individually-tested core
services (clip cutting, effects processing, metadata generation, subtitle
burning, uploads) into one operator-facing run. No new business rules live
here; every invariant is still owned and enforced by the service it
delegates to.
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from content_pipeline.app.subtitles import write_srt_for_clip
from content_pipeline.core.captions.subtitles import SubtitleBurner
from content_pipeline.core.channels import ChannelManager
from content_pipeline.core.clips.service import ClipCuttingService
from content_pipeline.core.effects import VideoEffectsProcessor
from content_pipeline.core.metadata.provider import MetadataProvider
from content_pipeline.core.uploads.service import UploadService
from content_pipeline.domain.clips import ClipCandidateRequest, CutResult, Transcript
from content_pipeline.domain.effects import EffectPlan, EffectRequest
from content_pipeline.domain.metadata import (
    Metadata,
    MetadataGenerationRequest,
    Visibility,
)
from content_pipeline.domain.trends import TrendSnapshot
from content_pipeline.domain.uploads import UploadRequest, UploadResponse
from content_pipeline.exceptions import ApplicationError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)


def topic_hint_from_snapshot(snapshot: TrendSnapshot) -> str | None:
    """Return the single highest-scored topic from a trend snapshot, if any.

    A convenience default for feeding ``TrendScanService`` output into
    ``PipelineRunRequest.topic_hint``. Callers with more nuanced selection
    logic (matching a topic to available footage, filtering by source, etc.)
    should read ``snapshot.candidates`` directly instead.
    """
    top = snapshot.top(1)
    return top[0].topic if top else None


@dataclass(frozen=True, slots=True)
class PipelineRunRequest:
    """Operator-supplied inputs for one end-to-end pipeline run."""

    source_video: Path
    channel_id: str
    output_directory: Path
    maximum_clips: int = 3
    minimum_duration_seconds: float = 15.0
    maximum_duration_seconds: float = 90.0
    topic_hint: str | None = None
    language: str = "en"
    category: str = "general"
    visibility: Visibility = Visibility.PRIVATE
    burn_subtitles: bool = False
    effects_plan: EffectPlan | None = None
    publish: bool = True


@dataclass(frozen=True, slots=True)
class PipelineClipOutcome:
    """The materialized result for one clip produced during a pipeline run."""

    cut_result: CutResult
    metadata: Metadata
    upload_response: UploadResponse | None


class ContentPipeline:
    """Coordinate clip cutting, metadata generation, and upload for one video.

    Trend detection is intentionally not chained automatically: a
    :class:`~content_pipeline.domain.trends.models.TrendSnapshot` describes
    topics, not footage, so the caller decides how a trending topic maps to
    ``topic_hint`` and to a choice of source video. See
    :meth:`topic_hint_from_snapshot` for a simple default.
    """

    def __init__(
        self,
        clip_service: ClipCuttingService,
        metadata_provider: MetadataProvider,
        channels: ChannelManager,
        upload_service: UploadService | None = None,
        subtitle_burner: SubtitleBurner | None = None,
        effects_processor: VideoEffectsProcessor | None = None,
    ) -> None:
        self._clip_service = clip_service
        self._metadata_provider = metadata_provider
        self._upload_service = upload_service
        self._channels = channels
        self._subtitle_burner = subtitle_burner or SubtitleBurner()
        self._effects_processor = effects_processor or VideoEffectsProcessor()

    def run(self, request: PipelineRunRequest) -> tuple[PipelineClipOutcome, ...]:
        """Run the full pipeline for one local source video.

        Steps: validate the destination channel, transcribe and select clip
        candidates, cut every selection, generate metadata per clip from its
        own transcript slice, optionally burn subtitles, and upload each
        clip unless ``request.publish`` is ``False``.
        """
        if request.publish and self._upload_service is None:
            raise ApplicationError(
                "An upload service is required when request.publish is True"
            )
        channel = self._channels.load_channel(request.channel_id)
        if not channel.enabled:
            raise ApplicationError(f"Channel is disabled: {request.channel_id}")

        candidate_request = ClipCandidateRequest(
            maximum_clips=request.maximum_clips,
            minimum_duration_seconds=request.minimum_duration_seconds,
            maximum_duration_seconds=request.maximum_duration_seconds,
            topic_hint=request.topic_hint,
        )
        transcript, plan = self._clip_service.plan_with_transcript(
            request.source_video, candidate_request
        )
        request.output_directory.mkdir(parents=True, exist_ok=True)
        cut_results = self._clip_service.cut_all(
            request.source_video, plan, request.output_directory
        )

        outcomes: list[PipelineClipOutcome] = []
        for selection, cut_result in zip(plan.selections, cut_results, strict=True):
            outcomes.append(
                self._publish_one(
                    request=request,
                    channel_id=channel.id,
                    transcript=transcript,
                    selection_start=selection.start_seconds,
                    selection_end=selection.end_seconds,
                    cut_result=cut_result,
                )
            )
        _LOGGER.info(
            "pipeline_run_completed",
            extra={
                "source_video": str(request.source_video),
                "channel_id": channel.id,
                "clip_count": len(outcomes),
            },
        )
        return tuple(outcomes)

    def _publish_one(
        self,
        *,
        request: PipelineRunRequest,
        channel_id: str,
        transcript: Transcript,
        selection_start: float,
        selection_end: float,
        cut_result: CutResult,
    ) -> PipelineClipOutcome:
        """Generate metadata for one cut clip and optionally upload it."""
        clip_transcript_text = transcript.text_between(selection_start, selection_end)
        generation = self._metadata_provider.generate(
            MetadataGenerationRequest(
                transcript=clip_transcript_text,
                language=request.language,
                target_platform="youtube",
            )
        )
        video_path = self._maybe_apply_effects(
            cut_result=cut_result, effects_plan=request.effects_plan
        )
        video_path = self._maybe_burn_subtitles(
            video_path=video_path,
            transcript=transcript,
            selection_start=selection_start,
            selection_end=selection_end,
            burn_subtitles=request.burn_subtitles,
        )
        metadata = Metadata(
            title=generation.title,
            description=generation.description,
            language=request.language,
            category=request.category,
            visibility=request.visibility,
            video_path=video_path,
            project_id=str(uuid4()),
            channel_id=channel_id,
            hashtags=generation.hashtags,
        )
        upload_response: UploadResponse | None = None
        if request.publish and self._upload_service is not None:
            upload_response = self._upload_service.upload(
                UploadRequest(metadata=metadata)
            )
        return PipelineClipOutcome(
            cut_result=cut_result, metadata=metadata, upload_response=upload_response
        )

    def _maybe_apply_effects(
        self,
        *,
        cut_result: CutResult,
        effects_plan: EffectPlan | None,
    ) -> Path:
        """Apply zoom/pan, transitions, overlays, and SFX when a plan is given.

        Runs before subtitle burn-in so captions are never obscured by a
        zoom/pan crop, and so a transition fade doesn't fade a subtitle track
        that hasn't been burned in yet.
        """
        if effects_plan is None or effects_plan.is_empty:
            return cut_result.output_video
        video_path = cut_result.output_video
        output_path = video_path.with_name(f"{video_path.stem}_fx.mp4")
        result = self._effects_processor.apply(
            EffectRequest(
                input_video=video_path,
                output_video=output_path,
                plan=effects_plan,
                clip_duration_seconds=cut_result.duration_seconds,
            )
        )
        return result.output_video

    def _maybe_burn_subtitles(
        self,
        *,
        video_path: Path,
        transcript: Transcript,
        selection_start: float,
        selection_end: float,
        burn_subtitles: bool,
    ) -> Path:
        """Burn subtitles into a clip when requested; otherwise return it unchanged."""
        if not burn_subtitles:
            return video_path
        srt_path = video_path.with_suffix(".srt")
        write_srt_for_clip(
            transcript,
            selection_start=selection_start,
            selection_end=selection_end,
            output_path=srt_path,
        )
        subtitled_path = video_path.with_name(f"{video_path.stem}_subtitled.mp4")
        return self._subtitle_burner.burn(video_path, srt_path, subtitled_path)
