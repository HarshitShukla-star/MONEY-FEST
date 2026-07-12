"""FFmpeg-backed visual/audio effects application at the effects boundary."""

import subprocess
from collections.abc import Callable
from math import isfinite
from pathlib import Path

from content_pipeline.core.effects.filters import (
    FilterGraph,
    applied_labels,
    build_filter_graph,
)
from content_pipeline.domain.effects import (
    EffectRequest,
    EffectResult,
    EffectValidationError,
)
from content_pipeline.exceptions import ProviderError, ValidationError
from content_pipeline.logging import get_logger
from content_pipeline.utils.files import require_file

_LOGGER = get_logger(__name__)

type CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
DEFAULT_TIMEOUT_SECONDS = 600.0


class VideoEffectsProcessor:
    """Apply zoom/pan, fade transitions, text overlays, and SFX with FFmpeg.

    Like ``ClipCutter`` and ``SubtitleBurner``, this operates only on local
    files already present on disk (the input video, and any sound-effect
    audio files referenced by the plan). It never fetches media over the
    network.
    """

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

    def apply(self, request: EffectRequest) -> EffectResult:
        """Apply every effect in ``request.plan`` and write a new output file."""
        if not isinstance(request, EffectRequest):
            raise EffectValidationError("Request must be an EffectRequest")
        if request.plan.is_empty:
            raise EffectValidationError("Effect plan has no effects to apply")
        source = require_file(request.input_video)
        output = _validate_output_path(request.output_video)
        if output.exists():
            raise EffectValidationError(f"Output video already exists: {output}")
        graph = build_filter_graph(
            request.plan, clip_duration_seconds=request.clip_duration_seconds
        )
        audio_inputs = tuple(require_file(path) for path in graph.extra_audio_inputs)
        command = self._build_command(source, output, graph, audio_inputs)
        try:
            self._runner(command)
        except (
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            _LOGGER.error(
                "effects_apply_failed",
                extra={"input_video": str(source), "output_video": str(output)},
            )
            raise ProviderError("FFmpeg effects processing failed") from exc
        labels = applied_labels(request.plan)
        _LOGGER.info(
            "effects_applied",
            extra={
                "input_video": str(source),
                "output_video": str(output),
                "effects": labels,
            },
        )
        return EffectResult(output_video=output, applied=labels)

    def _build_command(
        self,
        source: Path,
        output: Path,
        graph: FilterGraph,
        audio_inputs: tuple[Path, ...],
    ) -> list[str]:
        command = [self._executable, "-n", "-i", str(source)]
        for audio_input in audio_inputs:
            command.extend(["-i", str(audio_input)])
        if graph.filter_complex:
            command.extend(["-filter_complex", graph.filter_complex])
        command.extend(["-map", graph.video_map or "0:v"])
        command.extend(["-map", graph.audio_map or "0:a?"])
        if graph.video_map is None:
            command.extend(["-c:v", "copy"])
        if graph.audio_map is None:
            command.extend(["-c:a", "copy"])
        command.append(str(output))
        return command


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
        raise EffectValidationError("Output video must be a non-empty file path")
    if output_video.is_dir():
        raise EffectValidationError("Output video must not be a directory")
    if not output_video.parent.is_dir():
        raise EffectValidationError(
            f"Output video directory does not exist: {output_video.parent}"
        )
    return output_video
