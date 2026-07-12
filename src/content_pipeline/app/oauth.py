"""YouTube OAuth client construction.

This module is the application composition concern the README and
architecture docs call out as deliberately excluded from ``core`` and
``domain``: constructing an authenticated Google API client, persisting an
OAuth token, and refreshing it belong to the delivery layer, not to the
provider adapters that consume an already-authenticated client.

``core.trends.youtube_provider`` and ``core.uploads.youtube_provider`` accept
any object satisfying their minimal ``YouTubeClient`` protocol. The functions
here build a real ``googleapiclient`` resource that satisfies that protocol
and hand it to the adapters at the composition root.
"""

from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import Resource, build  # type: ignore[import-untyped]

from content_pipeline.config import Settings
from content_pipeline.exceptions import AuthenticationError, ConfigurationError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)

SCOPE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"

_API_SERVICE_NAME = "youtube"
_API_VERSION = "v3"


def run_oauth_login(
    settings: Settings, *, scopes: tuple[str, ...] = (SCOPE_UPLOAD, SCOPE_READONLY)
) -> Path:
    """Run the interactive OAuth consent flow and persist a refreshable token.

    Opens a local browser flow using the operator's own OAuth client secrets
    file. The resulting token (including its refresh token) is written to
    ``settings.youtube_oauth_token_path`` so future runs can build an
    authenticated client without repeating the interactive consent step.
    """
    client_secrets_path = _require_client_secrets_path(settings)
    token_path = _require_token_path(settings)
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_path), scopes=list(scopes)
    )
    try:
        credentials = flow.run_local_server(port=0)
    except Exception as exc:  # pragma: no cover - interactive browser flow
        raise AuthenticationError("YouTube OAuth consent flow failed") from exc
    _save_credentials(credentials, token_path)
    _LOGGER.info("youtube_oauth_login_completed", extra={"token_path": str(token_path)})
    return token_path


def build_youtube_client(settings: Settings) -> Resource:
    """Build an authenticated YouTube Data API client from a stored token.

    Raises:
        ConfigurationError: If no token has been stored yet (run OAuth login).
        AuthenticationError: If the stored token is present but not usable.
    """
    token_path = _require_token_path(settings)
    if not token_path.is_file():
        raise ConfigurationError(
            "No stored YouTube OAuth token was found at "
            f"{token_path}. Run the 'oauth login' command first."
        )
    credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
        str(token_path)
    )
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError as exc:
                raise AuthenticationError(
                    "Stored YouTube OAuth token could not be refreshed; "
                    "run the 'oauth login' command again"
                ) from exc
            _save_credentials(credentials, token_path)
        else:
            raise AuthenticationError(
                "Stored YouTube OAuth token is invalid; "
                "run the 'oauth login' command again"
            )
    return build(_API_SERVICE_NAME, _API_VERSION, credentials=credentials)


def build_youtube_client_with_api_key(api_key: str) -> Resource:
    """Build a read-only YouTube Data API client authenticated by API key.

    Public endpoints such as the trending chart do not require a signed-in
    user, so trend detection can run without the interactive OAuth flow.
    """
    if not isinstance(api_key, str) or not api_key.strip():
        raise ConfigurationError("A non-empty YouTube API key is required")
    return build(_API_SERVICE_NAME, _API_VERSION, developerKey=api_key.strip())


def _save_credentials(credentials: Credentials, token_path: Path) -> None:
    """Persist a token to disk so future runs can skip interactive consent."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")  # type: ignore[no-untyped-call]


def _require_client_secrets_path(settings: Settings) -> Path:
    path = settings.youtube_oauth_client_secrets_path
    if path is None or not path.is_file():
        raise ConfigurationError(
            "YOUTUBE_OAUTH_CLIENT_SECRETS_PATH must reference an existing "
            "OAuth client secrets file"
        )
    return path


def _require_token_path(settings: Settings) -> Path:
    path = settings.youtube_oauth_token_path
    if path is None:
        raise ConfigurationError("YOUTUBE_OAUTH_TOKEN_PATH must be configured")
    return path
