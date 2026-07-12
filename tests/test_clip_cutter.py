"""Tests for FFmpeg clip extraction without invoking FFmpeg."""

import subprocess
from pathlib import Path

import pytest

from content_pipeline.core.clips import ClipCutter
from content_pipeline.domain.clips import ClipSelection, ClipValidationError, CutRequest
from content_pipeline.exceptions import ProviderError, ValidationError


class RecordingRunner:
    """Mock command runner for the injected FFmpeg process boundary."""

    def __init__(
        self,
        error: OSError
        | subprocess.CalledProcessError
        | subprocess.TimeoutExpired
        | None = None,
    ) -> None:
        self.error = error
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(command, 0, "", "")


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path]:
    """Create an input video and a valid output location."""
    video = tmp_path / "input.mp4"
    output = tmp_path / "clip.mp4"
    video.touch()
    return video, output


def _selection() -> ClipSelection:
    return ClipSelection(
        start_seconds=1.5, end_seconds=11.5, title="Hook", reason="strong", score=0.8
    )


def test_cut_builds_a_shell_free_ffmpeg_command_and_returns_result(
    files: tuple[Path, Path],
) -> None:
    video, output = files
    runner = RecordingRunner()
    request = CutRequest(
        source_video=video, selection=_selection(), output_video=output
    )

    result = ClipCutter(runner=runner).cut(request)

    assert result.output_video == output
    assert result.start_seconds == 1.5
    assert result.end_seconds == 11.5
    assert runner.commands == [
        [
            "ffmpeg",
            "-n",
            "-ss",
            "1.500",
            "-i",
            str(video.resolve()),
            "-t",
            "10.000",
            "-c",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
            str(output),
        ]
    ]


def test_cut_rejects_missing_source_file(files: tuple[Path, Path]) -> None:
    video, output = files
    video.unlink()
    request = CutRequest(
        source_video=video, selection=_selection(), output_video=output
    )

    with pytest.raises(ValidationError, match="Expected a file"):
        ClipCutter(runner=RecordingRunner()).cut(request)


def test_cut_rejects_output_that_already_exists(files: tuple[Path, Path]) -> None:
    video, output = files
    output.touch()
    request = CutRequest(
        source_video=video, selection=_selection(), output_video=output
    )

    with pytest.raises(ClipValidationError, match="already exists"):
        ClipCutter(runner=RecordingRunner()).cut(request)


def test_cut_rejects_invalid_request_type(files: tuple[Path, Path]) -> None:
    with pytest.raises(ClipValidationError, match="CutRequest"):
        ClipCutter(runner=RecordingRunner()).cut("not-a-request")  # type: ignore[arg-type]


def test_cut_converts_ffmpeg_process_failures(files: tuple[Path, Path]) -> None:
    video, output = files
    error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="bad input")
    request = CutRequest(
        source_video=video, selection=_selection(), output_video=output
    )

    with pytest.raises(ProviderError, match="FFmpeg clip cut failed"):
        ClipCutter(runner=RecordingRunner(error)).cut(request)


def test_cut_converts_ffmpeg_timeout(files: tuple[Path, Path]) -> None:
    video, output = files
    error = subprocess.TimeoutExpired(["ffmpeg"], timeout=1)
    request = CutRequest(
        source_video=video, selection=_selection(), output_video=output
    )

    with pytest.raises(ProviderError, match="FFmpeg clip cut failed"):
        ClipCutter(runner=RecordingRunner(error)).cut(request)


def test_constructor_rejects_invalid_timeout(files: tuple[Path, Path]) -> None:
    for timeout in (0, float("inf"), float("nan")):
        with pytest.raises(ValidationError, match="timeout"):
            ClipCutter(runner=RecordingRunner(), timeout_seconds=timeout)
