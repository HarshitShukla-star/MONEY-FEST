"""Tests for pure FFmpeg filter-graph construction (no subprocess involved)."""

from pathlib import Path

import pytest

from content_pipeline.core.effects.filters import applied_labels, build_filter_graph
from content_pipeline.domain.effects import (
    EffectPlan,
    EffectValidationError,
    SoundEffect,
    TextOverlay,
    TextPosition,
    TransitionEffect,
    TransitionStyle,
    ZoomEffect,
    ZoomStyle,
)


def test_zoom_in_builds_a_zoompan_filter_with_no_audio_map() -> None:
    plan = EffectPlan(zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN, intensity=0.2))

    graph = build_filter_graph(plan, clip_duration_seconds=None)

    assert graph.video_map == "[vout]"
    assert graph.audio_map is None
    assert graph.extra_audio_inputs == ()
    assert graph.filter_complex is not None
    assert "[0:v]zoompan=" in graph.filter_complex
    assert graph.filter_complex.endswith("[vout]")


@pytest.mark.parametrize(
    "style", [ZoomStyle.ZOOM_OUT, ZoomStyle.PAN_LEFT, ZoomStyle.PAN_RIGHT]
)
def test_every_zoom_style_produces_a_zoompan_filter(style: ZoomStyle) -> None:
    plan = EffectPlan(zoom=ZoomEffect(style=style))

    graph = build_filter_graph(plan, clip_duration_seconds=None)

    assert graph.filter_complex is not None
    assert "zoompan=" in graph.filter_complex


def test_zoom_none_produces_no_video_filter() -> None:
    plan = EffectPlan(zoom=ZoomEffect(style=ZoomStyle.NONE))

    graph = build_filter_graph(plan, clip_duration_seconds=None)

    assert graph.video_map is None
    assert graph.filter_complex is None


def test_fade_in_out_requires_clip_duration_for_the_fade_out_half() -> None:
    plan = EffectPlan(
        transition=TransitionEffect(
            style=TransitionStyle.FADE_IN_OUT, duration_seconds=1
        )
    )

    with pytest.raises(EffectValidationError, match="Clip duration is required"):
        build_filter_graph(plan, clip_duration_seconds=None)


def test_fade_in_out_rejects_a_clip_shorter_than_the_fade() -> None:
    plan = EffectPlan(
        transition=TransitionEffect(
            style=TransitionStyle.FADE_IN_OUT, duration_seconds=5
        )
    )

    with pytest.raises(EffectValidationError, match="longer than"):
        build_filter_graph(plan, clip_duration_seconds=3)


def test_fade_in_out_builds_both_fade_filters_in_order() -> None:
    plan = EffectPlan(
        transition=TransitionEffect(
            style=TransitionStyle.FADE_IN_OUT, duration_seconds=1
        )
    )

    graph = build_filter_graph(plan, clip_duration_seconds=10)

    assert graph.filter_complex is not None
    assert "fade=t=in:st=0:d=1.000" in graph.filter_complex
    assert "fade=t=out:st=9.000:d=1.000" in graph.filter_complex


def test_overlay_builds_a_drawtext_filter_with_escaped_text() -> None:
    plan = EffectPlan(
        overlays=(
            TextOverlay(
                text="it's: 100%",
                start_seconds=1,
                end_seconds=2,
                position=TextPosition.TOP,
            ),
        )
    )

    graph = build_filter_graph(plan, clip_duration_seconds=None)

    assert graph.filter_complex is not None
    assert "drawtext=text='it\\'s\\: 100\\%'" in graph.filter_complex
    assert "enable='between(t,1.000,2.000)'" in graph.filter_complex


def test_sound_effects_build_an_amix_graph_with_delayed_inputs() -> None:
    plan = EffectPlan(
        sound_effects=(
            SoundEffect(audio_path=Path("ding.wav"), start_seconds=1, volume=0.5),
            SoundEffect(audio_path=Path("whoosh.wav"), start_seconds=2),
        )
    )

    graph = build_filter_graph(plan, clip_duration_seconds=None)

    assert graph.audio_map == "[aout]"
    assert graph.extra_audio_inputs == (Path("ding.wav"), Path("whoosh.wav"))
    assert graph.filter_complex is not None
    assert "[1:a]adelay=1000|1000,volume=0.500[sfx1]" in graph.filter_complex
    assert "[2:a]adelay=2000|2000,volume=1.000[sfx2]" in graph.filter_complex
    assert "[0:a][sfx1][sfx2]amix=inputs=3:duration=first" in graph.filter_complex


def test_zoom_and_sound_effects_combine_into_one_graph_with_both_maps() -> None:
    plan = EffectPlan(
        zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN),
        sound_effects=(SoundEffect(audio_path=Path("a.wav"), start_seconds=0),),
    )

    graph = build_filter_graph(plan, clip_duration_seconds=None)

    assert graph.video_map == "[vout]"
    assert graph.audio_map == "[aout]"
    assert graph.filter_complex is not None
    assert "[0:v]zoompan=" in graph.filter_complex
    assert graph.filter_complex.endswith("[aout]")


def test_applied_labels_describes_every_effect_in_a_plan() -> None:
    plan = EffectPlan(
        zoom=ZoomEffect(style=ZoomStyle.ZOOM_IN),
        transition=TransitionEffect(style=TransitionStyle.FADE_IN),
        overlays=(TextOverlay(text="hi", start_seconds=0, end_seconds=1),),
        sound_effects=(SoundEffect(audio_path=Path("a.wav"), start_seconds=2),),
    )

    labels = applied_labels(plan)

    assert labels == (
        "zoom:zoom_in",
        "transition:fade_in",
        "overlay:0.00-1.00",
        "sfx:2.00",
    )


def test_applied_labels_is_empty_for_an_empty_plan() -> None:
    assert applied_labels(EffectPlan()) == ()
