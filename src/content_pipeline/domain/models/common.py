"""Generic models shared across future application modules."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class OperationStatus(StrEnum):
    """Lifecycle outcome for a generic operation."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BaseResponse:
    """Base response metadata suitable for internal service boundaries."""

    status: OperationStatus
    message: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class ErrorResponse(BaseResponse):
    """A safe, serializable representation of an error outcome."""

    code: str = "internal_error"
    details: Mapping[str, str] = field(default_factory=dict)
    status: OperationStatus = field(default=OperationStatus.FAILED, init=False)


@dataclass(frozen=True, slots=True)
class Result[T]:
    """Explicit success/failure result that avoids ambiguous null return values."""

    value: T | None = None
    error: ErrorResponse | None = None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.error is None):
            raise ValueError("Result must contain exactly one of value or error")

    @property
    def is_success(self) -> bool:
        """Whether this result contains a value."""
        return self.error is None
