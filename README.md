# Content Pipeline Foundation

A production-oriented Python foundation for an AI-powered short-form content system. It includes reusable configuration, logging, errors, models, and utilities, plus channel management, OpenAI-backed metadata generation, FFmpeg subtitle burn-in, and a dependency-injected YouTube upload adapter. OAuth client construction and application-level workflow orchestration remain composition concerns.

## Quick start

1. Install Python 3.12 or newer.
2. Create and activate a virtual environment.
3. Install development dependencies: `python -m pip install -r requirements-dev.txt`.
4. Copy `.env.example` to `.env`, then set deployment values. A production environment requires `APP_SECRET_KEY`.
5. Run tests: `python -m pytest`.

## Layout

```text
src/content_pipeline/
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

## Metadata, captions, and uploads

The canonical, immutable metadata contract is in `content_pipeline.domain.metadata`; its OpenAI adapter generates validated title, description, and hashtags. The provider-neutral caption abstraction lives in `content_pipeline.domain.captions` and `content_pipeline.core.captions`, alongside an FFmpeg subtitle burner. The upload service uses an injected provider; the YouTube adapter performs resumable API uploads with neutral request and response values. See [Metadata](docs/metadata.md), [Caption architecture](docs/caption_architecture.md), and [Upload architecture](docs/upload_architecture.md).

## Engineering standards

All public APIs require type annotations. Keep domain logic framework-free, favor immutable dataclasses for generic values, and use dependency injection through `Protocol`-based ports when external systems are introduced. Add tests with every behavior change. Run `ruff check .`, `mypy`, and `pytest` before merging.

## Dependencies

- `pydantic`: robust runtime validation and typed settings models.
- `pydantic-settings`: environment and `.env` loading for Pydantic.
- `python-dotenv`: explicit, standard `.env` support requested for local configuration.
- `openai`: metadata generation through the injected OpenAI client boundary.
- `google-api-python-client`: YouTube Data API communication in the YouTube provider only.
- Development-only: `pytest`/`pytest-cov` for tests, `ruff` for linting, and `mypy` for static type checking.

No web framework, database, queue, worker, analytics system, or orchestration engine is included. Adding one must preserve the existing domain and provider boundaries.
