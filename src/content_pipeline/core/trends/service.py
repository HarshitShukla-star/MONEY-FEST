"""Fan out to registered trend providers and merge results into one snapshot."""

from content_pipeline.core.trends.provider import TrendProvider
from content_pipeline.domain.trends import TrendCandidate, TrendSnapshot
from content_pipeline.exceptions import ProviderError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)


class TrendScanService:
    """Combine one or more trend providers into a single ranked snapshot."""

    def __init__(self, providers: tuple[TrendProvider, ...]) -> None:
        if not isinstance(providers, tuple) or not providers:
            raise ProviderError("At least one trend provider is required")
        self._providers = providers

    def scan(self, *, limit_per_provider: int = 20) -> TrendSnapshot:
        """Fetch from every provider and return a merged, ranked snapshot.

        A single provider failing does not abort the scan; its failure is
        logged and the remaining providers still contribute candidates.
        """
        candidates: list[TrendCandidate] = []
        for provider in self._providers:
            try:
                candidates.extend(provider.fetch(limit=limit_per_provider))
            except ProviderError:
                _LOGGER.warning(
                    "trend_provider_failed",
                    extra={"provider": type(provider).__name__},
                )
        return TrendSnapshot(candidates=tuple(candidates))
