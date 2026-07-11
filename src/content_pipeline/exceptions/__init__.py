"""Typed application exception hierarchy."""


class ApplicationError(Exception):
    """Base exception for expected application failures."""


class ConfigurationError(ApplicationError):
    """Raised when runtime configuration is invalid or incomplete."""


class ValidationError(ApplicationError):
    """Raised when an input violates a business or utility constraint."""


class ProviderError(ApplicationError):
    """Raised when an infrastructure provider fails."""


class AuthenticationError(ProviderError):
    """Raised when authentication or authorization fails."""


class NetworkError(ProviderError):
    """Raised when a network dependency cannot be reached."""


class UploadError(ProviderError):
    """Reserved for future upload workflow failures."""


__all__ = [
    "ApplicationError",
    "AuthenticationError",
    "ConfigurationError",
    "NetworkError",
    "ProviderError",
    "UploadError",
    "ValidationError",
]
