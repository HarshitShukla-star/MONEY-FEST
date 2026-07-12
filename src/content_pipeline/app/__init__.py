"""Delivery layer: composition root, CLI, and end-to-end orchestration.

Everything in this package is the "composition concern" the top-level
README names as outside the reusable foundation: it is the one place
allowed to construct OAuth clients, read environment configuration, and
wire concrete adapters into the framework-independent ``core`` use cases.
"""

from content_pipeline.app.pipeline import (
    ContentPipeline,
    PipelineClipOutcome,
    PipelineRunRequest,
    topic_hint_from_snapshot,
)

__all__ = [
    "ContentPipeline",
    "PipelineClipOutcome",
    "PipelineRunRequest",
    "topic_hint_from_snapshot",
]
