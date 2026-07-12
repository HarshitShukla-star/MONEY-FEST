"""Business orchestration for transcript-driven clip cutting."""

from pathlib import Path

from content_pipeline.core.clips.cutter import ClipCutter
from content_pipeline.core.clips.provider import SegmentSelector, TranscriptionProvider
from content_pipeline.domain.clips import (
    ClipCandidateRequest,
    ClipPlan,
    ClipSelectionError,
    ClipValidationError,
    CutRequest,
    CutResult,
    Transcript,
)
from content_pipeline.logging import get_logger
from content_pipeline.utils.files import require_file

_LOGGER = get_logger(__name__)


class ClipCuttingService:
    """Coordinate transcription, selection, and extraction for one source video.

    This service operates only on a local video file already present on disk.
    It performs no network fetching of its own; the source video must be
    supplied by the caller (for example, the operator's own footage or
    footage obtained under an appropriate license).
    """

    def __init__(
        self,
        transcription_provider: TranscriptionProvider,
        segment_selector: SegmentSelector,
        cutter: ClipCutter,
    ) -> None:
        self._transcription_provider = transcription_provider
        self._segment_selector = segment_selector
        self._cutter = cutter

    def plan(
        self, source_video: Path, request: ClipCandidateRequest
    ) -> ClipPlan:
        """Transcribe a local source video and select candidate clips from it."""
        _transcript, clip_plan = self.plan_with_transcript(source_video, request)
        return clip_plan

    def plan_with_transcript(
        self, source_video: Path, request: ClipCandidateRequest
    ) -> tuple[Transcript, ClipPlan]:
        """Transcribe and select candidate clips, also returning the transcript.

        Callers that need the full transcript afterward (for example, to
        generate per-clip metadata or subtitles from the same transcription)
        should use this instead of ``plan`` to avoid transcribing twice.
        """
        source = require_file(source_video)
        transcript = self._transcription_provider.transcribe(source)
        clip_plan = self._segment_selector.select(transcript, request)
        if not clip_plan.selections:
            raise ClipSelectionError("No clip selections were produced")
        _LOGGER.info(
            "clip_plan_ready",
            extra={
                "source_video": str(source),
                "clip_count": len(clip_plan.selections),
            },
        )
        return transcript, clip_plan

    def cut_all(
        self,
        source_video: Path,
        plan: ClipPlan,
        output_directory: Path,
    ) -> tuple[CutResult, ...]:
        """Materialize every selection in ``plan`` into ``output_directory``."""
        source = require_file(source_video)
        if not isinstance(output_directory, Path) or not output_directory.is_dir():
            raise ClipValidationError(
                f"Output directory does not exist: {output_directory}"
            )
        results: list[CutResult] = []
        for index, selection in enumerate(plan.selections, start=1):
            output_video = output_directory / f"{source.stem}_clip_{index:02d}.mp4"
            request = CutRequest(
                source_video=source,
                selection=selection,
                output_video=output_video,
            )
            results.append(self._cutter.cut(request))
        _LOGGER.info(
            "clips_materialized",
            extra={"source_video": str(source), "clip_count": len(results)},
        )
        return tuple(results)
