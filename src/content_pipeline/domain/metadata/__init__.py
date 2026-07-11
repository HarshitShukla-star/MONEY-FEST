"""Canonical, immutable metadata contract for every content-pipeline module."""

from content_pipeline.domain.metadata.exceptions import (
    MetadataError,
    MetadataSerializationError,
    MetadataValidationError,
)
from content_pipeline.domain.metadata.generation import (
    MetadataGenerationRequest,
    MetadataGenerationResult,
)
from content_pipeline.domain.metadata.models import (
    Metadata,
    MetadataStatus,
    PlatformMetadata,
    Visibility,
)
from content_pipeline.domain.metadata.serialization import (
    SCHEMA_VERSION,
    MetadataSerializer,
)
from content_pipeline.domain.metadata.validation import (
    MAX_TITLE_LENGTH,
    CategoryRegistry,
)

__all__ = [
    "CategoryRegistry",
    "MAX_TITLE_LENGTH",
    "Metadata",
    "MetadataError",
    "MetadataGenerationRequest",
    "MetadataGenerationResult",
    "MetadataSerializationError",
    "MetadataSerializer",
    "MetadataStatus",
    "MetadataValidationError",
    "PlatformMetadata",
    "SCHEMA_VERSION",
    "Visibility",
]
