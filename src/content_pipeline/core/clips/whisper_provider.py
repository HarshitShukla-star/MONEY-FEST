"""OpenAI Whisper adapter for the provider-neutral transcription port."""

from pathlib import Path
from typing import Any

from openai import OpenAI

from content_pipeline.config import Settings
from content_pipeline.core.clips.provider import TranscriptionProvider
from content_pipeline.domain.clips import Transcript, TranscriptSegment
from content_pipeline.exceptions import ConfigurationError, ProviderError
from content_pipeline.logging import get_logger
from content_pipeline.utils.files import require_file

_LOGGER = get_logger(__name__)


class WhisperTranscriptionProvider(TranscriptionProvider):
    """Translate OpenAI Whisper transcription output into a neutral Transcript."""

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
                "OPENAI_API_KEY is required for the Whisper transcription provider"
            )
        self._client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def transcribe(self, source_video: Path) -> Transcript:
        """Transcribe ``source_video`` and return a validated, timed transcript."""
        source = require_file(source_video)
        try:
            with source.open("rb") as handle:
                response = self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=handle,
                    response_format="verbose_json",
                )
        except ProviderError:
            raise
        except Exception as exc:
            _LOGGER.error(
                "whisper_transcription_failed", extra={"source_video": str(source)}
            )
            raise ProviderError("Whisper transcription failed") from exc
        transcript = _parse_response(response)
        _LOGGER.info(
            "transcription_completed",
            extra={"provider": "openai", "source_video": str(source)},
        )
        return transcript


def _parse_response(response: Any) -> Transcript:
    """Convert a Whisper verbose-JSON response into a neutral Transcript."""
    payload = response if isinstance(response, dict) else response.model_dump()
    language = payload.get("language")
    duration = payload.get("duration")
    raw_segments = payload.get("segments")
    if (
        not isinstance(language, str)
        or not isinstance(duration, (int, float))
        or not isinstance(raw_segments, list)
    ):
        raise ProviderError("Whisper returned an incomplete transcription response")
    segments: list[TranscriptSegment] = []
    for raw_segment in raw_segments:
        if not isinstance(raw_segment, dict):
            raise ProviderError("Whisper returned a malformed transcript segment")
        start = raw_segment.get("start")
        end = raw_segment.get("end")
        text = raw_segment.get("text")
        if (
            not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ProviderError("Whisper returned a malformed transcript segment")
        segments.append(
            TranscriptSegment(start_seconds=start, end_seconds=end, text=text)
        )
    try:
        return Transcript(
            segments=tuple(segments), language=language, duration_seconds=duration
        )
    except Exception as exc:
        raise ProviderError("Whisper transcript failed validation") from exc
