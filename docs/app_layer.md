# Application layer

`content_pipeline.app` is the composition root and delivery mechanism the rest
of the codebase deliberately excludes. Everything here is allowed to read
environment configuration, construct OAuth clients, and choose concrete
adapters; nothing in `core` or `domain` may do those things.

## Modules

| Module | Responsibility |
| --- | --- |
| `app/oauth.py` | Constructs and refreshes an authenticated YouTube Data API client. `run_oauth_login` runs the interactive consent flow once and persists a refreshable token; `build_youtube_client` loads and refreshes that token on later runs; `build_youtube_client_with_api_key` builds a read-only client for public endpoints (the trending chart) without requiring user consent. |
| `app/composition.py` | Builds each `core` service from `Settings`: the channel manager, trend scan service, clip cutting service, metadata provider, and upload service. This is the only place that decides which concrete adapter backs each port. |
| `app/subtitles.py` | Writes a `.srt` file for one clip's slice of a transcript, re-timed to start at zero. Feeds `SubtitleBurner`, which only knows how to burn an existing subtitle file. |
| `app/pipeline.py` | `ContentPipeline.run()` chains clip cutting, optional effects processing, per-clip metadata generation, optional subtitle burn-in, and upload for one local source video. `topic_hint_from_snapshot` is a small convenience for feeding `TrendScanService` output into a run. |
| `app/cli.py` | Operator-facing `argparse` CLI: `oauth-login`, `channels add`/`list`, `trends`, and `run`. Installed as the `content-pipeline` console script and also runnable as `python -m content_pipeline`. |

## Why trend detection isn't chained automatically

`TrendScanService` returns *topics* (what's trending), not footage. Turning a
trending topic into a clip requires source video, which this project
deliberately does not fetch on the operator's behalf (see
`docs/clip_architecture.md`). `topic_hint_from_snapshot` exists so a caller
can pass the top trending topic into `ClipCandidateRequest.topic_hint` for a
video they've already chosen, but picking *which* video to react to a trend
with is left to the operator or a future application-specific module.

## Extending this layer

Add new adapters (a second upload platform, a different transcription
provider, etc.) by writing them beside their existing sibling in `core`, then
adding a `build_*` function to `app/composition.py` that chooses between them.
Do not add environment reads, provider SDK imports, or OAuth logic to `core`
or `domain` — that is what this layer is for.
