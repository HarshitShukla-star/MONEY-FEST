"""Strict JSON serialization helpers."""

import json
from pathlib import Path
from typing import Any

from content_pipeline.exceptions import ValidationError


def read_json(path: Path) -> Any:
    """Read UTF-8 JSON from a file, raising a domain-specific error if malformed."""
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Unable to read JSON from: {path}") from exc


def write_json(path: Path, value: Any) -> None:
    """Write JSON atomically enough for ordinary single-process application use."""
    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2, default=str)
            file.write("\n")
    except OSError as exc:
        raise ValidationError(f"Unable to write JSON to: {path}") from exc
