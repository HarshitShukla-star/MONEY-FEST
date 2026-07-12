"""Tests for the multi-provider trend scan service."""

import pytest

from content_pipeline.core.trends.service import TrendScanService
from content_pipeline.domain.trends import TrendCandidate, TrendSource
from content_pipeline.exceptions import ProviderError


class StubProvider:
    """Deterministic in-memory trend provider for service-level tests."""

    def __init__(self, candidates: tuple[TrendCandidate, ...] | Exception) -> None:
        self._candidates = candidates

    def fetch(self, *, limit: int = 20) -> tuple[TrendCandidate, ...]:
        if isinstance(self._candidates, Exception):
            raise self._candidates
        return self._candidates[:limit]


def _candidate(topic: str, score: float) -> TrendCandidate:
    return TrendCandidate(topic=topic, source=TrendSource.YOUTUBE, score=score)


def test_scan_merges_candidates_across_providers() -> None:
    provider_a = StubProvider((_candidate("a", 10.0),))
    provider_b = StubProvider((_candidate("b", 20.0),))
    service = TrendScanService((provider_a, provider_b))

    snapshot = service.scan()

    assert [c.topic for c in snapshot.candidates] == ["b", "a"]


def test_scan_tolerates_one_provider_failing() -> None:
    healthy = StubProvider((_candidate("a", 10.0),))
    failing = StubProvider(ProviderError("boom"))
    service = TrendScanService((healthy, failing))

    snapshot = service.scan()

    assert len(snapshot.candidates) == 1


def test_constructor_requires_at_least_one_provider() -> None:
    with pytest.raises(ProviderError):
        TrendScanService(())
