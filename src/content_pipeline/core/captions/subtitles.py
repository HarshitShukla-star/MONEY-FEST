"""FFmpeg-backed subtitle burn-in at the caption-processing boundary."""

import subprocess
from collections.abc import Callable
from math import isfinite
from pathlib import Path

from content_pipeline.exceptions import ProviderError, ValidationError
from content_pipeline.logging import get_logger
from content_pipeline.utils.files import require_file

_LOGGER = get_logger(__name__)

type CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
DEFAULT_TIMEOUT_SECONDS = 300.0


class SubtitleBurner:
    """Burn an existing SRT subtitle track into a video with FFmpeg."""

    def __init__(
        self,
        executable: str = "ffmpeg",
        runner: CommandRunner | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValidationError("FFmpeg timeout must be a positive number")
        self._executable = executable
        self._runner = runner or (
            lambda command: _run_command(command, timeout_seconds=timeout_seconds)
        )

    def burn(self, input_video: Path, subtitles: Path, output_video: Path) -> Path:
        """Burn ``subtitles`` into ``input_video`` and write ``output_video``."""
        source = require_file(input_video)
        subtitle_file = require_file(subtitles)
        if subtitle_file.suffix.lower() != ".srt":
            raise ValidationError("Subtitle file must have an .srt extension")
        output = _validate_output_path(output_video)
        if output == source:
            raise ValidationError("Output video must differ from the input video")
        if output.exists():
            raise ValidationError(f"Output video already exists: {output}")
        command = [
            self._executable,
            "-n",
            "-i",
            str(source),
            "-vf",
            f"subtitles=filename='{_escape_filter_path(subtitle_file)}'",
            "-c:a",
            "copy",
            str(output),
        ]
        try:
            self._runner(command)
        except (
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            _LOGGER.error(
                "subtitle_burn_failed",
                extra={"input_video": str(source), "output_video": str(output)},
            )
            raise ProviderError("FFmpeg subtitle burn failed") from exc
        _LOGGER.info(
            "subtitles_burned",
            extra={"input_video": str(source), "output_video": str(output)},
        )
        return output


def _run_command(
    command: list[str], *, timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    """Run FFmpeg without invoking a shell."""
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _validate_output_path(output_video: Path) -> Path:
    """Require an output filename in an existing destination directory."""
    if not isinstance(output_video, Path) or output_video == Path("."):
        raise ValidationError("Output video must be a non-empty file path")
    if output_video.is_dir():
        raise ValidationError("Output video must not be a directory")
    if not output_video.parent.is_dir():
        raise ValidationError(
            f"Output video directory does not exist: {output_video.parent}"
        )
    return output_video


def _escape_filter_path(path: Path) -> str:
    """Escape a path for FFmpeg's subtitle-filter filename argument."""
    value = str(path).replace("\\", "/")
    for character in ("\\", "'", ":", ",", ";", "[", "]"):
        value = value.replace(character, f"\\{character}")
    return value
