# Trend detection

The independent trend detection contract resides in `content_pipeline.domain.trends`
and `content_pipeline.core.trends`. It owns scoring and ranking of trend signals
only; it contains no source-fetching, clip-cutting, or upload behaviour.

## Domain contract

- `TrendSource` — a closed enum of signal origins (`youtube`, `reddit`, `google_trends`).
- `TrendCandidate` — an immutable, validated scored signal (topic, source, score,
  observed time, optional external id, provider-specific details).
- `TrendSnapshot` — an immutable, score-ranked collection of candidates from one scan,
  with a `top(limit)` accessor.

## Providers

`TrendProvider` is a `Protocol` with a single `fetch(*, limit)` method. Adapters
implement it against one signal source:

- `YouTubeTrendProvider` — wraps the YouTube Data API `videos.list(chart="mostPopular")`
  call using an injected, already-authenticated client (constructor injection only;
  this module performs no OAuth flow construction, matching the upload provider's
  pattern).

Add a Reddit or Google Trends adapter the same way: implement `TrendProvider.fetch`,
map the source-specific response into `TrendCandidate` values, and raise
`ProviderError` / `AuthenticationError` from `content_pipeline.exceptions` for
failure cases — never leak the underlying client's exception types.

## Service

`TrendScanService` fans out to one or more injected providers and merges their
results into a single ranked `TrendSnapshot`. A single provider failing is logged
and skipped rather than aborting the whole scan, so one flaky signal source does not
block trend detection for a channel.

## Extension rules

- New providers must not import from `core.trends.service` or from other pipeline
  stages (clipping, captions, uploads) — keep this module a leaf dependency.
- Scoring normalization belongs in `domain/trends/validation.py`; do not embed
  provider-specific scoring heuristics in `domain` models.
- Add tests with every behavior change, mocking the injected client surface the
  same way `tests/test_youtube_trend_provider.py` does — no live network calls.
