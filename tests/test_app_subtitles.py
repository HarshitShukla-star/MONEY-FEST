"""Tests for generating a re-timed SRT subtitle file for one clip slice."""

from pathlib import Path

import pytest

from content_pipeline.app.subtitles import write_srt_for_clip
from content_pipeline.domain.clips import Transcript, TranscriptSegment
from content_pipeline.exceptions import ValidationError


def _transcript() -> Transcript:
    return Transcript(
        segments=(
            TranscriptSegment(start_seconds=0, end_seconds=5, text="Intro line."),
            TranscriptSegment(start_seconds=5, end_seconds=12, text="Middle line."),
            TranscriptSegment(start_seconds=12, end_seconds=20, text="Outro line."),
        ),
        language="en",
        duration_seconds=20,
    )


def test_write_srt_includes_only_overlapping_segments_rebased_to_zero(
    tmp_path: Path,
) -> None:
    output = tmp_path / "clip.srt"

    write_srt_for_clip(
        _transcript(), selection_start=3, selection_end=10, output_path=output
    )

    content = output.read_text(encoding="utf-8")
    assert "Intro line." in content
    assert "Middle line." in content
    assert "Outro line." not in content
    assert "00:00:00,000 --> 00:00:02,000" in content
    assert "1\n" in content
    assert "2\n" in content


def test_write_srt_rejects_a_non_positive_range(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="after selection start"):
        write_srt_for_clip(
            _transcript(),
            selection_start=10,
            selection_end=10,
            output_path=tmp_path / "clip.srt",
        )


def test_write_srt_returns_the_written_path(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "clip.srt"
    output.parent.mkdir()

    result = write_srt_for_clip(
        _transcript(), selection_start=0, selection_end=5, output_path=output
    )

    assert result == output
    assert output.is_file()
