"""Tests for structured logging output."""

import json
import logging

from content_pipeline.logging.setup import JsonFormatter


def test_json_formatter_preserves_log_context() -> None:
    formatter = JsonFormatter()
    record = logging.getLogger("test.logger").makeRecord(
        "test.logger",
        logging.INFO,
        __file__,
        1,
        "Operation completed",
        (),
        None,
        extra={"operation_id": "op-123"},
    )

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "Operation completed"
    assert payload["context"] == {"operation_id": "op-123"}
