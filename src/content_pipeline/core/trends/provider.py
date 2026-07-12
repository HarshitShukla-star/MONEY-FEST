"""Consumer-owned port for trend-detection adapters."""

from abc import ABC, abstractmethod
from typing import Protocol

from content_pipeline.domain.trends import TrendCandidate


class TrendProvider(Protocol):
    """Fetch provider-neutral trend candidates from one signal source."""

    def fetch(self, *, limit: int = 20) -> tuple[TrendCandidate, ...]:
        """Return up to ``limit`` scored trend candidates."""


class AbstractTrendProvider(ABC):
    """Optional base class for adapters sharing implementation support."""

    @abstractmethod
    def fetch(self, *, limit: int = 20) -> tuple[TrendCandidate, ...]:
        """Return up to ``limit`` scored trend candidates."""
