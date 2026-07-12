"""Generate a SubRip (.srt) subtitle file for one clip's transcript slice.

``core.captions.subtitles.SubtitleBurner`` burns an already-written ``.srt``
file into a video; it deliberately has no opinion about where that file
comes from. Producing one from a transcript slice, and re-timing it to the
clip's own zero-based timeline, is an application-level concern that belongs
at the composition/delivery layer alongside the rest of this package.
"""

from pathlib import Path

from content_pipeline.domain.clips import Transcript
from content_pipeline.exceptions import ValidationError


def write_srt_for_clip(
    transcript: Transcript,
    *,
    selection_start: float,
    selection_end: float,
    output_path: Path,
) -> Path:
    """Write an SRT file covering ``[selection_start, selection_end)``.

    Segment timestamps are re-based so that ``selection_start`` becomes 0,
    matching the timeline of a clip already cut from the source video.
    """
    if selection_end <= selection_start:
        raise ValidationError("Selection end must be after selection start")
    entries = [
        segment
        for segment in transcript.segments
        if segment.start_seconds < selection_end
        and segment.end_seconds > selection_start
    ]
    lines: list[str] = []
    for index, segment in enumerate(entries, start=1):
        start = max(segment.start_seconds, selection_start) - selection_start
        end = min(segment.end_seconds, selection_end) - selection_start
        lines.append(str(index))
        lines.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
        lines.append(segment.text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _format_timestamp(seconds: float) -> str:
    """Render seconds as an SRT timestamp: HH:MM:SS,mmm."""
    total_milliseconds = round(seconds * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
