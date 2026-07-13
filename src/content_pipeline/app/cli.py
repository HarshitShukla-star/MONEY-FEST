"""Command-line entrypoint for the content pipeline.

This is the runnable delivery mechanism the README describes as missing:
``python -m content_pipeline`` (or the installed ``content-pipeline``
console script) gives an operator a way to authenticate with YouTube, manage
channels, scan trends, and run the full clip -> metadata -> upload pipeline
against a local source video, without writing any Python.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from content_pipeline.app.composition import (
    build_channel_manager,
    build_clip_cutting_service,
    build_metadata_provider,
    build_trend_service,
    build_upload_service,
    require_gemini_key,
)
from content_pipeline.app.server import serve
from content_pipeline.app.oauth import SCOPE_READONLY, SCOPE_UPLOAD, run_oauth_login
from content_pipeline.app.pipeline import ContentPipeline, PipelineRunRequest
from content_pipeline.config import get_settings
from content_pipeline.core.channels.models import Channel
from content_pipeline.domain.effects import (
    EffectPlan,
    TransitionEffect,
    TransitionStyle,
    ZoomEffect,
    ZoomStyle,
)
from content_pipeline.domain.metadata import Visibility
from content_pipeline.exceptions import ApplicationError
from content_pipeline.logging import configure_logging, get_logger

_LOGGER = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the requested command, and return a process exit code."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = cast(
        "Callable[[argparse.Namespace], int] | None", getattr(args, "handler", None)
    )
    if handler is None:
        parser.print_help()
        return 1
    try:
        return handler(args)
    except ApplicationError as exc:
        _LOGGER.error("command_failed", extra={"command": args.command})
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content-pipeline",
        description="Scan trends, cut clips, generate metadata, and upload to YouTube.",
    )
    subparsers = parser.add_subparsers(dest="command")

    oauth_parser = subparsers.add_parser(
        "oauth-login", help="Run the interactive YouTube OAuth consent flow."
    )
    oauth_parser.set_defaults(handler=_handle_oauth_login)

    serve_parser = subparsers.add_parser(
        "serve", help="Start the local JSON API for the frontend console."
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.set_defaults(handler=_handle_serve)

    channel_parser = subparsers.add_parser(
        "channels", help="Manage publishing channels."
    )
    channel_subparsers = channel_parser.add_subparsers(dest="channels_command")

    add_parser = channel_subparsers.add_parser("add", help="Register a new channel.")
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--platform", required=True)
    add_parser.add_argument("--credential-reference", default=None)
    add_parser.add_argument("--set-default", action="store_true")
    add_parser.set_defaults(handler=_handle_channels_add)

    list_parser = channel_subparsers.add_parser(
        "list", help="List registered channels."
    )
    list_parser.set_defaults(handler=_handle_channels_list)

    trends_parser = subparsers.add_parser(
        "trends", help="Scan currently trending topics."
    )
    trends_parser.add_argument("--limit", type=int, default=10)
    trends_parser.add_argument("--region", default="US")
    trends_parser.add_argument(
        "--api-key",
        default=None,
        help="YouTube Data API key. Falls back to the stored OAuth token if omitted.",
    )
    trends_parser.set_defaults(handler=_handle_trends)

    run_parser = subparsers.add_parser(
        "run", help="Run the full pipeline for one local source video."
    )
    run_parser.add_argument("--source-video", required=True, type=Path)
    run_parser.add_argument("--channel-id", required=True)
    run_parser.add_argument("--output-dir", required=True, type=Path)
    run_parser.add_argument("--max-clips", type=int, default=3)
    run_parser.add_argument("--min-duration", type=float, default=15.0)
    run_parser.add_argument("--max-duration", type=float, default=90.0)
    run_parser.add_argument("--topic-hint", default=None)
    run_parser.add_argument("--language", default="en")
    run_parser.add_argument("--category", default="general")
    run_parser.add_argument(
        "--visibility",
        choices=[value.value for value in Visibility],
        default=Visibility.PRIVATE.value,
    )
    run_parser.add_argument("--burn-subtitles", action="store_true")
    run_parser.add_argument(
        "--zoom",
        choices=[style.value for style in ZoomStyle if style is not ZoomStyle.NONE],
        default=None,
        help="Apply a Ken-Burns-style zoom/pan to every clip.",
    )
    run_parser.add_argument("--zoom-intensity", type=float, default=0.15)
    run_parser.add_argument(
        "--transition",
        choices=[
            style.value
            for style in TransitionStyle
            if style is not TransitionStyle.NONE
        ],
        default=None,
        help="Apply a fade transition at the edges of every clip.",
    )
    run_parser.add_argument("--transition-duration", type=float, default=0.5)
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Cut clips and generate metadata, but do not upload.",
    )
    run_parser.set_defaults(handler=_handle_run)

    return parser


def _handle_oauth_login(args: argparse.Namespace) -> int:
    settings = get_settings()
    token_path = run_oauth_login(settings, scopes=(SCOPE_UPLOAD, SCOPE_READONLY))
    print(f"YouTube OAuth token saved to {token_path}")
    return 0


def _handle_serve(args: argparse.Namespace) -> int:
    serve(host=args.host, port=args.port)
    return 0


def _handle_channels_add(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = build_channel_manager(settings)
    channel: Channel = manager.create_channel(
        name=args.name,
        platform=args.platform,
        credential_reference=args.credential_reference,
    )
    if args.set_default:
        channel = manager.set_default_channel(channel.id)
    print(f"Created channel {channel.id} ({channel.name} / {channel.platform})")
    return 0


def _handle_channels_list(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = build_channel_manager(settings)
    for channel in manager.list_channels():
        marker = "*" if channel.is_default else " "
        state = "enabled" if channel.enabled else "disabled"
        print(f"{marker} {channel.id}  {channel.name}  [{channel.platform}]  {state}")
    return 0


def _handle_trends(args: argparse.Namespace) -> int:
    settings = get_settings()
    service = build_trend_service(
        settings, youtube_api_key=args.api_key, region_code=args.region
    )
    snapshot = service.scan(limit_per_provider=args.limit)
    for candidate in snapshot.top(args.limit):
        print(f"{candidate.score:>12.0f}  {candidate.topic}")
    return 0


def _build_effects_plan(args: argparse.Namespace) -> EffectPlan | None:
    """Build an EffectPlan from CLI flags, or None if no effects were requested."""
    if args.zoom is None and args.transition is None:
        return None
    return EffectPlan(
        zoom=(
            ZoomEffect(style=ZoomStyle(args.zoom), intensity=args.zoom_intensity)
            if args.zoom is not None
            else None
        ),
        transition=(
            TransitionEffect(
                style=TransitionStyle(args.transition),
                duration_seconds=args.transition_duration,
            )
            if args.transition is not None
            else None
        ),
    )


def _handle_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    require_gemini_key(settings)
    channels = build_channel_manager(settings)
    pipeline = ContentPipeline(
        clip_service=build_clip_cutting_service(settings),
        metadata_provider=build_metadata_provider(settings),
        channels=channels,
        upload_service=(
            None if args.dry_run else build_upload_service(settings, channels)
        ),
    )
    request = PipelineRunRequest(
        source_video=args.source_video,
        channel_id=args.channel_id,
        output_directory=args.output_dir,
        maximum_clips=args.max_clips,
        minimum_duration_seconds=args.min_duration,
        maximum_duration_seconds=args.max_duration,
        topic_hint=args.topic_hint,
        language=args.language,
        category=args.category,
        visibility=Visibility(args.visibility),
        burn_subtitles=args.burn_subtitles,
        effects_plan=_build_effects_plan(args),
        publish=not args.dry_run,
    )
    outcomes = pipeline.run(request)
    for outcome in outcomes:
        status = (
            outcome.upload_response.result.value
            if outcome.upload_response is not None
            else "not-published"
        )
        url = outcome.upload_response.external_url if outcome.upload_response else ""
        print(f"{outcome.cut_result.output_video}  {status}  {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
