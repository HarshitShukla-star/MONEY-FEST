"""Tests for FFmpeg-backed effects application without invoking FFmpeg."""

import subprocess
from pathlib import Path

import pytest

from content_pipeline.core.effects import VideoEffectsProcessor
from content_pipeline.domain.effects import (
    EffectPlan,
    EffectRequest,
    EffectValidationError,
    SoundEffect,
    TransitionEffect,
    TransitionStyle,
    ZoomEffect,
    ZoomStyle,
)
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
def video_paths(tmp_path: Path) -> tuple[Path, Path]:
    """Create an input video and a valid (non-existent) output location."""
    video = tmp_path / "input.mp4"
    output = tmp_path / "output.mp4"
    video.touch()
    return video, output


def test_apply_rejects_an_empty_effect_plan(video_paths: tuple[Path, Path]) -> None:
    video, output = video_paths

    with pytest.raises(EffectValidationError, match="no effects"):
        VideoEffectsProcessor(runner=RecordingRunner()).apply(
            EffectRequest(input_video=video, output_video=output, plan=EffectPlan())
        )


def test_apply_builds_a_shell_free_command_for_a_video_only_plan(
    video_paths: tuple[Path, Path],
) -> None:
    video, output = video_paths
    runner = RecordingRunner()
    plan = EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN))

    result = VideoEffectsProcessor(runner=runner).apply(
        EffectRequest(input_video=video, output_video=output, plan=plan)
    )

    assert result.output_video == output
    assert result.applied == ("zoom:zoom_in",)
    assert len(runner.commands) == 1
    command = runner.commands[0]
    assert command[:4] == ["ffmpeg", "-n", "-i", str(video.resolve())]
    assert "-filter_complex" in command
    assert command[command.index("-map") + 1] == "[vout]"
    assert "0:a?" in command
    assert "-c:v" not in command
    assert "-c:a" in command
    assert command[-1] == str(output)


def test_apply_maps_extra_inputs_and_audio_output_for_sound_effects(
    tmp_path: Path, video_paths: tuple[Path, Path]
) -> None:
    video, output = video_paths
    sfx = tmp_path / "ding.wav"
    sfx.touch()
    runner = RecordingRunner()
    plan = EffectPlan(sound_effects=(SoundEffect(audio_path=sfx, start_seconds=1),))

    VideoEffectsProcessor(runner=runner).apply(
        EffectRequest(input_video=video, output_video=output, plan=plan)
    )

    command = runner.commands[0]
    assert command.count("-i") == 2
    assert str(sfx.resolve()) in command
    # No video filters were requested, so the video stream is copied and the
    # only "-map" pair pointing at a filter label is for audio.
    assert "-c:v" in command
    assert "[aout]" in command


def test_apply_rejects_a_missing_sound_effect_file(
    video_paths: tuple[Path, Path], tmp_path: Path
) -> None:
    video, output = video_paths
    plan = EffectPlan(
        sound_effects=(
            SoundEffect(audio_path=tmp_path / "missing.wav", start_seconds=0),
        )
    )

    with pytest.raises(ValidationError, match="Expected a file"):
        VideoEffectsProcessor(runner=RecordingRunner()).apply(
            EffectRequest(input_video=video, output_video=output, plan=plan)
        )


def test_apply_requires_clip_duration_for_fade_out(
    video_paths: tuple[Path, Path],
) -> None:
    video, output = video_paths
    plan = EffectPlan(
        transition=TransitionEffect(style=TransitionStyle.FADE_OUT, duration_seconds=1)
    )

    with pytest.raises(EffectValidationError, match="Clip duration is required"):
        VideoEffectsProcessor(runner=RecordingRunner()).apply(
            EffectRequest(input_video=video, output_video=output, plan=plan)
        )


def test_apply_rejects_missing_input_video(video_paths: tuple[Path, Path]) -> None:
    video, output = video_paths
    video.unlink()
    plan = EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN))

    with pytest.raises(ValidationError, match="Expected a file"):
        VideoEffectsProcessor(runner=RecordingRunner()).apply(
            EffectRequest(input_video=video, output_video=output, plan=plan)
        )


def test_apply_rejects_unsafe_output_and_timeout_configuration(
    video_paths: tuple[Path, Path], tmp_path: Path
) -> None:
    video, output = video_paths
    output.touch()
    plan = EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN))

    with pytest.raises(EffectValidationError, match="already exists"):
        VideoEffectsProcessor(runner=RecordingRunner()).apply(
            EffectRequest(input_video=video, output_video=output, plan=plan)
        )
    with pytest.raises(EffectValidationError, match="directory does not exist"):
        VideoEffectsProcessor(runner=RecordingRunner()).apply(
            EffectRequest(
                input_video=video,
                output_video=tmp_path / "missing" / "out.mp4",
                plan=plan,
            )
        )
    for timeout in (0, float("inf"), float("nan")):
        with pytest.raises(ValidationError, match="timeout"):
            VideoEffectsProcessor(runner=RecordingRunner(), timeout_seconds=timeout)


def test_apply_converts_ffmpeg_process_failures(
    video_paths: tuple[Path, Path],
) -> None:
    video, output = video_paths
    plan = EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN))
    error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="bad input")

    with pytest.raises(ProviderError, match="FFmpeg effects processing failed"):
        VideoEffectsProcessor(runner=RecordingRunner(error)).apply(
            EffectRequest(input_video=video, output_video=output, plan=plan)
        )


def test_apply_converts_ffmpeg_timeout(video_paths: tuple[Path, Path]) -> None:
    video, output = video_paths
    plan = EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN))
    error = subprocess.TimeoutExpired(["ffmpeg"], timeout=1)

    with pytest.raises(ProviderError, match="FFmpeg effects processing failed"):
        VideoEffectsProcessor(runner=RecordingRunner(error)).apply(
            EffectRequest(input_video=video, output_video=output, plan=plan)
        )
