"""Safe filesystem helpers."""

from pathlib import Path

from content_pipeline.exceptions import ValidationError


def ensure_directory(path: Path) -> Path:
    """Create a directory and return its resolved path."""
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def require_file(path: Path) -> Path:
    """Validate that a path exists and is a regular file."""
    if not path.is_file():
        raise ValidationError(f"Expected a file at: {path}")
    return path.resolve()
