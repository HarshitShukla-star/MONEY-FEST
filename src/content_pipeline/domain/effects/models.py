"""Immutable, provider-neutral values for post-cut visual and audio effects."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from content_pipeline.domain.effects.exceptions import EffectValidationError
from content_pipeline.domain.effects.validation import (
    normalize_font_size,
    normalize_intensity,
    normalize_overlay_text,
    normalize_positive_number,
    normalize_time_range,
    normalize_timestamp,
)


class ZoomStyle(StrEnum):
    """A Ken-Burns-style zoom or pan applied across a clip's full duration."""

    NONE = "none"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"


class TransitionStyle(StrEnum):
    """A fade transition applied at a clip's edges."""

    NONE = "none"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    FADE_IN_OUT = "fade_in_out"


class TextPosition(StrEnum):
    """Vertical placement for a text overlay."""

    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


@dataclass(frozen=True, slots=True)
class ZoomEffect:
    """A Ken-Burns-style zoom or pan, at a given intensity in (0, 1]."""

    style: ZoomStyle
    intensity: float = 0.15

    def __post_init__(self) -> None:
        if not isinstance(self.style, ZoomStyle):
            raise EffectValidationError("Zoom style must be a ZoomStyle")
        object.__setattr__(self, "intensity", normalize_intensity(self.intensity))


@dataclass(frozen=True, slots=True)
class TransitionEffect:
    """A fade-in, fade-out, or both, each lasting ``duration_seconds``."""

    style: TransitionStyle
    duration_seconds: float = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.style, TransitionStyle):
            raise EffectValidationError("Transition style must be a TransitionStyle")
        object.__setattr__(
            self,
            "duration_seconds",
            normalize_positive_number(self.duration_seconds, "Transition duration"),
        )


@dataclass(frozen=True, slots=True)
class TextOverlay:
    """A timed text caption burned into the video at a fixed screen position."""

    text: str
    start_seconds: float
    end_seconds: float
    position: TextPosition = TextPosition.BOTTOM
    font_size: int = 42

    def __post_init__(self) -> None:
        start, end = normalize_time_range(self.start_seconds, self.end_seconds)
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "text", normalize_overlay_text(self.text))
        if not isinstance(self.position, TextPosition):
            raise EffectValidationError("Position must be a TextPosition")
        object.__setattr__(self, "font_size", normalize_font_size(self.font_size))

    @property
    def duration_seconds(self) -> float:
        """Return how long the overlay stays on screen, in seconds."""
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True, slots=True)
class SoundEffect:
    """A local audio file mixed in at a fixed offset within the video's timeline.

    Like clip cutting's source video, the audio file must already be present
    on disk and supplied by the caller (a sound-effect library the operator
    controls the rights to); this module never fetches audio from a network
    source.
    """

    audio_path: Path
    start_seconds: float
    volume: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.audio_path, Path) or self.audio_path == Path("."):
            raise EffectValidationError(
                "Sound effect audio path must be a non-empty file path"
            )
        object.__setattr__(
            self, "start_seconds", normalize_timestamp(self.start_seconds, "Start time")
        )
        object.__setattr__(
            self, "volume", normalize_positive_number(self.volume, "Volume")
        )


@dataclass(frozen=True, slots=True)
class EffectPlan:
    """An immutable bundle of effects to apply to one cut clip."""

    zoom: ZoomEffect | None = None
    transition: TransitionEffect | None = None
    overlays: tuple[TextOverlay, ...] = ()
    sound_effects: tuple[SoundEffect, ...] = ()

    def __post_init__(self) -> None:
        if self.zoom is not None and not isinstance(self.zoom, ZoomEffect):
            raise EffectValidationError("Zoom must be a ZoomEffect or None")
        if self.transition is not None and not isinstance(
            self.transition, TransitionEffect
        ):
            raise EffectValidationError("Transition must be a TransitionEffect or None")
        if not isinstance(self.overlays, tuple) or not all(
            isinstance(item, TextOverlay) for item in self.overlays
        ):
            raise EffectValidationError(
                "Overlays must be a tuple of TextOverlay values"
            )
        if not isinstance(self.sound_effects, tuple) or not all(
            isinstance(item, SoundEffect) for item in self.sound_effects
        ):
            raise EffectValidationError(
                "Sound effects must be a tuple of SoundEffect values"
            )
        object.__setattr__(
            self,
            "overlays",
            tuple(sorted(self.overlays, key=lambda item: item.start_seconds)),
        )
        object.__setattr__(
            self,
            "sound_effects",
            tuple(sorted(self.sound_effects, key=lambda item: item.start_seconds)),
        )

    @property
    def is_empty(self) -> bool:
        """Return whether this plan has no effects to apply at all."""
        no_transition = (
            self.transition is None or self.transition.style is TransitionStyle.NONE
        )
        return (
            (self.zoom is None or self.zoom.style is ZoomStyle.NONE)
            and no_transition
            and not self.overlays
            and not self.sound_effects
        )


@dataclass(frozen=True, slots=True)
class EffectRequest:
    """A request to apply one effect plan to a local input video."""

    input_video: Path
    output_video: Path
    plan: EffectPlan
    clip_duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.input_video, Path) or self.input_video == Path("."):
            raise EffectValidationError("Input video must be a non-empty file path")
        if not isinstance(self.output_video, Path) or self.output_video == Path("."):
            raise EffectValidationError("Output video must be a non-empty file path")
        if self.output_video == self.input_video:
            raise EffectValidationError("Output video must differ from the input video")
        if not isinstance(self.plan, EffectPlan):
            raise EffectValidationError("Plan must be an EffectPlan")
        if self.clip_duration_seconds is not None:
            object.__setattr__(
                self,
                "clip_duration_seconds",
                normalize_positive_number(
                    self.clip_duration_seconds, "Clip duration"
                ),
            )


@dataclass(frozen=True, slots=True)
class EffectResult:
    """The normalized outcome of applying one effect plan to a video."""

    output_video: Path
    applied: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.output_video, Path) or self.output_video == Path("."):
            raise EffectValidationError("Output video must be a non-empty file path")
        if not isinstance(self.applied, tuple) or not all(
            isinstance(item, str) for item in self.applied
        ):
            raise EffectValidationError("Applied must be a tuple of strings")
