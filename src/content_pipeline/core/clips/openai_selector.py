"""OpenAI adapter for the provider-neutral clip-selection port."""

import json
from collections.abc import Mapping
from typing import cast

from openai import OpenAI

from content_pipeline.config import Settings
from content_pipeline.core.clips.provider import SegmentSelector
from content_pipeline.domain.clips import (
    ClipCandidateRequest,
    ClipPlan,
    ClipSelection,
    Transcript,
)
from content_pipeline.exceptions import ConfigurationError, ProviderError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)

_SYSTEM_INSTRUCTION = (
    "Select the strongest self-contained short-form clip candidates from the "
    "supplied timed transcript. Return a JSON object with a single field "
    '"clips": an array of objects, each with start_seconds (number), '
    "end_seconds (number), title (string), reason (string), and score "
    "(number between 0 and 1). Only use timestamps that appear in the "
    "transcript and respect the requested clip-count and duration bounds."
)


class OpenAISegmentSelector(SegmentSelector):
    """Translate OpenAI Chat Completions output into a neutral ClipPlan."""

    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self._settings = settings
        if client is not None:
            self._client = client
            return
        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise ConfigurationError(
                "OPENAI_API_KEY is required for the OpenAI segment selector"
            )
        self._client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def select(
        self, transcript: Transcript, request: ClipCandidateRequest
    ) -> ClipPlan:
        """Ask the model for candidate clips and validate its selections."""
        try:
            completion = self._client.chat.completions.create(
                model=self._settings.openai_metadata_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_INSTRUCTION},
                    {"role": "user", "content": _prompt(transcript, request)},
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            plan = _parse_plan(content, transcript, request)
        except ProviderError:
            raise
        except Exception as exc:
            _LOGGER.error("openai_segment_selection_failed")
            raise ProviderError("OpenAI segment selection failed") from exc
        _LOGGER.info(
            "clip_plan_generated",
            extra={
                "provider": "openai",
                "model": self._settings.openai_metadata_model,
                "clip_count": len(plan.selections),
            },
        )
        return plan


def _prompt(transcript: Transcript, request: ClipCandidateRequest) -> str:
    """Render the neutral transcript and bounds for the model."""
    lines = [
        f"[{segment.start_seconds:.2f}-{segment.end_seconds:.2f}] {segment.text}"
        for segment in transcript.segments
    ]
    context = [
        f"Language: {transcript.language}",
        f"Maximum clips: {request.maximum_clips}",
        f"Minimum clip duration seconds: {request.minimum_duration_seconds}",
        f"Maximum clip duration seconds: {request.maximum_duration_seconds}",
    ]
    if request.topic_hint is not None:
        context.append(f"Topic hint: {request.topic_hint}")
    context.append("Transcript:\n" + "\n".join(lines))
    return "\n\n".join(context)


def _parse_plan(
    content: str | None,
    transcript: Transcript,
    request: ClipCandidateRequest,
) -> ClipPlan:
    """Convert a structured OpenAI message into a validated ClipPlan."""
    if content is None:
        raise ProviderError("OpenAI returned an empty clip-selection response")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError("OpenAI returned malformed clip-selection JSON") from exc
    if not isinstance(payload, Mapping):
        raise ProviderError("OpenAI returned clip-selection JSON that is not an object")
    raw_clips = payload.get("clips")
    if not isinstance(raw_clips, list) or not raw_clips:
        raise ProviderError("OpenAI returned no clip selections")
    selections: list[ClipSelection] = []
    for raw_clip in raw_clips[: request.maximum_clips]:
        selections.append(_parse_selection(raw_clip, transcript))
    try:
        return ClipPlan(selections=tuple(selections))
    except Exception as exc:
        raise ProviderError("OpenAI clip plan failed validation") from exc


def _parse_selection(raw_clip: object, transcript: Transcript) -> ClipSelection:
    """Convert and bounds-check a single raw clip object from the model."""
    if not isinstance(raw_clip, Mapping):
        raise ProviderError("OpenAI returned a malformed clip selection")
    start = raw_clip.get("start_seconds")
    end = raw_clip.get("end_seconds")
    title = raw_clip.get("title")
    reason = raw_clip.get("reason")
    score = raw_clip.get("score")
    if (
        not isinstance(start, (int, float))
        or not isinstance(end, (int, float))
        or not isinstance(title, str)
        or not isinstance(reason, str)
        or not isinstance(score, (int, float))
    ):
        raise ProviderError("OpenAI returned a malformed clip selection")
    if end > transcript.duration_seconds:
        raise ProviderError("OpenAI selected a clip beyond the transcript duration")
    try:
        return ClipSelection(
            start_seconds=cast(float, start),
            end_seconds=cast(float, end),
            title=title,
            reason=reason,
            score=cast(float, score),
        )
    except Exception as exc:
        raise ProviderError("OpenAI selection failed validation") from exc
