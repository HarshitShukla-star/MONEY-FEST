# Visual and audio effects

The independent effects contract resides in `content_pipeline.domain.effects`
and `content_pipeline.core.effects`. It owns zoom/pan ("Ken Burns"), fade
transitions, timed text overlays, and sound-effect mixing for an already-cut
local clip; it contains no source-fetching, transcription, upload, or OAuth
behaviour.

**This module operates only on local files already present on disk** — the
input video, and any sound-effect audio referenced by a plan. It never
fetches media from a network source itself. This mirrors the boundary
documented in `docs/clip_architecture.md`: source acquisition stays out of
scope everywhere in this pipeline, not just in clip cutting.

## Domain contract

- `ZoomStyle` — `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, or `none`.
- `TransitionStyle` — `fade_in`, `fade_out`, `fade_in_out`, or `none`.
- `TextPosition` — `top`, `center`, `bottom`.
- `ZoomEffect` — a zoom/pan style with an intensity in `(0, 1]`.
- `TransitionEffect` — a fade style with a duration in seconds.
- `TextOverlay` — an immutable, validated timed caption with a screen
  position and font size.
- `SoundEffect` — a local audio file, an offset in seconds, and a volume
  multiplier. Like the source video in clip cutting, the audio file must
  already be on disk and supplied by the caller.
- `EffectPlan` — an immutable bundle of at most one zoom, at most one
  transition, and any number of overlays and sound effects, order-normalized
  by start time. `EffectPlan.is_empty` reports whether a plan has nothing to
  apply.
- `EffectRequest` / `EffectResult` — the request to apply one plan to a local
  input video, and the normalized outcome of doing so.

## Core layer

- `content_pipeline.core.effects.filters` builds the FFmpeg filter graph as
  pure string construction, with no subprocess involved — the same
  separation `ClipCutter` and `SubtitleBurner` use between command assembly
  and process execution. `build_filter_graph` returns a `FilterGraph` with
  the `-filter_complex` string plus the video/audio stream maps and any
  extra sound-effect inputs the command needs; `applied_labels` returns a
  human-readable summary of what a plan will do.
- `VideoEffectsProcessor.apply(request)` shells out to FFmpeg (no shell,
  argument list only) using that filter graph, following the same
  injected-runner and path-validation pattern as `ClipCutter` and
  `SubtitleBurner`. It refuses to overwrite an existing output file,
  validates the destination directory, and requires every sound-effect
  audio file to already exist.

## Application layer

`ContentPipeline` (in `content_pipeline.app.pipeline`) applies an optional
`EffectPlan` to every cut clip, before subtitle burn-in and before upload.
Effects run before subtitles so a zoom/pan crop never clips a caption that
hasn't been burned in yet. Passing no plan (`PipelineRunRequest.effects_plan
= None`, the default) skips this step entirely — a plan is required for the
processor to do anything, so a clip with no plan is never re-encoded.

The CLI (`content-pipeline run`) exposes `--zoom`, `--zoom-intensity`,
`--transition`, and `--transition-duration` for the common case. Overlays and
sound effects don't have CLI flags yet (per-clip timed text and library
paths don't reduce well to trivial flags); build an `EffectPlan` directly
and pass it to `ContentPipeline.run()` when you need them.

## Extension rules

- New filter types belong in `core/effects/filters.py` as another pure
  string-building function; keep `VideoEffectsProcessor` itself limited to
  command assembly and process execution.
- Do not add any adapter to this module (or a new module it depends on) that
  fetches video or audio content over the network. Source acquisition is
  explicitly out of scope here, the same as in clip cutting.
- Time-range, intensity, and text validation belongs in
  `domain/effects/validation.py`; do not embed FFmpeg-specific heuristics in
  `domain` models.
- Add tests with every behavior change: filter-graph construction should be
  tested as plain string assertions (`tests/test_effects_filters.py`), and
  command assembly should mock the injected runner the same way
  `tests/test_effects_processor.py`, `tests/test_clip_cutter.py`, and
  `tests/test_subtitle_burner.py` do — no live network calls and no real
  FFmpeg invocation.
