"""Immutable, provider-neutral values for content uploads."""

from dataclasses import dataclass
from enum import StrEnum

from content_pipeline.domain.metadata import Metadata
from content_pipeline.domain.uploads.exceptions import UploadValidationError


class UploadResult(StrEnum):
    """Terminal outcome reported by an upload provider."""

    SUCCESS = "success"
    FAILURE = "failure"


class UploadStatus(StrEnum):
    """Provider-neutral state of an upload operation."""

    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class UploadRequest:
    """Request to publish one canonical metadata version."""

    metadata: Metadata

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, Metadata):
            raise UploadValidationError("Metadata must be a Metadata value")


@dataclass(frozen=True, slots=True)
class UploadResponse:
    """Normalized result returned by any upload provider."""

    result: UploadResult
    status: UploadStatus
    provider_name: str
    external_id: str | None = None
    external_url: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.result, UploadResult):
            raise UploadValidationError("Result must be a supported UploadResult value")
        if not isinstance(self.status, UploadStatus):
            raise UploadValidationError("Status must be a supported UploadStatus value")
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise UploadValidationError("Provider name must not be empty")
        if self.result is UploadResult.SUCCESS and self.status is UploadStatus.FAILED:
            raise UploadValidationError("A successful upload cannot have failed status")
        if (
            self.result is UploadResult.FAILURE
            and self.status is not UploadStatus.FAILED
        ):
            raise UploadValidationError("A failed upload must have failed status")
        for value, field_name in (
            (self.external_id, "External id"),
            (self.external_url, "External URL"),
            (self.message, "Message"),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise UploadValidationError(f"{field_name} must not be blank")
