"""AI metadata-generation ports and provider adapters."""

from content_pipeline.core.metadata.openai_provider import OpenAIMetadataProvider
from content_pipeline.core.metadata.provider import (
    AbstractMetadataProvider,
    MetadataProvider,
)

__all__ = [
    "AbstractMetadataProvider",
    "MetadataProvider",
    "OpenAIMetadataProvider",
]
