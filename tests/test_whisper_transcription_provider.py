"""Tests for the OpenAI Whisper transcription adapter without network access."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from openai import OpenAI

from content_pipeline.config import Settings
from content_pipeline.core.clips import (
    TranscriptionProvider,
    WhisperTranscriptionProvider,
)
from content_pipeline.exceptions import (
    ConfigurationError,
    ProviderError,
    ValidationError,
)


class RecordingTranscriptionClient:
    """Minimal mock of the SDK client used by the adapter."""

    def __init__(self, payload: object, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.payload


def _settings() -> Settings:
    return Settings(debug=False)


@pytest.fixture
def video(tmp_path: Path) -> Path:
    path = tmp_path / "source.mp4"
    path.touch()
    return path


def test_provider_translates_a_mocked_verbose_json_response(video: Path) -> None:
    client = RecordingTranscriptionClient(
        {
            "language": "english",
            "duration": 20.0,
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "intro"},
                {"start": 5.0, "end": 20.0, "text": "the main point"},
            ],
        }
    )
    provider: TranscriptionProvider = WhisperTranscriptionProvider(
        _settings(), cast(OpenAI, client)
    )

    transcript = provider.transcribe(video)

    assert transcript.language == "english"
    assert transcript.duration_seconds == 20.0
    assert len(transcript.segments) == 2
    assert client.calls[0]["model"] == "whisper-1"
    assert client.calls[0]["response_format"] == "verbose_json"


def test_provider_rejects_missing_source_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    provider = WhisperTranscriptionProvider(
        _settings(), cast(OpenAI, RecordingTranscriptionClient({}))
    )

    with pytest.raises(ValidationError, match="Expected a file"):
        provider.transcribe(missing)


def test_provider_translates_sdk_and_response_failures(video: Path) -> None:
    failing = WhisperTranscriptionProvider(
        _settings(),
        cast(OpenAI, RecordingTranscriptionClient(None, RuntimeError("boom"))),
    )
    with pytest.raises(ProviderError, match="Whisper transcription failed"):
        failing.transcribe(video)

    incomplete = WhisperTranscriptionProvider(
        _settings(), cast(OpenAI, RecordingTranscriptionClient({"language": "en"}))
    )
    with pytest.raises(ProviderError, match="incomplete transcription response"):
        incomplete.transcribe(video)

    malformed_segment = WhisperTranscriptionProvider(
        _settings(),
        cast(
            OpenAI,
            RecordingTranscriptionClient(
                {"language": "en", "duration": 5.0, "segments": [{"start": 0.0}]}
            ),
        ),
    )
    with pytest.raises(ProviderError, match="malformed transcript segment"):
        malformed_segment.transcribe(video)


def test_provider_requires_configured_key_only_when_creating_sdk_client() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        WhisperTranscriptionProvider(_settings())
