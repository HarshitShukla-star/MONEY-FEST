"""FFmpeg-backed clip extraction at the clip-processing boundary."""

import subprocess
from collections.abc import Callable
from math import isfinite
from pathlib import Path

from content_pipeline.domain.clips import ClipValidationError, CutRequest, CutResult
from content_pipeline.exceptions import ProviderError, ValidationError
from content_pipeline.logging import get_logger
from content_pipeline.utils.files import require_file

_LOGGER = get_logger(__name__)

type CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
DEFAULT_TIMEOUT_SECONDS = 300.0


class ClipCutter:
    """Extract one time-bounded clip from a local source video with FFmpeg."""

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

    def cut(self, request: CutRequest) -> CutResult:
        """Extract the requested selection's time range into a new file."""
        if not isinstance(request, CutRequest):
            raise ClipValidationError("Request must be a CutRequest")
        source = require_file(request.source_video)
        output = _validate_output_path(request.output_video)
        if output.exists():
            raise ClipValidationError(f"Output video already exists: {output}")
        selection = request.selection
        duration = selection.duration_seconds
        command = [
            self._executable,
            "-n",
            "-ss",
            f"{selection.start_seconds:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
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
                "clip_cut_failed",
                extra={"source_video": str(source), "output_video": str(output)},
            )
            raise ProviderError("FFmpeg clip cut failed") from exc
        _LOGGER.info(
            "clip_cut",
            extra={
                "source_video": str(source),
                "output_video": str(output),
                "start_seconds": selection.start_seconds,
                "end_seconds": selection.end_seconds,
            },
        )
        return CutResult(
            output_video=output,
            start_seconds=selection.start_seconds,
            end_seconds=selection.end_seconds,
        )


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
        raise ClipValidationError("Output video must be a non-empty file path")
    if output_video.is_dir():
        raise ClipValidationError("Output video must not be a directory")
    if not output_video.parent.is_dir():
        raise ClipValidationError(
            f"Output video directory does not exist: {output_video.parent}"
        )
    return output_video
