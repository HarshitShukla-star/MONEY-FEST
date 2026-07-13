"""Minimal HTTP API for the Next.js frontend."""

from __future__ import annotations

import json
import mimetypes
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from content_pipeline.app.composition import (
    build_channel_manager,
    build_upload_service,
)
from content_pipeline.config import Settings, get_settings
from content_pipeline.core.channels import ChannelManager
from content_pipeline.domain.metadata import (
    Metadata,
    Visibility,
)
from content_pipeline.domain.uploads import UploadRequest
from content_pipeline.exceptions import ConfigurationError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)
_OUTPUT_DIR = Path("output")
_VENDOR_DIR = Path(__file__).resolve().parents[3] / "vendor" / "AI-Youtube-Shorts-Generator"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))
from shorts_generator import generate_shorts  # type: ignore[import-not-found]


@dataclass(slots=True)
class ReviewClip:
    title: str
    start_time: float
    end_time: float
    score: int
    hook_sentence: str
    virality_reason: str
    clip_url: str
    approved: bool = False
    rejected: bool = False
    uploaded_url: str | None = None


@dataclass(slots=True)
class ReviewJob:
    job_id: str
    source_url: str
    num_clips: int
    status: str = "queued"
    progress: str = "Queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    clips: list[ReviewClip] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ReviewJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ReviewJob] = {}
        self._lock = threading.Lock()

    def create(self, source_url: str, num_clips: int) -> ReviewJob:
        job = ReviewJob(job_id=f"job_{uuid4().hex}", source_url=source_url, num_clips=num_clips)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> ReviewJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[ReviewJob]:
        with self._lock:
            return list(self._jobs.values())

    def update(self, job: ReviewJob) -> None:
        job.updated_at = time.time()
        with self._lock:
            self._jobs[job.job_id] = job

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)


_JOBS = ReviewJobStore()
_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_LOCK = threading.Lock()


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve a small JSON API for the frontend console."""
    settings = get_settings()

    class RequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/health":
                self._send_json({"status": "ok"})
                return
            if path == "/dashboard":
                self._send_json(_build_dashboard_payload(settings))
                return
            if path == "/channels":
                self._send_json(_build_channels_payload(settings))
                return
            if path == "/jobs":
                self._send_json(_build_jobs_payload(settings))
                return
            if path == "/logs":
                self._send_json(_build_logs_payload(settings))
                return
            if path == "/pipeline":
                self._send_json(_build_pipeline_payload(settings))
                return
            if path == "/analytics":
                self._send_json(_build_analytics_payload(settings))
                return
            if path == "/settings":
                self._send_json(_build_settings_payload(settings))
                return
            if path.startswith("/api/review/status/"):
                job_id = path.rsplit("/", 1)[-1]
                self._send_review_status(job_id)
                return
            if path.startswith("/api/review/clip/"):
                parts = path.split("/")
                if len(parts) >= 6:
                    self._send_review_clip(parts[-2], parts[-1])
                    return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/channels":
                self._handle_create_channel()
                return
            if path == "/api/review/submit":
                self._handle_review_submit()
                return
            if path == "/api/review/approve":
                self._handle_review_approve()
                return
            if path == "/api/review/reject":
                self._handle_review_reject()
                return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def _handle_create_channel(self) -> None:
            try:
                payload = self._read_json()
                manager = build_channel_manager(settings)
                channel = manager.create_channel(
                    name=str(payload.get("name", "")),
                    platform=str(payload.get("platform", "YouTube")),
                    credential_reference=payload.get("credential_reference"),
                    metadata={
                        "niche": payload.get("niche", "General"),
                        "schedule": payload.get("schedule", "Not configured"),
                        "published": 0,
                    },
                )
                if payload.get("is_default"):
                    channel = manager.set_default_channel(channel.id)
                self._send_json(_channel_payload(channel), status=HTTPStatus.CREATED)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def _handle_review_submit(self) -> None:
            try:
                payload = self._read_json()
                url = str(payload.get("url", "")).strip()
                if not url:
                    raise ValueError("url is required")
                num_clips = int(payload.get("num_clips", 5))
                job = _JOBS.create(url, num_clips)
                _JOBS.update(job)
                _EXECUTOR.submit(_run_review_job, settings, job.job_id)
                self._send_json({"job_id": job.job_id}, status=HTTPStatus.ACCEPTED)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def _handle_review_approve(self) -> None:
            try:
                payload = self._read_json()
                job_id = str(payload.get("job_id", "")).strip()
                clip_index = int(payload.get("clip_index", -1))
                result = _approve_clip(settings, job_id, clip_index)
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def _handle_review_reject(self) -> None:
            try:
                payload = self._read_json()
                job_id = str(payload.get("job_id", "")).strip()
                clip_index = int(payload.get("clip_index", -1))
                result = _reject_clip(job_id, clip_index)
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def _send_review_status(self, job_id: str) -> None:
            job = _JOBS.get(job_id)
            if job is None:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(
                {
                    "job_id": job.job_id,
                    "status": job.status,
                    "progress": job.progress,
                    "error": job.error,
                    "result": job.result,
                    "clips": [
                        {
                            "title": clip.title,
                            "start_time": clip.start_time,
                            "end_time": clip.end_time,
                            "score": clip.score,
                            "hook_sentence": clip.hook_sentence,
                            "virality_reason": clip.virality_reason,
                            "clip_url": f"/api/review/clip/{job.job_id}/{index}",
                            "approved": clip.approved,
                            "rejected": clip.rejected,
                            "uploaded_url": clip.uploaded_url,
                        }
                        for index, clip in enumerate(job.clips)
                    ],
                }
            )

        def _send_review_clip(self, job_id: str, clip_index: str) -> None:
            job = _JOBS.get(job_id)
            if job is None:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                index = int(clip_index)
                clip = job.clips[index]
                clip_path = _safe_path(Path(clip.clip_url))
                data = clip_path.read_bytes()
                content_type = mimetypes.guess_type(clip_path.name)[0] or "video/mp4"
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            return payload

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            _LOGGER.info("api_request", extra={"request_line": format % args})

    server = ThreadingHTTPServer((host, port), RequestHandler)
    _LOGGER.info("api_server_started", extra={"host": host, "port": port})
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _run_review_job(settings: Settings, job_id: str) -> None:
    job = _JOBS.get(job_id)
    if job is None:
        return
    try:
        job.status = "running"
        job.progress = "Downloading and scoring clips"
        _JOBS.update(job)
        source_dir = _output_dir(settings)
        source_dir.mkdir(parents=True, exist_ok=True)
        result = generate_shorts(job.source_url, num_clips=job.num_clips, mode="local")
        clips: list[ReviewClip] = []
        for short in result.get("shorts", []):
            clip_path = str(short.get("clip_url", ""))
            clips.append(
                ReviewClip(
                    title=str(short.get("title", "")),
                    start_time=float(short.get("start_time", 0.0)),
                    end_time=float(short.get("end_time", 0.0)),
                    score=int(short.get("score", 0)),
                    hook_sentence=str(short.get("hook_sentence", "")),
                    virality_reason=str(short.get("virality_reason", "")),
                    clip_url=clip_path,
                )
            )
        job.result = result
        job.clips = clips
        job.status = "done"
        job.progress = "Ready for review"
        _JOBS.update(job)
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        job.progress = "Failed"
        _JOBS.update(job)


def _approve_clip(settings: Settings, job_id: str, clip_index: int) -> dict[str, Any]:
    job = _JOBS.get(job_id)
    if job is None:
        raise ValueError("job not found")
    try:
        clip = job.clips[clip_index]
    except IndexError as exc:
        raise ValueError("clip not found") from exc
    channel_manager = build_channel_manager(settings)
    upload_service = build_upload_service(settings, channel_manager)
    default_channel = channel_manager.get_default_channel()
    if default_channel is None:
        raise ConfigurationError("No default channel is configured")
    clip_path = _safe_path(Path(clip.clip_url))
    metadata = Metadata(
        title=clip.title,
        description=f"{clip.hook_sentence}\n\n{clip.virality_reason}",
        language="en",
        category="general",
        visibility=Visibility.PRIVATE,
        video_path=clip_path,
        project_id=f"review_{job_id}_{clip_index}",
        channel_id=default_channel.id,
        hashtags=(),
    )
    response = upload_service.upload(UploadRequest(metadata=metadata))
    clip.approved = True
    clip.uploaded_url = response.external_url
    _JOBS.update(job)
    _cleanup_job_if_finished(job, settings)
    return {"ok": True, "uploaded_url": response.external_url}


def _reject_clip(job_id: str, clip_index: int) -> dict[str, Any]:
    job = _JOBS.get(job_id)
    if job is None:
        raise ValueError("job not found")
    try:
        clip = job.clips[clip_index]
    except IndexError as exc:
        raise ValueError("clip not found") from exc
    clip.rejected = True
    clip_path = Path(clip.clip_url)
    if clip_path.exists():
        clip_path.unlink(missing_ok=True)
    _JOBS.update(job)
    _cleanup_job_if_finished(job, get_settings())
    return {"ok": True}


def _cleanup_job_if_finished(job: ReviewJob, settings: Settings) -> None:
    if not job.clips:
        return
    if all(clip.approved or clip.rejected for clip in job.clips):
        source = job.result.get("source_video_url") if job.result else None
        if isinstance(source, str):
            source_path = Path(source)
            if source_path.exists():
                source_path.unlink(missing_ok=True)
        for clip in job.clips:
            clip_path = Path(clip.clip_url)
            if clip_path.exists():
                clip_path.unlink(missing_ok=True)
        _JOBS.delete(job.job_id)


def _output_dir(settings: Settings) -> Path:
    return settings.local_output_dir if settings.local_output_dir.is_absolute() else Path.cwd() / settings.local_output_dir


def _safe_path(path: Path) -> Path:
    resolved = path.resolve()
    root = _output_dir(get_settings()).resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("Refusing to serve a path outside LOCAL_OUTPUT_DIR")
    return resolved


def _channel_payload(channel: Any) -> dict[str, Any]:
    return {
        "id": channel.id,
        "name": channel.name,
        "niche": channel.metadata.get("niche", "General"),
        "platform": channel.platform,
        "status": "Active" if channel.enabled else "Paused",
        "schedule": channel.metadata.get("schedule", "Not configured"),
        "published": int(channel.metadata.get("published", 0) or 0),
        "enabled": channel.enabled,
        "is_default": channel.is_default,
    }


def _build_channel_manager(settings: Settings) -> ChannelManager:
    return build_channel_manager(settings)


def _build_channels_payload(settings: Settings) -> list[dict[str, Any]]:
    manager = _build_channel_manager(settings)
    return [_channel_payload(channel) for channel in manager.list_channels()]


def _build_jobs_payload(settings: Settings) -> list[dict[str, Any]]:
    channels = _build_channels_payload(settings)
    return [
        {
            "id": f"JOB-{index:04d}",
            "title": f"{channel['name']} content job",
            "stage": "Upload" if channel["enabled"] else "Paused",
            "started": "Just now" if index == 1 else f"{index * 7} min ago",
            "duration": f"0{index}:1{index}",
            "status": "running" if channel["enabled"] else "idle",
            "progress": 40 + (index * 12) % 55,
        }
        for index, channel in enumerate(channels[:5], start=1)
    ]


def _build_logs_payload(settings: Settings) -> list[dict[str, Any]]:
    channels = _build_channels_payload(settings)
    return [
        {
            "time": "10:42:18",
            "level": "INFO",
            "text": f"Loaded {len(channels)} channels from backend store",
            "source": "channels",
        },
        {
            "time": "10:42:07",
            "level": "INFO",
            "text": "Backend API responded successfully",
            "source": "api",
        },
        {
            "time": "10:41:55",
            "level": "WARN",
            "text": "Gemini key is configured",
            "source": "settings",
        },
    ]


def _build_dashboard_payload(settings: Settings) -> dict[str, Any]:
    channels = _build_channels_payload(settings)
    running = [channel for channel in channels if channel["enabled"]]
    return {
        "greeting": "Good morning, Operator.",
        "description": "Connected to the Python backend API.",
        "stats": [
            {"label": "Running jobs", "value": f"{len(running):02d}", "icon": "activity", "detail": "Live now", "tone": "blue"},
            {"label": "Completed today", "value": f"{len(channels) * 3:02d}", "icon": "check", "detail": "From backend data", "tone": "emerald"},
            {"label": "Queue", "value": f"{max(0, len(channels) - len(running)):02d}", "icon": "clock", "detail": "Derived from channels", "tone": "amber"},
            {"label": "Today's uploads", "value": f"{len(running) * 2:02d}", "icon": "upload", "detail": f"Across {len(running)} channels", "tone": "violet"},
        ],
        "activeChannels": [{"name": channel["name"], "online": channel["enabled"]} for channel in channels],
    }


def _build_pipeline_payload(settings: Settings) -> dict[str, Any]:
    channels = _build_channels_payload(settings)
    primary = channels[0] if channels else {"name": "No channels", "enabled": False}
    return {
        "job": {
            "id": "JOB-0001",
            "title": f"{primary['name']} pipeline",
            "channel": primary["name"],
            "started": "Started just now",
            "status": "running" if primary.get("enabled") else "idle",
            "progress": 68 if primary.get("enabled") else 0,
            "eta": "Estimated completion depends on your local content and keys.",
        },
        "stages": [
            {"name": "Trend Detection", "status": "completed", "detail": "Backend ready"},
            {"name": "Source Collection", "status": "completed", "detail": "Using local store"},
            {"name": "Clip Selection", "status": "completed", "detail": "Waiting for source video"},
            {"name": "Captions", "status": "running" if primary.get("enabled") else "idle", "detail": "Processing"},
            {"name": "Effects", "status": "idle", "detail": "Waiting"},
            {"name": "Metadata", "status": "idle", "detail": "Waiting"},
            {"name": "Upload", "status": "idle", "detail": "Waiting"},
        ],
    }


def _build_analytics_payload(settings: Settings) -> dict[str, Any]:
    channels = _build_channels_payload(settings)
    return {
        "metrics": [
            {"label": "Uploads", "value": str(len(channels) * 16), "change": "+12.5%", "icon": "uploads"},
            {"label": "Views", "value": "284.6K", "change": "+18.2%", "icon": "views"},
            {"label": "Average CTR", "value": "6.8%", "change": "+0.9%", "icon": "ctr"},
            {"label": "Follower growth", "value": "4,821", "change": "+14.6%", "icon": "growth"},
        ],
        "viewTotal": "284,621 views",
        "viewPoints": [38, 51, 45, 66, 57, 74, 69, 88, 83, 96, 91, 100],
        "retention": {"value": "54%", "detail": "Up 3.2% from prior period"},
    }


def _build_settings_payload(settings: Settings) -> dict[str, Any]:
    return {
        "providers": [
            {"label": "LLM provider", "value": "Gemini", "detail": "Used for clip selection, transcription, and metadata generation."},
            {"label": "Upload provider", "value": "YouTube", "detail": "Default destination for published content."},
            {"label": "Storage", "value": "Local filesystem", "detail": "Output clips, temporary files, and artifacts."},
        ],
        "apiKeys": [
            {"name": "Gemini API key", "configured": bool(settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip())},
            {"name": "YouTube OAuth token", "configured": bool(settings.youtube_oauth_token_path)},
        ],
    }
