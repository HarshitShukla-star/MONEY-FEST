"""Executable contract tests for canonical content metadata."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from content_pipeline.domain.metadata import (
    CategoryRegistry,
    Metadata,
    MetadataSerializationError,
    MetadataSerializer,
    MetadataStatus,
    MetadataValidationError,
    PlatformMetadata,
    Visibility,
)


@pytest.fixture
def metadata() -> Metadata:
    """Return a fully populated, deterministic metadata version."""
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    return Metadata(
        title="  A practical metadata contract  ",
        description="A portable description.",
        hashtags=("Python", "#Automation"),
        tags=("Engineering", "Metadata"),
        language="pt-br",
        category="Education",
        visibility=Visibility.UNLISTED,
        thumbnail_path=Path("art/thumb.png"),
        video_path=Path("output/video.mp4"),
        project_id="project-42",
        channel_id="channel-7",
        scheduled_publish_at=datetime(2026, 1, 2, tzinfo=UTC),
        platform_metadata=(
            PlatformMetadata("Example_Platform", {"audience": "regional"}),
        ),
        custom_fields={"campaign": {"id": 42}, "topics": ["python"]},
        status=MetadataStatus.SCHEDULED,
        created_at=instant,
        updated_at=instant,
    )


def test_metadata_normalizes_and_is_deeply_immutable(metadata: Metadata) -> None:
    assert metadata.title == "A practical metadata contract"
    assert metadata.hashtags == ("#Python", "#Automation")
    assert metadata.language == "pt-BR"
    assert metadata.platform("example_platform").fields["audience"] == "regional"  # type: ignore[union-attr]

    with pytest.raises(TypeError):
        metadata.custom_fields["campaign"] = "new"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        metadata.title = "Changed"  # type: ignore[misc]


def test_dict_and_json_round_trip(metadata: Metadata) -> None:
    exported = MetadataSerializer.to_dict(metadata)

    assert exported["schema_version"] == 1
    assert exported["platform_metadata"] == {
        "example_platform": {"audience": "regional"}
    }
    assert MetadataSerializer.from_dict(exported) == metadata
    assert (
        MetadataSerializer.from_json(MetadataSerializer.to_json(metadata)) == metadata
    )


def test_serialization_rejects_unknown_schema_and_bad_json(metadata: Metadata) -> None:
    document = MetadataSerializer.to_dict(metadata)
    document["schema_version"] = 99

    with pytest.raises(MetadataSerializationError, match="Unsupported"):
        MetadataSerializer.from_dict(document)
    with pytest.raises(MetadataSerializationError, match="malformed"):
        MetadataSerializer.from_json("not json")


def test_serialization_reports_missing_required_fields(metadata: Metadata) -> None:
    document = MetadataSerializer.to_dict(metadata)
    del document["project_id"]

    with pytest.raises(MetadataSerializationError, match="invalid fields"):
        MetadataSerializer.from_dict(document)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"title": ""}, "Title must not be empty"),
        ({"title": "x" * 101}, "must not exceed"),
        ({"hashtags": ("News", "#news")}, "Hashtags must be unique"),
        ({"tags": ("News", "news")}, "Tags must be unique"),
        ({"language": "english"}, "BCP 47"),
        ({"category": ""}, "Category must not be empty"),
        ({"video_path": Path(".")}, "Video path"),
        ({"project_id": " "}, "Project id"),
        ({"custom_fields": {"bad": object()}}, "JSON-compatible"),
    ],
)
def test_validation_rejects_invalid_inputs(
    metadata: Metadata, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(MetadataValidationError, match=message):
        replace(metadata, **changes)


def test_validation_rejects_invalid_visibility_and_schedule(metadata: Metadata) -> None:
    with pytest.raises(MetadataValidationError, match="Visibility"):
        replace(metadata, visibility="everyone")  # type: ignore[arg-type]
    with pytest.raises(MetadataValidationError, match="Scheduled publish time"):
        replace(metadata, scheduled_publish_at=None)


def test_platform_extensions_are_generic_and_unique(metadata: Metadata) -> None:
    with pytest.raises(MetadataValidationError, match="unique"):
        replace(
            metadata,
            platform_metadata=(
                PlatformMetadata("custom", {}),
                PlatformMetadata("CUSTOM", {}),
            ),
        )
    with pytest.raises(MetadataValidationError, match="identifier"):
        PlatformMetadata("not a platform", {})


def test_category_registry_is_an_optional_application_policy() -> None:
    registry = CategoryRegistry(("Education", "News"))

    assert registry.validate("Education") == "Education"
    with pytest.raises(MetadataValidationError, match="not registered"):
        registry.validate("Entertainment")


def test_versioning_creates_a_new_historical_value(metadata: Metadata) -> None:
    revised = metadata.next_version(updated_at=datetime(2026, 1, 3, tzinfo=UTC))

    assert metadata.version == 1
    assert revised.version == 2
    assert revised.created_at == metadata.created_at
    assert revised.updated_at == datetime(2026, 1, 3, tzinfo=UTC)
