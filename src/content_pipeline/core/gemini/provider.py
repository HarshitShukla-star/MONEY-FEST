"""Gemini adapters for transcription, clip selection, and metadata."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import requests

from content_pipeline.config import Settings
from content_pipeline.core.clips.provider import SegmentSelector, TranscriptionProvider
from content_pipeline.core.metadata.provider import MetadataProvider
from content_pipeline.domain.clips import (
    ClipCandidateRequest,
    ClipPlan,
    ClipSelection,
    Transcript,
    TranscriptSegment,
)
from content_pipeline.domain.metadata import (
    MetadataGenerationRequest,
    MetadataGenerationResult,
)
from content_pipeline.exceptions import ConfigurationError, ProviderError
from content_pipeline.logging import get_logger
from content_pipeline.utils.files import require_file

_LOGGER = get_logger(__name__)
_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
            raise ConfigurationError("GEMINI_API_KEY is required for Gemini providers")
        self._key = settings.gemini_api_key.get_secret_value()
        self._model = settings.gemini_model

    def generate(self, prompt: str, *, mime_type: str | None = None, file_path: Path | None = None) -> str:
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if file_path is not None:
            data = file_path.read_bytes()
            parts.insert(
                0,
                {
                    "inline_data": {
                        "mime_type": mime_type or "application/octet-stream",
                        "data": base64.b64encode(data).decode("ascii"),
                    }
                },
            )
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        body = self._post_with_fallbacks(payload)
        try:
            candidates = body["candidates"]
            content = candidates[0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in content)
        except Exception as exc:
            raise ProviderError("Gemini returned an invalid response") from exc
        return text.strip()

    def _post_with_fallbacks(self, payload: dict[str, Any]) -> dict[str, Any]:
        models = [self._model, "gemini-2.5-flash-lite", "gemini-2.5-flash"]
        seen: set[str] = set()
        last_error: str | None = None
        for model in models:
            if model in seen:
                continue
            seen.add(model)
            url = f"{_API_ROOT}/models/{model}:generateContent"
            response = requests.post(url, params={"key": self._key}, json=payload, timeout=120)
            if response.ok:
                return response.json()
            last_error = response.text
            if response.status_code != 404:
                break
        message = last_error or "unknown Gemini error"
        if "no longer available to new users" in message.lower():
            raise ProviderError(
                "Gemini model access is unavailable for this key. Try GEMINI_MODEL=gemini-2.5-flash-lite "
                "or create a fresh Gemini API key in AI Studio."
            )
        raise ProviderError(f"Gemini request failed: {message}")


class GeminiMetadataProvider(MetadataProvider):
    def __init__(self, settings: Settings) -> None:
        self._client = GeminiClient(settings)
        self._model = settings.gemini_model

    def generate(self, request: MetadataGenerationRequest) -> MetadataGenerationResult:
        prompt = _metadata_prompt(request)
        try:
            content = self._client.generate(prompt)
            result = _parse_metadata_result(content)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Gemini metadata generation failed") from exc
        _LOGGER.info("metadata_generated", extra={"provider": "gemini", "model": self._model})
        return result


class GeminiSegmentSelector(SegmentSelector):
    def __init__(self, settings: Settings) -> None:
        self._client = GeminiClient(settings)
        self._model = settings.gemini_model

    def select(self, transcript: Transcript, request: ClipCandidateRequest) -> ClipPlan:
        prompt = _selection_prompt(transcript, request)
        try:
            content = self._client.generate(prompt)
            plan = _parse_plan(content, transcript, request)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Gemini segment selection failed") from exc
        _LOGGER.info(
            "clip_plan_generated",
            extra={"provider": "gemini", "model": self._model, "clip_count": len(plan.selections)},
        )
        return plan


class GeminiTranscriptionProvider(TranscriptionProvider):
    def __init__(self, settings: Settings) -> None:
        self._client = GeminiClient(settings)
        self._model = settings.gemini_model

    def transcribe(self, source_video: Path) -> Transcript:
        source = require_file(source_video)
        mime_type = _guess_mime_type(source)
        prompt = (
            "Transcribe the provided video into a JSON object with fields "
            '"language" (string), "duration_seconds" (number), and "segments" '
            '([{start_seconds, end_seconds, text}]). Preserve approximate timestamps.'
        )
        try:
            content = self._client.generate(prompt, mime_type=mime_type, file_path=source)
            transcript = _parse_transcript(content)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Gemini transcription failed") from exc
        _LOGGER.info("transcription_completed", extra={"provider": "gemini", "source_video": str(source)})
        return transcript


def _metadata_prompt(request: MetadataGenerationRequest) -> str:
    context = [f"Transcript:\n{request.transcript}"]
    if request.language is not None:
        context.append(f"Language: {request.language}")
    if request.tone is not None:
        context.append(f"Tone: {request.tone}")
    if request.target_platform is not None:
        context.append(f"Target platform: {request.target_platform}")
    context.append(
        "Return JSON with exactly these fields: title (string), description (string), hashtags (array of strings)."
    )
    return "\n\n".join(context)


def _selection_prompt(transcript: Transcript, request: ClipCandidateRequest) -> str:
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
    context.append(
        "Return JSON with exactly one field clips, an array of {start_seconds, end_seconds, title, reason, score}."
    )
    context.append("Transcript:\n" + "\n".join(lines))
    return "\n\n".join(context)


def _parse_metadata_result(content: str) -> MetadataGenerationResult:
    payload = _json_payload(content)
    title = payload.get("title")
    description = payload.get("description")
    hashtags = payload.get("hashtags")
    if (
        not isinstance(title, str)
        or not isinstance(description, str)
        or not isinstance(hashtags, list)
        or not all(isinstance(item, str) for item in hashtags)
    ):
        raise ProviderError("Gemini returned invalid metadata fields")
    return MetadataGenerationResult(title=title, description=description, hashtags=cast(tuple[str, ...], tuple(hashtags)))


def _parse_transcript(content: str) -> Transcript:
    payload = _json_payload(content)
    language = payload.get("language")
    duration = payload.get("duration_seconds")
    segments = payload.get("segments")
    if not isinstance(language, str) or not isinstance(duration, (int, float)) or not isinstance(segments, list):
        raise ProviderError("Gemini returned an invalid transcript")
    parsed: list[TranscriptSegment] = []
    for raw in segments:
        if not isinstance(raw, Mapping):
            raise ProviderError("Gemini returned a malformed transcript segment")
        start = raw.get("start_seconds")
        end = raw.get("end_seconds")
        text = raw.get("text")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or not isinstance(text, str):
            raise ProviderError("Gemini returned a malformed transcript segment")
        parsed.append(TranscriptSegment(start_seconds=float(start), end_seconds=float(end), text=text))
    return Transcript(segments=tuple(parsed), language=language, duration_seconds=float(duration))


def _parse_plan(content: str, transcript: Transcript, request: ClipCandidateRequest) -> ClipPlan:
    payload = _json_payload(content)
    raw_clips = payload.get("clips")
    if not isinstance(raw_clips, list) or not raw_clips:
        raise ProviderError("Gemini returned no clip selections")
    selections: list[ClipSelection] = []
    for raw_clip in raw_clips[: request.maximum_clips]:
        if not isinstance(raw_clip, Mapping):
            raise ProviderError("Gemini returned a malformed clip selection")
        start = raw_clip.get("start_seconds")
        end = raw_clip.get("end_seconds")
        title = raw_clip.get("title")
        reason = raw_clip.get("reason")
        score = raw_clip.get("score")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or not isinstance(title, str) or not isinstance(reason, str) or not isinstance(score, (int, float)):
            raise ProviderError("Gemini returned a malformed clip selection")
        if end > transcript.duration_seconds:
            raise ProviderError("Gemini selected a clip beyond the transcript duration")
        selections.append(
            ClipSelection(
                start_seconds=float(start),
                end_seconds=float(end),
                title=title,
                reason=reason,
                score=float(score),
            )
        )
    return ClipPlan(selections=tuple(selections))


def _json_payload(content: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError("Gemini returned malformed JSON") from exc
    if not isinstance(payload, Mapping):
        raise ProviderError("Gemini returned JSON that is not an object")
    return payload


def _guess_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }.get(suffix, "application/octet-stream")
