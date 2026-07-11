"""Consumer-owned upload provider port for future platform adapters."""

from abc import ABC, abstractmethod
from typing import Protocol

from content_pipeline.core.channels.models import Channel
from content_pipeline.domain.uploads import UploadRequest, UploadResponse


class UploadProvider(Protocol):
    """Port used by uploads without coupling the service to a platform SDK."""

    def supports(self, platform: str) -> bool:
        """Return whether this adapter supports a normalized platform name."""

    def upload(self, request: UploadRequest, channel: Channel) -> UploadResponse:
        """Upload a request to the supplied channel and return a neutral response."""


class AbstractUploadProvider(ABC):
    """Optional base class for upload adapters requiring shared implementation."""

    @abstractmethod
    def supports(self, platform: str) -> bool:
        """Return whether this adapter supports a normalized platform name."""

    @abstractmethod
    def upload(self, request: UploadRequest, channel: Channel) -> UploadResponse:
        """Upload a request to the supplied channel and return a neutral response."""
