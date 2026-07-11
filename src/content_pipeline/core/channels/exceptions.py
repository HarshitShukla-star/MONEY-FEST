"""Errors specific to channel-management operations."""

from content_pipeline.exceptions import ApplicationError, ValidationError


class ChannelError(ApplicationError):
    """Base exception for expected channel-management failures."""


class ChannelNotFoundError(ChannelError):
    """Raised when an operation references a channel that does not exist."""


class DuplicateChannelError(ChannelError):
    """Raised when a channel id or friendly name is already in use."""


class ChannelStateError(ChannelError):
    """Raised when a requested channel state violates an invariant."""


class ChannelPersistenceError(ChannelError):
    """Raised when the channel store cannot be read or written safely."""


class ChannelValidationError(ValidationError):
    """Raised when channel input or persisted channel data is invalid."""
