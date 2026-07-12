"""Tests for the YouTube trending adapter without network access."""

from collections.abc import Mapping

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from content_pipeline.core.trends.youtube_provider import YouTubeTrendProvider
from content_pipeline.domain.trends import TrendSource
from content_pipeline.exceptions import AuthenticationError, ProviderError

_SAMPLE_ITEM = {
    "id": "abc123",
    "snippet": {
        "title": "Building an AI automation",
        "categoryId": "28",
        "channelTitle": "deepucodes",
    },
    "statistics": {"viewCount": "45000"},
}


class RecordingRequest:
    """Mock executable request with a configurable response or error."""

    def __init__(self, response: Mapping[str, object] | Exception) -> None:
        self._response = response

    def execute(self) -> Mapping[str, object]:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class RecordingVideosResource:
    """Mock videos resource that captures the list() call arguments."""

    def __init__(self, request: RecordingRequest) -> None:
        self._request = request
        self.calls: list[dict[str, object]] = []

    def list(
        self, *, part: str, chart: str, regionCode: str, maxResults: int
    ) -> RecordingRequest:
        self.calls.append(
            {
                "part": part,
                "chart": chart,
                "regionCode": regionCode,
                "maxResults": maxResults,
            }
        )
        return self._request


class RecordingClient:
    """Mock injected YouTube client."""

    def __init__(self, videos: RecordingVideosResource) -> None:
        self._videos = videos

    def videos(self) -> RecordingVideosResource:
        return self._videos


def _http_error(status: int) -> HttpError:
    return HttpError(Response({"status": status}), b"{}")


def test_fetch_maps_chart_items_to_candidates() -> None:
    videos = RecordingVideosResource(RecordingRequest({"items": [_SAMPLE_ITEM]}))
    provider = YouTubeTrendProvider(RecordingClient(videos), region_code="in")

    candidates = provider.fetch(limit=5)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.topic == "Building an AI automation"
    assert candidate.source is TrendSource.YOUTUBE
    assert candidate.score == 45000.0
    assert candidate.external_id == "abc123"
    assert videos.calls[0]["regionCode"] == "IN"
    assert videos.calls[0]["maxResults"] == 5


def test_fetch_skips_malformed_items() -> None:
    videos = RecordingVideosResource(
        RecordingRequest({"items": [_SAMPLE_ITEM, {"id": "missing-fields"}]})
    )
    provider = YouTubeTrendProvider(RecordingClient(videos))

    candidates = provider.fetch()

    assert len(candidates) == 1


def test_fetch_raises_provider_error_on_malformed_response() -> None:
    videos = RecordingVideosResource(RecordingRequest({"items": "not-a-list"}))
    provider = YouTubeTrendProvider(RecordingClient(videos))

    with pytest.raises(ProviderError):
        provider.fetch()


def test_fetch_raises_authentication_error_on_401() -> None:
    videos = RecordingVideosResource(RecordingRequest(_http_error(401)))
    provider = YouTubeTrendProvider(RecordingClient(videos))

    with pytest.raises(AuthenticationError):
        provider.fetch()


def test_fetch_raises_provider_error_on_other_http_errors() -> None:
    videos = RecordingVideosResource(RecordingRequest(_http_error(500)))
    provider = YouTubeTrendProvider(RecordingClient(videos))

    with pytest.raises(ProviderError):
        provider.fetch()


def test_fetch_rejects_non_positive_limit() -> None:
    videos = RecordingVideosResource(RecordingRequest({"items": []}))
    provider = YouTubeTrendProvider(RecordingClient(videos))

    with pytest.raises(ProviderError):
        provider.fetch(limit=0)


def test_constructor_rejects_invalid_region_code() -> None:
    videos = RecordingVideosResource(RecordingRequest({"items": []}))
    with pytest.raises(ProviderError):
        YouTubeTrendProvider(RecordingClient(videos), region_code="usa")
