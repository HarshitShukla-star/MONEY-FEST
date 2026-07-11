"""Tests for the YouTube upload adapter without network access."""

from collections.abc import Mapping
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from content_pipeline.core.channels import Channel
from content_pipeline.core.uploads import YouTubeUploadProvider
from content_pipeline.domain.metadata import Metadata, Visibility
from content_pipeline.domain.uploads import UploadRequest
from content_pipeline.exceptions import AuthenticationError, ProviderError


class RecordingUploadRequest:
    """Mock resumable Google request with configurable chunk responses."""

    def __init__(
        self, responses: list[Mapping[str, object] | Exception | None]
    ) -> None:
        self._responses = iter(responses)

    def next_chunk(self) -> tuple[object | None, Mapping[str, object] | None]:
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return None, response


class RecordingVideosResource:
    """Mock videos resource that captures the API insert payload."""

    def __init__(self, request: RecordingUploadRequest) -> None:
        self.request = request
        self.calls: list[dict[str, object]] = []

    def insert(
        self, *, part: str, body: Mapping[str, object], media_body: object
    ) -> RecordingUploadRequest:
        self.calls.append({"part": part, "body": body, "media_body": media_body})
        return self.request


class RecordingClient:
    """Mock injected YouTube client."""

    def __init__(self, videos: RecordingVideosResource) -> None:
        self._videos = videos

    def videos(self) -> RecordingVideosResource:
        return self._videos


class FailingUploadRequest:
    """Mock request that raises a Google API error during upload."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def next_chunk(self) -> tuple[object | None, Mapping[str, object] | None]:
        raise self._error


def _request(tmp_path: Path) -> UploadRequest:
    video = tmp_path / "video.mp4"
    video.touch()
    return UploadRequest(
        Metadata(
            title="YouTube test",
            description="A provider test.",
            language="en",
            category="Education",
            visibility=Visibility.UNLISTED,
            video_path=video,
            project_id="project-1",
            channel_id="youtube-main",
            tags=("automation",),
            hashtags=("python",),
        )
    )


def _channel() -> Channel:
    return Channel(
        id="youtube-main",
        name="YouTube",
        platform="youtube",
        enabled=True,
        is_default=False,
        credential_reference=None,
    )


def test_youtube_provider_uploads_with_neutral_metadata(tmp_path: Path) -> None:
    videos = RecordingVideosResource(RecordingUploadRequest([None, {"id": "abc123"}]))
    provider = YouTubeUploadProvider(RecordingClient(videos))

    response = provider.upload(_request(tmp_path), _channel())

    assert provider.supports("youtube") is True
    assert provider.supports("instagram") is False
    assert response.external_id == "abc123"
    assert response.external_url == "https://www.youtube.com/watch?v=abc123"
    assert videos.calls[0]["part"] == "snippet,status"
    body = videos.calls[0]["body"]
    assert body == {
        "snippet": {
            "title": "YouTube test",
            "description": "A provider test.",
            "tags": ["automation", "#python"],
        },
        "status": {"privacyStatus": "unlisted"},
    }


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [(401, AuthenticationError), (500, ProviderError)],
)
def test_youtube_provider_translates_google_api_failures(
    tmp_path: Path, status: int, exception_type: type[Exception]
) -> None:
    error = HttpError(Response({"status": str(status)}), b"api failure")
    request = FailingUploadRequest(error)
    videos = RecordingVideosResource(request)  # type: ignore[arg-type]

    with pytest.raises(exception_type):
        YouTubeUploadProvider(RecordingClient(videos)).upload(
            _request(tmp_path), _channel()
        )


def test_youtube_provider_rejects_an_invalid_upload_response(tmp_path: Path) -> None:
    videos = RecordingVideosResource(RecordingUploadRequest([{}]))

    with pytest.raises(ProviderError, match="no video id"):
        YouTubeUploadProvider(RecordingClient(videos)).upload(
            _request(tmp_path), _channel()
        )


def test_youtube_provider_retries_transient_resumable_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "content_pipeline.core.uploads.youtube_provider.sleep", lambda _: None
    )
    error = HttpError(Response({"status": "503"}), b"temporarily unavailable")
    videos = RecordingVideosResource(RecordingUploadRequest([error, {"id": "abc123"}]))

    response = YouTubeUploadProvider(RecordingClient(videos)).upload(
        _request(tmp_path), _channel()
    )

    assert response.external_id == "abc123"
