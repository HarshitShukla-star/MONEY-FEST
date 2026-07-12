# Content Pipeline

A production-oriented Python system for an AI-powered short-form content pipeline. It includes reusable configuration, logging, errors, models, and utilities, plus channel management, OpenAI-backed metadata generation, FFmpeg subtitle burn-in, transcript-driven clip cutting, FFmpeg-backed zoom/pan/transition/overlay/SFX effects, a dependency-injected YouTube upload adapter, and an `app` delivery layer that wires everything into a runnable CLI, complete with YouTube OAuth client construction and end-to-end workflow orchestration.

## Quick start

1. Install Python 3.12 or newer.
2. Create and activate a virtual environment.
3. Install development dependencies: `python -m pip install -r requirements-dev.txt`.
4. Copy `.env.example` to `.env`, then set deployment values. A production environment requires `APP_SECRET_KEY`. Set `OPENAI_API_KEY` to cut clips and generate metadata. Set `YOUTUBE_OAUTH_CLIENT_SECRETS_PATH` and `YOUTUBE_OAUTH_TOKEN_PATH` to upload to YouTube.
5. Run tests: `python -m pytest`.
6. Install the package to get the `content-pipeline` command: `python -m pip install -e .`.

## Running the pipeline

```bash
# One-time: register a Google Cloud OAuth client (Desktop app type), download
# its client secrets JSON, and point YOUTUBE_OAUTH_CLIENT_SECRETS_PATH at it.
content-pipeline oauth-login

# Register a destination channel.
content-pipeline channels add --name "My Channel" --platform youtube --set-default

# See what's trending (uses an API key if supplied, otherwise the OAuth token).
content-pipeline trends --limit 10

# Cut clips from a local video, generate metadata, and upload them.
content-pipeline run \
  --source-video ./footage/episode-12.mp4 \
  --channel-id <channel-id-from-channels-list> \
  --output-dir ./out \
  --max-clips 3 \
  --visibility unlisted \
  --zoom zoom_in --zoom-intensity 0.2 \
  --transition fade_in_out --transition-duration 0.5 \
  --dry-run   # drop this flag once you're happy with the metadata/clips
```

`python -m content_pipeline` works the same way if the package isn't installed as a console script. See [Application layer](docs/app_layer.md) for how the CLI, OAuth client construction, and `ContentPipeline` orchestrator fit together.

## Layout

```text
src/content_pipeline/
  app/          composition root: OAuth client construction, service wiring, CLI, orchestration
  config/       validated environment configuration
  core/         composition and shared abstractions
  domain/models generic framework-independent contracts
  exceptions/   application error hierarchy
  logging/      structured logging configuration
  utils/        generic file, JSON, time, and validation helpers
tests/          executable specifications
docs/           architecture and development guidance
scripts/        operational automation (when needed)
assets/         checked-in static assets (when needed)
```

## Configuration and logging

`Settings` loads `.env` and environment variables through Pydantic Settings. Environment values take precedence, configuration is validated at startup, and invalid configuration is surfaced as `ConfigurationError` when loaded through `get_settings()`.

Configure logging at the composition root with `configure_logging(settings.log_level, settings.log_format)`. JSON is the default format for production-friendly log ingestion; text is available for local development. Use `get_logger(__name__)` instead of `print()`.

## Channel management

The independent Channel Manager resides in `content_pipeline.core.channels`. It owns publishing-destination records and JSON persistence only; it contains no upload, network, OAuth, AI, API, or authentication behaviour. See [Channel Manager](docs/channel_manager.md) for its contract and extension rules.

## Metadata, captions, effects, uploads, and orchestration

The canonical, immutable metadata contract is in `content_pipeline.domain.metadata`; its OpenAI adapter generates validated title, description, and hashtags. The provider-neutral caption abstraction lives in `content_pipeline.domain.captions` and `content_pipeline.core.captions`, alongside an FFmpeg subtitle burner. The provider-neutral effects abstraction lives in `content_pipeline.domain.effects` and `content_pipeline.core.effects`: zoom/pan, fade transitions, timed text overlays, and sound-effect mixing for an already-cut clip, applied with FFmpeg through the same injected-runner pattern as clip cutting and subtitle burn-in. The upload service uses an injected provider; the YouTube adapter performs resumable API uploads with neutral request and response values. `content_pipeline.app` is the composition root that builds concrete adapters from `Settings`, constructs and refreshes the YouTube OAuth client, and chains clip cutting, optional effects processing, metadata generation, optional subtitle burn-in, and upload into one operator-facing `ContentPipeline.run()`. See [Metadata](docs/metadata.md), [Caption architecture](docs/caption_architecture.md), [Effects architecture](docs/effects_architecture.md), [Upload architecture](docs/upload_architecture.md), and [Application layer](docs/app_layer.md).

## Engineering standards

All public APIs require type annotations. Keep domain logic framework-free, favor immutable dataclasses for generic values, and use dependency injection through `Protocol`-based ports when external systems are introduced. Add tests with every behavior change. Run `ruff check .`, `mypy`, and `pytest` before merging.

## Dependencies

- `pydantic`: robust runtime validation and typed settings models.
- `pydantic-settings`: environment and `.env` loading for Pydantic.
- `python-dotenv`: explicit, standard `.env` support requested for local configuration.
- `openai`: metadata generation through the injected OpenAI client boundary.
- `google-api-python-client`: YouTube Data API communication in the YouTube provider only.
- `google-auth-oauthlib`: interactive OAuth consent flow and token refresh, confined to `content_pipeline.app.oauth`.
- Development-only: `pytest`/`pytest-cov` for tests, `ruff` for linting, and `mypy` for static type checking.

No web framework, database, queue, worker, or analytics system is included. Adding one must preserve the existing domain and provider boundaries.

