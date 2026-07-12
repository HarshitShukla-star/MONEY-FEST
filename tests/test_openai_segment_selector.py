"""Tests for the OpenAI clip-selection adapter without network access."""

from types import SimpleNamespace
from typing import cast

import pytest
from openai import OpenAI

from content_pipeline.config import Settings
from content_pipeline.core.clips import OpenAISegmentSelector, SegmentSelector
from content_pipeline.domain.clips import (
    ClipCandidateRequest,
    Transcript,
    TranscriptSegment,
)
from content_pipeline.exceptions import ConfigurationError, ProviderError


class RecordingOpenAIClient:
    """Minimal mock of the SDK client used by the adapter."""

    def __init__(self, content: str | None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def _settings() -> Settings:
    return Settings(debug=False, openai_metadata_model="test-model")


def _transcript() -> Transcript:
    return Transcript(
        segments=(
            TranscriptSegment(start_seconds=0, end_seconds=5, text="intro"),
            TranscriptSegment(start_seconds=5, end_seconds=20, text="the main point"),
        ),
        language="en",
        duration_seconds=20,
    )


def _request() -> ClipCandidateRequest:
    return ClipCandidateRequest(
        maximum_clips=2, minimum_duration_seconds=5, maximum_duration_seconds=15
    )


def test_selector_translates_a_mocked_sdk_response() -> None:
    client = RecordingOpenAIClient(
        '{"clips": [{"start_seconds": 5, "end_seconds": 18, "title": "Big idea", '
        '"reason": "clear hook", "score": 0.9}]}'
    )
    selector: SegmentSelector = OpenAISegmentSelector(_settings(), cast(OpenAI, client))

    plan = selector.select(_transcript(), _request())

    assert len(plan.selections) == 1
    selection = plan.selections[0]
    assert selection.title == "Big idea"
    assert selection.start_seconds == 5.0
    assert selection.end_seconds == 18.0
    assert client.calls[0]["model"] == "test-model"
    messages = cast(list[dict[str, str]], client.calls[0]["messages"])
    assert "Maximum clips: 2" in messages[1]["content"]


def test_selector_rejects_clips_beyond_transcript_duration() -> None:
    client = RecordingOpenAIClient(
        '{"clips": [{"start_seconds": 5, "end_seconds": 999, "title": "t", '
        '"reason": "r", "score": 0.5}]}'
    )
    selector = OpenAISegmentSelector(_settings(), cast(OpenAI, client))

    with pytest.raises(ProviderError, match="beyond the transcript duration"):
        selector.select(_transcript(), _request())


def test_selector_translates_sdk_and_response_failures() -> None:
    failing = OpenAISegmentSelector(
        _settings(), cast(OpenAI, RecordingOpenAIClient(None, RuntimeError("boom")))
    )
    with pytest.raises(ProviderError, match="OpenAI segment selection failed"):
        failing.select(_transcript(), _request())

    malformed = OpenAISegmentSelector(
        _settings(), cast(OpenAI, RecordingOpenAIClient("not json"))
    )
    with pytest.raises(ProviderError, match="malformed clip-selection JSON"):
        malformed.select(_transcript(), _request())

    empty = OpenAISegmentSelector(
        _settings(), cast(OpenAI, RecordingOpenAIClient('{"clips": []}'))
    )
    with pytest.raises(ProviderError, match="no clip selections"):
        empty.select(_transcript(), _request())


def test_selector_requires_configured_key_only_when_creating_sdk_client() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        OpenAISegmentSelector(_settings())
