# Metadata module

`content_pipeline.domain.metadata` is the canonical, framework-free contract for content metadata. Caption, upload, workflow, analytics, rendering, and publishing code should consume this value rather than introduce incompatible metadata shapes.

## Architecture

The module is a child of the existing `domain` boundary. It has four deliberately separate concerns:

- `models.py` defines immutable `Metadata` and `PlatformMetadata` values.
- `validation.py` owns normalization, invariant checks, and the optional application-owned `CategoryRegistry`.
- `serialization.py` owns JSON/dictionary conversion only; it never reads or writes storage.
- `utils.py` validates and deep-freezes arbitrary JSON-compatible extension data.

There is no metadata repository. Storage belongs to the consuming use case, which can use `MetadataSerializer` with a JSON file, database, or remote service without changing the domain contract.

## Public API

```python
from pathlib import Path

from content_pipeline.domain.metadata import (
    Metadata,
    MetadataSerializer,
    MetadataStatus,
    PlatformMetadata,
    Visibility,
)

metadata = Metadata(
    title="Weekly engineering update",
    description="What changed this week.",
    hashtags=("engineering",),
    tags=("release", "weekly"),
    language="en",
    category="Engineering",
    visibility=Visibility.UNLISTED,
    video_path=Path("build/update.mp4"),
    thumbnail_path=Path("build/update.png"),
    project_id="project-123",
    channel_id="channel-main",
    platform_metadata=(
        PlatformMetadata("youtube", {"made_for_kids": False}),
    ),
    custom_fields={"campaign": "weekly-update"},
    status=MetadataStatus.READY,
)

payload = MetadataSerializer.to_json(metadata)
same_metadata = MetadataSerializer.from_json(payload)
```

`Metadata` contains title, description, hashtags, tags, language, category, visibility, video and optional thumbnail paths, project/channel identifiers, UTC lifecycle timestamps, optional scheduling, status, version, platform extensions, and arbitrary custom fields. `platform(name)` retrieves one extension safely.

## Validation rules

- Titles, project IDs, channel IDs, language, and category are required. Titles are trimmed and limited to 100 characters.
- Language uses a compact BCP 47 form such as `en`, `hi`, or `pt-BR`.
- Hashtags and tags are case-insensitively unique; hashtags are normalized to include `#`.
- Visibility and status must be their exported enums. A scheduled status requires a timezone-aware scheduled publish time.
- Timestamps must be timezone-aware and `updated_at` cannot precede `created_at`.
- Video paths are required `Path` values; thumbnail paths are optional. The contract validates their shape but not existence, so a workflow can describe artifacts before rendering creates them.
- Extension and custom fields must contain only JSON-compatible values with non-empty string keys. Nested containers are frozen.

`CategoryRegistry` provides an optional closed taxonomy at application composition time. The domain model intentionally does not impose a platform's category list.

## Extensions and compatibility

Platform metadata is represented by `PlatformMetadata(platform, fields)`, not platform-specific model classes. Adding a platform therefore requires no change to `Metadata`; the platform name is a normalized identifier and its fields are an isolated JSON-compatible payload. This supports existing and future platforms without coupling the core contract to one provider.

Serialization emits a `schema_version` (currently `1`). `MetadataSerializer` is pure and storage-independent, giving later schema migrations one explicit extension point. Metadata values are frozen; `metadata.next_version()` returns a new version while retaining the old value for workflow history. For a revised content value, construct a new immutable `Metadata` (or use `dataclasses.replace`) with the next version before persisting both versions in the consumer's chosen store.
