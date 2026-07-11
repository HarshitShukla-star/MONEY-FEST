"""Validation of normalized caption results."""

from content_pipeline.domain.captions.exceptions import CaptionValidationError
from content_pipeline.domain.captions.models import (
    CaptionRequest,
    CaptionResponse,
    CaptionTask,
)
from content_pipeline.domain.models.validation import normalize_hashtags, validate_title


class CaptionValidator:
    """Validate parsed content against its provider-neutral request contract."""

    def validate(
        self, request: CaptionRequest, response: CaptionResponse
    ) -> CaptionResponse:
        """Validate a parsed response and return its normalized immutable value."""
        if request.prompt.task is not response.task:
            raise CaptionValidationError(
                "Response task does not match the request task"
            )
        text = response.text.strip()
        hashtags = normalize_hashtags(response.hashtags, CaptionValidationError)
        if response.task is CaptionTask.HASHTAGS:
            if not hashtags:
                raise CaptionValidationError("Hashtag response must not be empty")
        elif not text:
            raise CaptionValidationError("Caption response must not be empty")
        if response.task is CaptionTask.TITLE:
            text = validate_title(text, CaptionValidationError)
        maximum = request.options.maximum_characters
        if maximum is not None and len(text) > maximum:
            raise CaptionValidationError(
                f"Caption response must not exceed {maximum} characters"
            )
        return CaptionResponse(
            task=response.task, text=text, hashtags=hashtags, fields=response.fields
        )
