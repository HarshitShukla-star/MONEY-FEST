"""Pure FFmpeg filter-graph construction for visual/audio effects (no I/O).

Kept separate from ``processor.py`` so the graph-building logic can be
tested as plain string construction, the same way the pipeline's other
FFmpeg-backed stages separate command assembly from process execution.
"""

from dataclasses import dataclass
from pathlib import Path

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

_ZOOM_STEP_PER_INTENSITY = 0.0012
_MAX_ZOOM_GAIN_PER_INTENSITY = 0.5
_PAN_STEP_PER_INTENSITY = 0.0018
_PAN_ZOOM_LEVEL = 1.15

_TEXT_Y_BY_POSITION = {
    TextPosition.TOP: "40",
    TextPosition.CENTER: "(h-text_h)/2",
    TextPosition.BOTTOM: "h-text_h-40",
}


@dataclass(frozen=True, slots=True)
class FilterGraph:
    """An FFmpeg ``-filter_complex`` graph plus the inputs/maps it requires."""

    filter_complex: str | None
    video_map: str | None
    audio_map: str | None
    extra_audio_inputs: tuple[Path, ...]


def build_filter_graph(
    plan: EffectPlan, *, clip_duration_seconds: float | None
) -> FilterGraph:
    """Build the full FFmpeg filter graph needed to apply one effect plan."""
    video_filters = _video_filters(plan, clip_duration_seconds)
    parts: list[str] = []
    if video_filters:
        parts.append(f"[0:v]{','.join(video_filters)}[vout]")
    audio_map: str | None = None
    if plan.sound_effects:
        parts.append(_audio_mix_filter(plan.sound_effects))
        audio_map = "[aout]"
    return FilterGraph(
        filter_complex=";".join(parts) if parts else None,
        video_map="[vout]" if video_filters else None,
        audio_map=audio_map,
        extra_audio_inputs=tuple(item.audio_path for item in plan.sound_effects),
    )


def applied_labels(plan: EffectPlan) -> tuple[str, ...]:
    """Return human-readable labels describing every effect a plan applies."""
    labels: list[str] = []
    if plan.zoom is not None and plan.zoom.style is not ZoomStyle.NONE:
        labels.append(f"zoom:{plan.zoom.style.value}")
    if (
        plan.transition is not None
        and plan.transition.style is not TransitionStyle.NONE
    ):
        labels.append(f"transition:{plan.transition.style.value}")
    labels.extend(
        f"overlay:{item.start_seconds:.2f}-{item.end_seconds:.2f}"
        for item in plan.overlays
    )
    labels.extend(f"sfx:{item.start_seconds:.2f}" for item in plan.sound_effects)
    return tuple(labels)


def _video_filters(
    plan: EffectPlan, clip_duration_seconds: float | None
) -> list[str]:
    filters: list[str] = []
    if plan.zoom is not None and plan.zoom.style is not ZoomStyle.NONE:
        filters.append(_zoom_filter(plan.zoom))
    if (
        plan.transition is not None
        and plan.transition.style is not TransitionStyle.NONE
    ):
        filters.extend(_transition_filters(plan.transition, clip_duration_seconds))
    filters.extend(_drawtext_filter(item) for item in plan.overlays)
    return filters


def _zoom_filter(zoom: ZoomEffect) -> str:
    step = _ZOOM_STEP_PER_INTENSITY * zoom.intensity
    max_zoom = 1.0 + _MAX_ZOOM_GAIN_PER_INTENSITY * zoom.intensity
    pan_step = _PAN_STEP_PER_INTENSITY * zoom.intensity
    if zoom.style is ZoomStyle.ZOOM_IN:
        zoom_expr = f"min(zoom+{step:.5f},{max_zoom:.4f})"
        x_expr, y_expr = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif zoom.style is ZoomStyle.ZOOM_OUT:
        zoom_expr = f"if(eq(on,1),{max_zoom:.4f},max(1.001,zoom-{step:.5f}))"
        x_expr, y_expr = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif zoom.style is ZoomStyle.PAN_LEFT:
        zoom_expr = f"{_PAN_ZOOM_LEVEL:.2f}"
        x_expr = f"max(0,(iw-iw/zoom)/2-on*{pan_step:.5f}*iw)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif zoom.style is ZoomStyle.PAN_RIGHT:
        zoom_expr = f"{_PAN_ZOOM_LEVEL:.2f}"
        x_expr = f"min(iw-iw/zoom,(iw-iw/zoom)/2+on*{pan_step:.5f}*iw)"
        y_expr = "ih/2-(ih/zoom/2)"
    else:  # pragma: no cover - EffectPlan never builds a NONE zoom filter
        raise EffectValidationError(f"Unsupported zoom style: {zoom.style}")
    return f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d=1:s=1280x720"


def _transition_filters(
    transition: TransitionEffect, clip_duration_seconds: float | None
) -> list[str]:
    duration = transition.duration_seconds
    filters: list[str] = []
    if transition.style in (TransitionStyle.FADE_IN, TransitionStyle.FADE_IN_OUT):
        filters.append(f"fade=t=in:st=0:d={duration:.3f}")
    if transition.style in (TransitionStyle.FADE_OUT, TransitionStyle.FADE_IN_OUT):
        if clip_duration_seconds is None:
            raise EffectValidationError(
                "Clip duration is required to place a fade-out transition"
            )
        if clip_duration_seconds <= duration:
            raise EffectValidationError(
                "Clip duration must be longer than the fade-out duration"
            )
        start = clip_duration_seconds - duration
        filters.append(f"fade=t=out:st={start:.3f}:d={duration:.3f}")
    return filters


def _drawtext_filter(overlay: TextOverlay) -> str:
    text = _escape_drawtext(overlay.text)
    y_expr = _TEXT_Y_BY_POSITION[overlay.position]
    return (
        f"drawtext=text='{text}':fontsize={overlay.font_size}:fontcolor=white:"
        f"borderw=2:bordercolor=black@0.8:x=(w-text_w)/2:y={y_expr}:"
        f"enable='between(t,{overlay.start_seconds:.3f},{overlay.end_seconds:.3f})'"
    )


def _escape_drawtext(text: str) -> str:
    """Escape a caption for FFmpeg's drawtext filter argument syntax."""
    escaped = text.replace("\\", "\\\\")
    for character in ("'", ":", "%", ","):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _audio_mix_filter(sound_effects: tuple[SoundEffect, ...]) -> str:
    labels: list[str] = []
    parts: list[str] = []
    for index, effect in enumerate(sound_effects, start=1):
        delay_ms = round(effect.start_seconds * 1000)
        label = f"sfx{index}"
        parts.append(
            f"[{index}:a]adelay={delay_ms}|{delay_ms},volume={effect.volume:.3f}"
            f"[{label}]"
        )
        labels.append(f"[{label}]")
    mix_inputs = "[0:a]" + "".join(labels)
    parts.append(
        f"{mix_inputs}amix=inputs={len(sound_effects) + 1}:"
        "duration=first:dropout_transition=0[aout]"
    )
    return ";".join(parts)
