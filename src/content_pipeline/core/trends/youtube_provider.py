"""YouTube Data API adapter for the provider-neutral trend detection port."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from content_pipeline.core.trends.provider import AbstractTrendProvider
from content_pipeline.domain.trends import TrendCandidate, TrendSource
from content_pipeline.exceptions import AuthenticationError, ProviderError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)
_DEFAULT_REGION_CODE = "US"


class YouTubeVideosResource(Protocol):
    """Minimal videos resource surface used by this provider."""

    def list(
        self,
        *,
        part: str,
        chart: str,
        regionCode: str,
        maxResults: int,
    ) -> "YouTubeVideosRequest":
        """Create a request to list videos matching a chart."""


class YouTubeVideosRequest(Protocol):
    """Minimal executable request surface returned by the videos resource."""

    def execute(self) -> Mapping[str, object]:
        """Execute the request and return the decoded JSON response."""


class YouTubeClient(Protocol):
    """Injected authenticated YouTube Data API client surface."""

    def videos(self) -> YouTubeVideosResource:
        """Return the videos resource."""


class YouTubeTrendProvider(AbstractTrendProvider):
    """Fetch the regional trending chart using an injected authenticated client."""

    def __init__(
        self, client: YouTubeClient, *, region_code: str = _DEFAULT_REGION_CODE
    ) -> None:
        self._client = client
        self._region_code = _require_region_code(region_code)

    def fetch(self, *, limit: int = 20) -> tuple[TrendCandidate, ...]:
        """Return trending YouTube videos mapped to neutral trend candidates."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ProviderError("Limit must be a positive integer")
        try:
            request = self._client.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode=self._region_code,
                maxResults=limit,
            )
            response = request.execute()
        except HttpError as exc:
            if _http_status(exc) in {401, 403}:
                raise AuthenticationError("YouTube authentication failed") from exc
            raise ProviderError("YouTube trending request failed") from exc
        except GoogleAuthError as exc:
            raise AuthenticationError("YouTube authentication failed") from exc
        except Exception as exc:
            raise ProviderError("YouTube trending request failed") from exc

        items = response.get("items")
        if not isinstance(items, Sequence) or isinstance(items, str):
            raise ProviderError("YouTube trending response was malformed")
        candidates = tuple(_to_candidate(item) for item in items if _is_usable(item))
        _LOGGER.info(
            "youtube_trends_fetched",
            extra={"region_code": self._region_code, "count": len(candidates)},
        )
        return candidates


def _is_usable(item: object) -> bool:
    """Report whether a chart item has the fields needed to build a candidate."""
    return (
        isinstance(item, Mapping)
        and isinstance(item.get("snippet"), Mapping)
        and isinstance(item.get("statistics"), Mapping)
        and isinstance(item.get("id"), str)
    )


def _to_candidate(item: Mapping[str, object]) -> TrendCandidate:
    """Map one YouTube chart item to a neutral, scored trend candidate."""
    snippet = item["snippet"]
    statistics = item["statistics"]
    assert isinstance(snippet, Mapping)  # narrowed by _is_usable
    assert isinstance(statistics, Mapping)
    title = snippet.get("title")
    view_count = statistics.get("viewCount", "0")
    return TrendCandidate(
        topic=title if isinstance(title, str) else "Untitled",
        source=TrendSource.YOUTUBE,
        score=float(view_count) if _is_numeric_string(view_count) else 0.0,
        external_id=str(item["id"]),
        details={
            "category_id": snippet.get("categoryId"),
            "channel_title": snippet.get("channelTitle"),
        },
    )


def _is_numeric_string(value: object) -> bool:
    """Report whether a value is a string containing only digits."""
    return isinstance(value, str) and value.isdigit()


def _require_region_code(region_code: str) -> str:
    """Validate a two-letter ISO region code."""
    if (
        not isinstance(region_code, str)
        or len(region_code) != 2
        or not region_code.isalpha()
    ):
        raise ProviderError("Region code must be a two-letter ISO code")
    return region_code.upper()


def _http_status(error: HttpError) -> int | None:
    """Read the HTTP status without exposing the client response type."""
    status = getattr(error.resp, "status", None)
    return status if isinstance(status, int) else None
