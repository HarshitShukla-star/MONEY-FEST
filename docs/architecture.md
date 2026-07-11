# Locked architecture

This is the authoritative architecture for the repository. The top-level folders and the `src/content_pipeline` package layout are locked: future work must not rename, move, or repurpose them. New code belongs in the existing boundary described below. A new package is permitted only as a child of the assigned existing boundary when a cohesive module needs more than one file.

## Dependency direction

Dependencies must point toward stable policy:

```text
config, logging, utils, and future delivery code
                    |
                    v
                 core
                    |
                    v
                 domain
                    |
                    v
               exceptions
```

`domain` must never import `core`, `config`, `logging`, `utils`, a framework, or an external service SDK. `core` may orchestrate domain objects and depend on configuration or logging interfaces. `config`, `logging`, and `utils` are cross-cutting facilities; they may depend on `exceptions`, but must not depend on `core` or `domain` workflows. Avoid imports between sibling feature modules.

## Repository folders

| Location | Responsibility | Future code belongs here when |
| --- | --- | --- |
| `src/content_pipeline/` | The importable application package and deliberately small public API. | Exporting only stable, high-level public types. Do not import feature implementations here merely for convenience. |
| `src/content_pipeline/core/` | Application use cases, orchestration, dependency wiring, and consumer-owned `Protocol` ports. | A workflow coordinates domain models or calls a dependency. Place a single use case in a module here; use a child package only when the use case family is cohesive. Provider adapters live beside the consumer-owned port in a clearly named implementation module until a dedicated existing boundary is introduced by an explicitly approved architecture change. |
| `src/content_pipeline/domain/` | Framework-independent business concepts and rules. | The code expresses a durable business invariant, entity, value object, or policy with no I/O. |
| `src/content_pipeline/domain/models/` | Generic domain value and response models. | A reusable, framework-independent model is shared by more than one domain or core module. Product-specific models should live next to their owning core use case instead. |
| `src/content_pipeline/config/` | Environment-backed configuration and startup validation. | Adding typed settings, configuration parsing, or validation. Do not read environment variables anywhere else. |
| `src/content_pipeline/logging/` | Logging configuration and formatters. | Adding log handlers, formatters, filters, or logging-safe context helpers. Do not call `print()`. |
| `src/content_pipeline/exceptions/` | Stable hierarchy for expected application failures. | Adding a reusable application error class. Preserve inheritance so callers can catch the correct category. |
| `src/content_pipeline/utils/` | Small generic helpers with tightly bounded side effects. | A helper is domain-neutral, independently testable, and does not orchestrate a workflow. Do not place business rules here. |
| `tests/` | Behavioural and regression tests mirroring source responsibility by filename. | Every changed behaviour needs a focused test. Tests may import public or internal package APIs but must not become production helpers. |
| `docs/` | Maintained architectural and developer documentation. | A decision, boundary, operational convention, or developer workflow requires durable explanation. |
| `scripts/` | Explicit command-line operational or developer automation. | An action must be repeatable outside application runtime. Scripts use shared settings and logging. |
| `assets/` | Checked-in static assets required by the application. | The asset is non-secret, non-user-generated, and required at runtime or build time. |

## Module rules

- Use absolute imports rooted at `content_pipeline`.
- Public functions, methods, and module-level constants require complete type annotations. Public return types must be explicit.
- Use immutable dataclasses for domain values unless mutability is an intentional business requirement.
- A `core` use case owns the protocol for a service it consumes. Inject its implementation at the composition point; do not instantiate remote clients in domain code.
- Keep I/O at the outer edge. File, network, database, queue, and provider interactions must not leak into domain models.
- Add generic errors to `exceptions`; translate provider/library exceptions at the core boundary and chain the original exception with `raise ... from exc`.
- Load `Settings` through `get_settings()` at startup, validate there, and never log `SecretStr` values.
- Configure logging once at startup with `configure_logging()`. Use `get_logger(__name__)` and pass operational fields through `extra`; JSON logs retain those values under `context`.
- Do not add a web framework, database library, provider SDK, queue, or AI dependency until a concrete use case requires it and its placement is documented.

## Quality gate

Every change must pass the following from the repository root:

```text
python -m pytest -p no:cacheprovider
python -m ruff check .
python -m mypy
```

The test cache provider is disabled in the command above only because this workspace currently has a local cache-path collision; it is not an application constraint.
