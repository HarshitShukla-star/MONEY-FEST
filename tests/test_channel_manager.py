"""Behavioural tests for the independent channel-management module."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from content_pipeline.core.channels import (
    ChannelManager,
    ChannelUpdate,
    JsonChannelRepository,
    PlatformRegistry,
)
from content_pipeline.core.channels.exceptions import (
    ChannelNotFoundError,
    ChannelPersistenceError,
    ChannelStateError,
    ChannelValidationError,
    DuplicateChannelError,
)


@pytest.fixture
def manager(tmp_path: Path) -> ChannelManager:
    """Return a manager backed by a temporary JSON store."""
    return ChannelManager(
        JsonChannelRepository(tmp_path / "channels.json"),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_create_load_and_persist_channel(manager: ChannelManager) -> None:
    created = manager.create_channel(
        "Primary Shorts",
        "YouTube",
        channel_id="youtube-main",
        credential_reference="secret://youtube/main",
        metadata={"region": "IN"},
        tags=("shorts", "primary"),
    )

    loaded = manager.load_channel("youtube-main")

    assert loaded == created
    assert loaded.platform == "youtube"
    assert loaded.metadata == {"region": "IN"}


def test_create_rejects_duplicate_id_and_name(manager: ChannelManager) -> None:
    manager.create_channel("Primary", "youtube", channel_id="one")

    with pytest.raises(DuplicateChannelError, match="id already exists"):
        manager.create_channel("Different", "youtube", channel_id="one")
    with pytest.raises(DuplicateChannelError, match="name already exists"):
        manager.create_channel("primary", "youtube", channel_id="two")


@pytest.mark.parametrize("name,platform", [("", "youtube"), ("Valid", "unknown")])
def test_create_validates_required_fields_and_platform(
    manager: ChannelManager, name: str, platform: str
) -> None:
    with pytest.raises(ChannelValidationError):
        manager.create_channel(name, platform)


def test_update_can_change_fields_and_clear_credential(manager: ChannelManager) -> None:
    manager.create_channel(
        "Primary", "youtube", channel_id="one", credential_reference="secret://one"
    )

    updated = manager.update_channel(
        "one",
        ChannelUpdate(
            name="Updated",
            platform="instagram",
            credential_reference=None,
            metadata={"language": "en"},
            tags=("news",),
        ),
    )

    assert updated.name == "Updated"
    assert updated.platform == "instagram"
    assert updated.credential_reference is None
    assert updated.tags == ("news",)


def test_enable_disable_and_default_invariants(manager: ChannelManager) -> None:
    manager.create_channel("One", "youtube", channel_id="one")
    manager.create_channel("Two", "instagram", channel_id="two", enabled=False)

    with pytest.raises(ChannelStateError, match="disabled"):
        manager.set_default_channel("two")

    manager.enable_channel("two")
    selected = manager.set_default_channel("two")

    assert selected.is_default is True
    with pytest.raises(ChannelStateError, match="must remain enabled"):
        manager.disable_channel("two")


def test_setting_default_replaces_previous_default(manager: ChannelManager) -> None:
    manager.create_channel("One", "youtube", channel_id="one")
    manager.create_channel("Two", "instagram", channel_id="two")
    manager.set_default_channel("one")

    manager.set_default_channel("two")

    assert manager.get_default_channel().id == "two"  # type: ignore[union-attr]
    assert manager.load_channel("one").is_default is False


def test_delete_and_not_found_behaviour(manager: ChannelManager) -> None:
    manager.create_channel("One", "youtube", channel_id="one")
    manager.delete_channel("one")

    assert manager.find_by_id("one") is None
    with pytest.raises(ChannelNotFoundError):
        manager.load_channel("one")
    with pytest.raises(ChannelNotFoundError):
        manager.delete_channel("one")


def test_search_and_list_are_deterministic(manager: ChannelManager) -> None:
    manager.create_channel("Bravo Tech", "youtube", channel_id="b")
    manager.create_channel("Alpha News", "youtube", channel_id="a")
    manager.create_channel("Alpha Stories", "instagram", channel_id="c")

    assert [item.id for item in manager.list_channels()] == ["a", "c", "b"]
    assert [item.id for item in manager.find_by_platform("youtube")] == ["a", "b"]
    assert [item.id for item in manager.find_by_name("alpha")] == ["a", "c"]


def test_platform_registry_allows_extension_without_manager_changes(
    tmp_path: Path,
) -> None:
    registry = PlatformRegistry(("youtube",))
    registry.register("linkedin")
    manager = ChannelManager(
        JsonChannelRepository(tmp_path / "channels.json"), registry
    )

    channel = manager.create_channel(
        "Professional", "linkedin", channel_id="linkedin-one"
    )

    assert channel.platform == "linkedin"


def test_json_repository_reports_corrupt_storage(tmp_path: Path) -> None:
    store = tmp_path / "channels.json"
    store.write_text("{not valid json", encoding="utf-8")
    manager = ChannelManager(JsonChannelRepository(store))

    with pytest.raises(ChannelPersistenceError, match="Unable to read"):
        manager.list_channels()


def test_json_repository_rejects_type_coercion_in_persisted_records(
    tmp_path: Path,
) -> None:
    store = tmp_path / "channels.json"
    store.write_text(
        '[{"id":"one","name":"One","platform":"youtube",'
        '"enabled":"false","is_default":false,"credential_reference":null,'
        '"metadata":{},"created_at":"2026-01-01T00:00:00+00:00",'
        '"updated_at":"2026-01-01T00:00:00+00:00","tags":[]}]',
        encoding="utf-8",
    )

    with pytest.raises(ChannelPersistenceError, match="invalid record"):
        ChannelManager(JsonChannelRepository(store)).list_channels()


def test_manager_rejects_invalid_runtime_channel_values(
    manager: ChannelManager,
) -> None:
    with pytest.raises(ChannelValidationError, match="boolean"):
        manager.create_channel("One", "youtube", enabled="true")  # type: ignore[arg-type]
    with pytest.raises(ChannelValidationError, match="tuple of strings"):
        manager.create_channel("One", "youtube", tags=("valid", 1))  # type: ignore[arg-type]
    manager.create_channel("One", "youtube", channel_id="one")
    with pytest.raises(ChannelValidationError, match="ChannelUpdate"):
        manager.update_channel("one", object())  # type: ignore[arg-type]


def test_metadata_and_tags_must_be_valid(manager: ChannelManager) -> None:
    with pytest.raises(ChannelValidationError, match="JSON serializable"):
        manager.create_channel("One", "youtube", metadata={"bad": object()})
    with pytest.raises(ChannelValidationError, match="JSON serializable"):
        manager.create_channel("One", "youtube", metadata={"bad": float("nan")})
    with pytest.raises(ChannelValidationError, match="tags must be unique"):
        manager.create_channel("One", "youtube", tags=("News", "news"))
