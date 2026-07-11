"""Tests for generic domain models."""

import pytest

from content_pipeline.domain.models import ErrorResponse, Result


def test_result_contains_success_value() -> None:
    result = Result(value="ready")

    assert result.is_success is True
    assert result.value == "ready"


def test_result_rejects_ambiguous_state() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Result(value="ready", error=ErrorResponse())
