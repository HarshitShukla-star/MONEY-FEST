"""Tests for FFmpeg subtitle burn-in without invoking FFmpeg."""

import subprocess
from pathlib import Path

import pytest

from content_pipeline.core.captions import SubtitleBurner
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
def files(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create input artifacts and a valid output location."""
    video = tmp_path / "input.mp4"
    subtitles = tmp_path / "captions.srt"
    output = tmp_path / "output.mp4"
    video.touch()
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    return video, subtitles, output


def test_burn_builds_a_shell_free_ffmpeg_command_and_returns_output(
    files: tuple[Path, Path, Path],
) -> None:
    video, subtitles, output = files
    runner = RecordingRunner()
    escaped_subtitle = str(subtitles.resolve()).replace("\\", "/").replace(":", "\\:")

    result = SubtitleBurner(runner=runner).burn(video, subtitles, output)

    assert result == output
    assert runner.commands == [
        [
            "ffmpeg",
            "-n",
            "-i",
            str(video.resolve()),
            "-vf",
            f"subtitles=filename='{escaped_subtitle}'",
            "-c:a",
            "copy",
            str(output),
        ]
    ]


@pytest.mark.parametrize("missing_index", [0, 1])
def test_burn_rejects_missing_input_or_subtitle_files(
    files: tuple[Path, Path, Path], missing_index: int
) -> None:
    paths = list(files)
    paths[missing_index].unlink()
    runner = RecordingRunner()

    with pytest.raises(ValidationError, match="Expected a file"):
        SubtitleBurner(runner=runner).burn(*paths)

    assert runner.commands == []


def test_burn_rejects_invalid_subtitle_and_output_paths(
    files: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    video, subtitles, _ = files
    invalid_subtitles = subtitles.with_suffix(".txt")
    subtitles.rename(invalid_subtitles)
    valid_subtitles = tmp_path / "valid.srt"
    valid_subtitles.touch()

    with pytest.raises(ValidationError, match=".srt"):
        SubtitleBurner(runner=RecordingRunner()).burn(
            video, invalid_subtitles, tmp_path / "output.mp4"
        )
    with pytest.raises(ValidationError, match="directory does not exist"):
        SubtitleBurner(runner=RecordingRunner()).burn(
            video, valid_subtitles, tmp_path / "missing" / "output.mp4"
        )
    with pytest.raises(ValidationError, match="must not be a directory"):
        SubtitleBurner(runner=RecordingRunner()).burn(video, valid_subtitles, tmp_path)


def test_burn_converts_ffmpeg_process_failures(files: tuple[Path, Path, Path]) -> None:
    video, subtitles, output = files
    error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="bad input")

    with pytest.raises(ProviderError, match="FFmpeg subtitle burn failed"):
        SubtitleBurner(runner=RecordingRunner(error)).burn(video, subtitles, output)


def test_burn_rejects_unsafe_output_and_timeout_configuration(
    files: tuple[Path, Path, Path],
) -> None:
    video, subtitles, output = files
    output.touch()

    with pytest.raises(ValidationError, match="already exists"):
        SubtitleBurner(runner=RecordingRunner()).burn(video, subtitles, output)
    with pytest.raises(ValidationError, match="differ"):
        SubtitleBurner(runner=RecordingRunner()).burn(video, subtitles, video)
    for timeout in (0, float("inf"), float("nan")):
        with pytest.raises(ValidationError, match="timeout"):
            SubtitleBurner(runner=RecordingRunner(), timeout_seconds=timeout)


def test_burn_converts_ffmpeg_timeout(files: tuple[Path, Path, Path]) -> None:
    video, subtitles, output = files
    error = subprocess.TimeoutExpired(["ffmpeg"], timeout=1)

    with pytest.raises(ProviderError, match="FFmpeg subtitle burn failed"):
        SubtitleBurner(runner=RecordingRunner(error)).burn(video, subtitles, output)
