"""Consumer-owned port for AI metadata-generation adapters."""

from abc import ABC, abstractmethod
from typing import Protocol

from content_pipeline.domain.metadata import (
    MetadataGenerationRequest,
    MetadataGenerationResult,
)


class MetadataProvider(Protocol):
    """Generate provider-neutral metadata text from a transcript."""

    def generate(self, request: MetadataGenerationRequest) -> MetadataGenerationResult:
        """Return generated title, description, and hashtags."""


class AbstractMetadataProvider(ABC):
    """Optional base class for adapters sharing implementation support."""

    @abstractmethod
    def generate(self, request: MetadataGenerationRequest) -> MetadataGenerationResult:
        """Return generated title, description, and hashtags."""
