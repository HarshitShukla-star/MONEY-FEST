"""Consumer-owned port for future caption provider adapters."""

from abc import ABC, abstractmethod
from typing import Protocol

from content_pipeline.domain.captions import CaptionRequest, ProviderResponse


class CaptionProvider(Protocol):
    """Port used by caption workflows, independent of an AI SDK or vendor."""

    def generate(self, request: CaptionRequest) -> ProviderResponse:
        """Generate raw output for a neutral caption request."""


class AbstractCaptionProvider(ABC):
    """Optional base class for adapters that need shared implementation support."""

    @abstractmethod
    def generate(self, request: CaptionRequest) -> ProviderResponse:
        """Generate raw output for a neutral caption request."""
