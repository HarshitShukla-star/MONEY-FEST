# Clip cutting

The independent clip-cutting contract resides in `content_pipeline.domain.clips`
and `content_pipeline.core.clips`. It owns transcript-driven clip selection and
FFmpeg-based extraction only; it contains no source-fetching, effects, upload,
or OAuth behaviour.

**This module operates only on a local source video file already present on
disk.** It never fetches, downloads, or scrapes video content from any
network source itself. The source video must be supplied by the caller — for
example, the operator's own footage, or footage obtained under an appropriate
license. This boundary is intentional and must not be weakened by adding a
network-fetching adapter here or upstream of this module.

## Domain contract

- `TranscriptSegment` — an immutable, validated timed span of speech (start,
  end, text).
- `Transcript` — an immutable, time-ordered, non-overlapping collection of
  segments for one source video, bounded by the source's total duration, with
  a `text_between(start, end)` accessor.
- `ClipCandidateRequest` — bounds and hints passed to a selector (maximum clip
  count, minimum/maximum clip duration, optional topic hint).
- `ClipSelection` — an immutable, validated candidate clip time range with a
  title, rationale, and score in `[0, 1]`, not yet cut from any file.
- `ClipPlan` — an immutable, score-ranked collection of selections from one
  planning pass.
- `CutRequest` / `CutResult` — the request to materialize one selection from a
  local source video, and the normalized outcome of doing so.

## Providers

Two `Protocol` ports, each with one adapter:

- `TranscriptionProvider.transcribe(source_video)` — `WhisperTranscriptionProvider`
  wraps the OpenAI Whisper transcription endpoint using an injected, already
  constructed client (constructor injection only, matching the metadata and
  upload providers' pattern) and validates the response into a `Transcript`.
- `SegmentSelector.select(transcript, request)` — `OpenAISegmentSelector` asks
  an OpenAI chat model to choose candidate clips from a transcript and
  validates every returned timestamp against the transcript's own duration
  before constructing `ClipSelection` values.

Add a different transcription or selection backend the same way: implement the
relevant `Protocol`, map the adapter's response into the neutral domain
values, and raise `ProviderError` (or a more specific subclass) from
`content_pipeline.exceptions` for failure cases — never leak the underlying
SDK's exception types.

## Cutting

`ClipCutter` shells out to FFmpeg (no shell, argument list only) to copy the
requested time range out of the source video, following the same
injected-runner and path-validation pattern as `SubtitleBurner`. It refuses to
overwrite an existing output file and validates the destination directory
before running FFmpeg.

## Service

`ClipCuttingService` coordinates the two providers and the cutter:

- `plan(source_video, request)` — transcribes a local file and asks the
  selector for a `ClipPlan`; raises `ClipSelectionError` if the plan is empty.
- `cut_all(source_video, plan, output_directory)` — materializes every
  selection in a plan into numbered files in an existing output directory.

## Extension rules

- New providers must not import from `core.clips.service` or from other
  pipeline stages (trends, captions, uploads) — keep this module a leaf
  dependency.
- Do not add any adapter to this module (or a new module it depends on) that
  fetches video content over the network from a source the caller does not
  already control the rights to. Source acquisition is explicitly out of
  scope here.
- Time-range and score normalization belongs in `domain/clips/validation.py`;
  do not embed provider-specific heuristics in `domain` models.
- Add tests with every behavior change, mocking the injected client or
  runner surface the same way `tests/test_whisper_transcription_provider.py`,
  `tests/test_openai_segment_selector.py`, and `tests/test_clip_cutter.py` do —
  no live network calls and no real FFmpeg invocation.
