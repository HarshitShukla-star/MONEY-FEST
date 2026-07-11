"""Behavioural tests for provider-neutral upload orchestration."""

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from content_pipeline.core.channels import (
    Channel,
    ChannelManager,
    JsonChannelRepository,
)
from content_pipeline.core.channels.exceptions import ChannelStateError
from content_pipeline.core.uploads import UploadProvider, UploadService
from content_pipeline.domain.metadata import Metadata, Visibility
from content_pipeline.domain.uploads import (
    UploadProviderError,
    UploadRequest,
    UploadResponse,
    UploadResult,
    UploadStatus,
    UploadValidationError,
)


class RecordingProvider:
    """Test double for the injected upload-provider port."""

    def __init__(self, *, supported: bool = True, fail: bool = False) -> None:
        self.supported = supported
        self.fail = fail
        self.platforms: list[str] = []
        self.calls: list[tuple[UploadRequest, Channel]] = []

    def supports(self, platform: str) -> bool:
        self.platforms.append(platform)
        return self.supported

    def upload(self, request: UploadRequest, channel: Channel) -> UploadResponse:
        if self.fail:
            raise RuntimeError("vendor transport failure")
        self.calls.append((request, channel))
        return UploadResponse(
            result=UploadResult.SUCCESS,
            status=UploadStatus.PUBLISHED,
            provider_name="fake",
            external_id="post-1",
        )


@pytest.fixture
def manager(tmp_path: Path) -> ChannelManager:
    """Return a channel manager containing one enabled YouTube channel."""
    manager = ChannelManager(JsonChannelRepository(tmp_path / "channels.json"))
    manager.create_channel("Primary", "youtube", channel_id="youtube-main")
    return manager


def _request(tmp_path: Path) -> UploadRequest:
    video = tmp_path / "video.mp4"
    video.touch()
    return UploadRequest(
        Metadata(
            title="Upload test",
            description="A valid upload test.",
            language="en",
            category="Education",
            visibility=Visibility.PUBLIC,
            video_path=video,
            project_id="project-1",
            channel_id="youtube-main",
        )
    )


def test_upload_validates_then_delegates_to_the_injected_provider(
    manager: ChannelManager, tmp_path: Path
) -> None:
    provider = RecordingProvider()
    service = UploadService(cast(UploadProvider, provider), manager)
    request = _request(tmp_path)

    result = service.upload(request)

    assert result.external_id == "post-1"
    assert provider.platforms == ["youtube"]
    assert provider.calls == [(request, manager.load_channel("youtube-main"))]


def test_upload_rejects_a_missing_video_path_before_calling_provider(
    manager: ChannelManager, tmp_path: Path
) -> None:
    provider = RecordingProvider()
    service = UploadService(cast(UploadProvider, provider), manager)
    request = _request(tmp_path)
    request = replace(
        request,
        metadata=replace(request.metadata, video_path=tmp_path / "missing.mp4"),
    )

    with pytest.raises(UploadValidationError, match="existing file"):
        service.upload(request)

    assert provider.calls == []


def test_upload_rejects_disabled_channels_before_calling_provider(
    manager: ChannelManager, tmp_path: Path
) -> None:
    manager.disable_channel("youtube-main")
    provider = RecordingProvider()
    service = UploadService(cast(UploadProvider, provider), manager)

    with pytest.raises(ChannelStateError, match="disabled"):
        service.upload(_request(tmp_path))

    assert provider.calls == []


def test_upload_rejects_platforms_not_supported_by_the_provider(
    manager: ChannelManager, tmp_path: Path
) -> None:
    provider = RecordingProvider(supported=False)
    service = UploadService(cast(UploadProvider, provider), manager)

    with pytest.raises(UploadValidationError, match="Unsupported platform"):
        service.upload(_request(tmp_path))

    assert provider.calls == []


def test_upload_normalizes_provider_failures(
    manager: ChannelManager, tmp_path: Path
) -> None:
    provider = RecordingProvider(fail=True)
    service = UploadService(cast(UploadProvider, provider), manager)

    with pytest.raises(UploadProviderError, match="Upload provider failed"):
        service.upload(_request(tmp_path))


def test_upload_rejects_invalid_request_and_metadata(
    manager: ChannelManager, tmp_path: Path
) -> None:
    service = UploadService(cast(UploadProvider, RecordingProvider()), manager)

    with pytest.raises(UploadValidationError, match="UploadRequest"):
        service.upload(cast(UploadRequest, object()))

    request = _request(tmp_path)
    object.__setattr__(request, "metadata", object())
    with pytest.raises(UploadValidationError, match="Metadata"):
        service.upload(request)
