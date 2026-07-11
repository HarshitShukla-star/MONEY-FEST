"""Business orchestration for provider-neutral caption generation."""

from collections.abc import Mapping

from content_pipeline.core.captions.parsers import ResponseParser
from content_pipeline.core.captions.provider import CaptionProvider
from content_pipeline.domain.captions import (
    CaptionRequest,
    CaptionResponse,
    CaptionValidationError,
    CaptionValidator,
    PromptBuilder,
    ResponseFormat,
)
from content_pipeline.domain.captions.exceptions import CaptionParseError
from content_pipeline.logging import get_logger

_LOGGER = get_logger(__name__)


class CaptionService:
    """Coordinate caption generation using only injected provider-neutral ports."""

    def __init__(
        self,
        provider: CaptionProvider,
        prompt_builder: PromptBuilder,
        parsers: Mapping[ResponseFormat, ResponseParser],
        validator: CaptionValidator,
    ) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder
        self._parsers = dict(parsers)
        self._validator = validator

    def generate(self, request: CaptionRequest) -> CaptionResponse:
        """Generate, parse, and validate a caption through injected dependencies."""
        if not isinstance(request, CaptionRequest):
            raise CaptionValidationError("Request must be a CaptionRequest")
        prompt = self._prompt_builder.build_from_prompt(request.prompt)
        validated_request = CaptionRequest(prompt=prompt, options=request.options)
        parser = self._parsers.get(validated_request.options.response_format)
        if parser is None:
            raise CaptionParseError(
                "No response parser is configured for "
                f"{validated_request.options.response_format.value}"
            )
        response = self._provider.generate(validated_request)
        parsed = parser.parse(validated_request, response)
        result = self._validator.validate(validated_request, parsed)
        _LOGGER.info(
            "caption_generated",
            extra={
                "task": result.task.value,
                "provider": response.provider_name,
                "response_format": validated_request.options.response_format.value,
            },
        )
        return result
