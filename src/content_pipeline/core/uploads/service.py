"""Business orchestration for provider-neutral content uploads."""

from dataclasses import replace

from content_pipeline.core.channels import ChannelManager
from content_pipeline.core.channels.exceptions import ChannelStateError
from content_pipeline.core.uploads.provider import UploadProvider
from content_pipeline.domain.metadata import Metadata
from content_pipeline.domain.uploads import (
    UploadProviderError,
    UploadRequest,
    UploadResponse,
    UploadValidationError,
)
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)


class UploadService:
    """Validate and route uploads through an injected provider port."""

    def __init__(self, provider: UploadProvider, channels: ChannelManager) -> None:
        self._provider = provider
        self._channels = channels

    def upload(self, request: UploadRequest) -> UploadResponse:
        """Upload a validated request without exposing provider-specific failures."""
        if not isinstance(request, UploadRequest):
            raise UploadValidationError("Request must be an UploadRequest")
        self._validate_metadata(request.metadata)
        channel = self._channels.load_channel(request.metadata.channel_id)
        if not channel.enabled:
            raise ChannelStateError("A disabled channel cannot receive uploads")
        try:
            if not self._provider.supports(channel.platform):
                raise UploadValidationError(
                    f"Unsupported platform for upload provider: {channel.platform}"
                )
            response = self._provider.upload(request, channel)
        except UploadValidationError:
            raise
        except Exception:
            _LOGGER.error(
                "upload_provider_failed",
                extra={"channel_id": channel.id, "platform": channel.platform},
            )
            raise UploadProviderError("Upload provider failed") from None
        if not isinstance(response, UploadResponse):
            raise UploadProviderError("Upload provider returned an invalid response")
        _LOGGER.info(
            "upload_completed",
            extra={
                "channel_id": channel.id,
                "platform": channel.platform,
                "provider": response.provider_name,
                "result": response.result.value,
                "status": response.status.value,
            },
        )
        return response

    @staticmethod
    def _validate_metadata(metadata: Metadata) -> None:
        if not isinstance(metadata, Metadata):
            raise UploadValidationError("Metadata must be a Metadata value")
        try:
            replace(metadata)
        except Exception as exc:
            raise UploadValidationError("Metadata is invalid") from exc
        if not metadata.video_path.is_file():
            raise UploadValidationError(
                f"Video path does not reference an existing file: {metadata.video_path}"
            )
