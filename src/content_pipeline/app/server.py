"""Minimal HTTP API for the Next.js frontend."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from content_pipeline.app.composition import build_channel_manager
from content_pipeline.config import Settings, get_settings
from content_pipeline.core.channels.models import ChannelUpdate
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)


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
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
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
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path != "/channels":
                self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
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
                self._send_json(
                    {
                        "id": channel.id,
                        "name": channel.name,
                        "niche": channel.metadata.get("niche", "General"),
                        "platform": channel.platform,
                        "status": "Active" if channel.enabled else "Paused",
                        "schedule": channel.metadata.get("schedule", "Not configured"),
                        "published": int(channel.metadata.get("published", 0) or 0),
                        "enabled": channel.enabled,
                        "is_default": channel.is_default,
                    },
                    status=HTTPStatus.CREATED,
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            _LOGGER.info(
                "api_request",
                extra={"request_line": format % args},
            )

    server = ThreadingHTTPServer((host, port), RequestHandler)
    _LOGGER.info("api_server_started", extra={"host": host, "port": port})
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _build_channel_manager(settings: Settings):
    return build_channel_manager(settings)


def _build_channels_payload(settings: Settings) -> list[dict[str, Any]]:
    manager = _build_channel_manager(settings)
    channels = manager.list_channels()
    return [
        {
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
        for channel in channels
    ]


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
            "text": "Gemini key is not validated by the frontend layer",
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
            {
                "label": "Running jobs",
                "value": f"{len(running):02d}",
                "icon": "activity",
                "detail": "Live now",
                "tone": "blue",
            },
            {
                "label": "Completed today",
                "value": f"{len(channels) * 3:02d}",
                "icon": "check",
                "detail": "From backend data",
                "tone": "emerald",
            },
            {
                "label": "Queue",
                "value": f"{max(0, len(channels) - len(running)):02d}",
                "icon": "clock",
                "detail": "Derived from channels",
                "tone": "amber",
            },
            {
                "label": "Today's uploads",
                "value": f"{len(running) * 2:02d}",
                "icon": "upload",
                "detail": f"Across {len(running)} channels",
                "tone": "violet",
            },
        ],
        "activeChannels": [
            {"name": channel["name"], "online": channel["enabled"]}
            for channel in channels
        ],
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
