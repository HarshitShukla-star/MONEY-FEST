"""YouTube Data API adapter for the provider-neutral upload port."""

from collections.abc import Mapping
from time import sleep
from typing import Protocol

from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from googleapiclient.http import MediaFileUpload  # type: ignore[import-untyped]

from content_pipeline.core.channels.models import Channel
from content_pipeline.core.uploads.provider import UploadProvider
from content_pipeline.domain.uploads import (
    UploadRequest,
    UploadResponse,
    UploadResult,
    UploadStatus,
)
from content_pipeline.exceptions import AuthenticationError, ProviderError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)
_RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 3


class YouTubeUploadRequest(Protocol):
    """Minimal resumable request surface supplied by the Google client."""

    def next_chunk(self) -> tuple[object | None, Mapping[str, object] | None]:
        """Upload the next chunk and return its progress and final response."""


class YouTubeVideosResource(Protocol):
    """Minimal videos resource surface used by this provider."""

    def insert(
        self,
        *,
        part: str,
        body: Mapping[str, object],
        media_body: MediaFileUpload,
    ) -> YouTubeUploadRequest:
        """Create a resumable YouTube video upload request."""


class YouTubeClient(Protocol):
    """Injected authenticated YouTube Data API client surface."""

    def videos(self) -> YouTubeVideosResource:
        """Return the videos resource."""


class YouTubeUploadProvider(UploadProvider):
    """Perform YouTube API communication using an injected authenticated client."""

    def __init__(
        self,
        client: YouTubeClient,
        *,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        if isinstance(max_retries, bool) or not isinstance(max_retries, int):
            raise ValueError("Maximum YouTube upload retries must be an integer")
        if max_retries < 0:
            raise ValueError("Maximum YouTube upload retries cannot be negative")
        self._client = client
        self._max_retries = max_retries

    def supports(self, platform: str) -> bool:
        """Report support for the platform registered by the channel manager."""
        return platform == "youtube"

    def upload(self, request: UploadRequest, channel: Channel) -> UploadResponse:
        """Upload the supplied video and map the API result to an upload response."""
        try:
            upload_request = self._client.videos().insert(
                part="snippet,status",
                body=_video_body(request),
                media_body=MediaFileUpload(
                    str(request.metadata.video_path),
                    mimetype="video/*",
                    resumable=True,
                ),
            )
            response = _complete_upload(upload_request, max_retries=self._max_retries)
        except HttpError as exc:
            if _http_status(exc) in {401, 403}:
                raise AuthenticationError("YouTube authentication failed") from exc
            raise ProviderError("YouTube API upload failed") from exc
        except GoogleAuthError as exc:
            raise AuthenticationError("YouTube authentication failed") from exc
        except (OSError, ValueError) as exc:
            raise ProviderError("YouTube upload failed") from exc
        except Exception as exc:
            raise ProviderError("YouTube upload failed") from exc
        video_id = response.get("id")
        if not isinstance(video_id, str) or not video_id:
            raise ProviderError("YouTube upload returned no video id")
        _LOGGER.info(
            "youtube_upload_completed",
            extra={"channel_id": channel.id, "video_id": video_id},
        )
        return UploadResponse(
            result=UploadResult.SUCCESS,
            status=UploadStatus.PUBLISHED,
            provider_name="youtube",
            external_id=video_id,
            external_url=f"https://www.youtube.com/watch?v={video_id}",
        )


def _video_body(request: UploadRequest) -> dict[str, object]:
    """Map neutral metadata to the YouTube ``snippet`` and ``status`` parts."""
    metadata = request.metadata
    return {
        "snippet": {
            "title": metadata.title,
            "description": metadata.description,
            "tags": [*metadata.tags, *metadata.hashtags],
        },
        "status": {"privacyStatus": metadata.visibility.value},
    }


def _complete_upload(
    request: YouTubeUploadRequest, *, max_retries: int
) -> Mapping[str, object]:
    """Advance a resumable upload until the YouTube API returns a response."""
    response: Mapping[str, object] | None = None
    retries = 0
    while response is None:
        try:
            progress, response = request.next_chunk()
        except HttpError as exc:
            if _http_status(exc) not in _RETRYABLE_HTTP_STATUSES:
                raise
            retries = _retry_or_raise(exc, retries, max_retries)
        except OSError as exc:
            retries = _retry_or_raise(exc, retries, max_retries)
        else:
            retries = 0
            if progress is not None:
                _LOGGER.info("youtube_upload_progress")
    return response


def _retry_or_raise(error: Exception, retries: int, max_retries: int) -> int:
    """Retry only transient resumable-upload failures with bounded backoff."""
    if retries >= max_retries:
        raise error
    delay = 2**retries
    _LOGGER.warning(
        "youtube_upload_retrying",
        extra={"attempt": retries + 1, "delay_seconds": delay},
    )
    sleep(delay)
    return retries + 1


def _http_status(error: HttpError) -> int | None:
    """Read the HTTP status without exposing the client response type."""
    status = getattr(error.resp, "status", None)
    return status if isinstance(status, int) else None
