"""Tests for immutable visual/audio effects domain values."""

from pathlib import Path

import pytest

from content_pipeline.domain.effects import (
    EffectPlan,
    EffectRequest,
    EffectResult,
    EffectValidationError,
    SoundEffect,
    TextOverlay,
    TransitionEffect,
    TransitionStyle,
    ZoomEffect,
    ZoomStyle,
)


def test_zoom_effect_normalizes_intensity() -> None:
    effect = ZoomEffect(style=ZoomStyle.ZOOM_IN, intensity=1)

    assert effect.intensity == 1.0


@pytest.mark.parametrize("intensity", [0, -0.1, 1.5, float("nan"), float("inf")])
def test_zoom_effect_rejects_out_of_range_intensity(intensity: float) -> None:
    with pytest.raises(EffectValidationError, match="Intensity"):
        ZoomEffect(style=ZoomStyle.ZOOM_IN, intensity=intensity)


def test_zoom_effect_rejects_non_enum_style() -> None:
    with pytest.raises(EffectValidationError, match="ZoomStyle"):
        ZoomEffect(style="zoom_in")  # type: ignore[arg-type]


def test_transition_effect_rejects_non_positive_duration() -> None:
    with pytest.raises(EffectValidationError, match="positive"):
        TransitionEffect(style=TransitionStyle.FADE_IN, duration_seconds=0)


def test_text_overlay_normalizes_fields_and_validates_time_range() -> None:
    overlay = TextOverlay(
        text="  hello  ", start_seconds=1, end_seconds=3, font_size=40
    )

    assert overlay.text == "hello"
    assert overlay.duration_seconds == 2.0


def test_text_overlay_rejects_end_before_start() -> None:
    with pytest.raises(EffectValidationError, match="End time"):
        TextOverlay(text="hi", start_seconds=5, end_seconds=2)


def test_text_overlay_rejects_empty_text() -> None:
    with pytest.raises(EffectValidationError, match="Overlay text"):
        TextOverlay(text="   ", start_seconds=0, end_seconds=1)


@pytest.mark.parametrize("font_size", [4, 500])
def test_text_overlay_rejects_out_of_range_font_size(font_size: int) -> None:
    with pytest.raises(EffectValidationError, match="Font size"):
        TextOverlay(text="hi", start_seconds=0, end_seconds=1, font_size=font_size)


def test_sound_effect_requires_a_real_looking_path_and_positive_volume() -> None:
    with pytest.raises(EffectValidationError, match="audio path"):
        SoundEffect(audio_path=Path(), start_seconds=0)
    with pytest.raises(EffectValidationError, match="Volume"):
        SoundEffect(audio_path=Path("sfx.wav"), start_seconds=0, volume=0)


def test_effect_plan_orders_overlays_and_sound_effects_by_start_time() -> None:
    late_overlay = TextOverlay(text="late", start_seconds=5, end_seconds=6)
    early_overlay = TextOverlay(text="early", start_seconds=0, end_seconds=1)
    late_sfx = SoundEffect(audio_path=Path("a.wav"), start_seconds=4)
    early_sfx = SoundEffect(audio_path=Path("b.wav"), start_seconds=1)

    plan = EffectPlan(
        overlays=(late_overlay, early_overlay),
        sound_effects=(late_sfx, early_sfx),
    )

    assert plan.overlays == (early_overlay, late_overlay)
    assert plan.sound_effects == (early_sfx, late_sfx)


def test_effect_plan_is_empty_reports_no_effects() -> None:
    assert EffectPlan().is_empty is True
    assert EffectPlan(zoom=ZoomEffect(style=ZoomStyle.NONE)).is_empty is True
    assert EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN)).is_empty is False


def test_effect_request_rejects_matching_input_and_output_paths() -> None:
    video = Path("clip.mp4")
    with pytest.raises(EffectValidationError, match="differ"):
        EffectRequest(input_video=video, output_video=video, plan=EffectPlan())


def test_effect_request_normalizes_clip_duration() -> None:
    request = EffectRequest(
        input_video=Path("in.mp4"),
        output_video=Path("out.mp4"),
        plan=EffectPlan(),
        clip_duration_seconds=10,
    )

    assert request.clip_duration_seconds == 10.0


def test_effect_result_requires_string_labels() -> None:
    with pytest.raises(EffectValidationError, match="Applied"):
        EffectResult(output_video=Path("out.mp4"), applied=(1,))  # type: ignore[arg-type]
