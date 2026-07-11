"""Extensible platform-name validation."""

from collections.abc import Iterable

from content_pipeline.core.channels.exceptions import ChannelValidationError


class PlatformRegistry:
    """Registry of accepted platform identifiers.

    Register future platform identifiers during application composition without
    changing channel models or the manager implementation.
    """

    def __init__(self, platforms: Iterable[str] = ()) -> None:
        self._platforms: set[str] = set()
        for platform in platforms:
            self.register(platform)

    def register(self, platform: str) -> None:
        """Register a normalized platform identifier."""
        normalized = self.normalize(platform)
        self._platforms.add(normalized)

    def validate(self, platform: str) -> str:
        """Return a normalized registered platform or raise a validation error."""
        normalized = self.normalize(platform)
        if normalized not in self._platforms:
            supported = ", ".join(sorted(self._platforms))
            raise ChannelValidationError(
                f"Unsupported platform '{normalized}'. Supported platforms: {supported}"
            )
        return normalized

    @staticmethod
    def normalize(platform: str) -> str:
        """Normalize a platform name and reject blank or malformed identifiers."""
        if not isinstance(platform, str):
            raise ChannelValidationError("Platform must be a non-empty identifier")
        normalized = platform.strip().lower()
        if not normalized or not normalized.replace("_", "").isalnum():
            raise ChannelValidationError("Platform must be a non-empty identifier")
        return normalized

    @property
    def platforms(self) -> frozenset[str]:
        """Return all registered platform identifiers."""
        return frozenset(self._platforms)


def default_platform_registry() -> PlatformRegistry:
    """Return the registry containing the currently supported platforms."""
    return PlatformRegistry(("youtube", "instagram", "tiktok", "facebook"))
