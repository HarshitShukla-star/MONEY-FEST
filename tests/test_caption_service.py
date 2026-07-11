"""Behavioural tests for CaptionService orchestration only."""

from collections.abc import Mapping
from typing import cast

import pytest

from content_pipeline.core.captions import CaptionService
from content_pipeline.core.captions.parsers import ResponseParser
from content_pipeline.core.captions.provider import CaptionProvider
from content_pipeline.domain.captions import (
    CaptionGenerationOptions,
    CaptionParseError,
    CaptionPrompt,
    CaptionRequest,
    CaptionResponse,
    CaptionTask,
    CaptionValidationError,
    CaptionValidator,
    PromptBuilder,
    ProviderResponse,
    ResponseFormat,
)


class RecordingProvider:
    """In-memory test double for the injected provider port."""

    def __init__(self, response: ProviderResponse) -> None:
        self.response = response
        self.requests: list[CaptionRequest] = []

    def generate(self, request: CaptionRequest) -> ProviderResponse:
        self.requests.append(request)
        return self.response


class RecordingParser:
    """In-memory test double for the injected parser port."""

    def __init__(self, parsed: CaptionResponse) -> None:
        self.parsed = parsed
        self.calls: list[tuple[CaptionRequest, ProviderResponse]] = []

    def parse(
        self, request: CaptionRequest, response: ProviderResponse
    ) -> CaptionResponse:
        self.calls.append((request, response))
        return self.parsed


class RecordingPromptBuilder(PromptBuilder):
    """Records that the service normalizes the prompt through the builder."""

    def __init__(self) -> None:
        self.prompts: list[CaptionPrompt] = []

    def build_from_prompt(self, prompt: CaptionPrompt) -> CaptionPrompt:
        self.prompts.append(prompt)
        return super().build_from_prompt(prompt)


def _request(response_format: ResponseFormat = ResponseFormat.TEXT) -> CaptionRequest:
    return CaptionRequest(
        prompt=CaptionPrompt(
            task=CaptionTask.CAPTION,
            system_instruction="Write a caption.",
            user_instruction="Subject: automation",
            language="en",
        ),
        options=CaptionGenerationOptions(response_format=response_format),
    )


def _service(
    provider: CaptionProvider,
    parsers: Mapping[ResponseFormat, ResponseParser],
    prompt_builder: PromptBuilder | None = None,
) -> CaptionService:
    return CaptionService(
        provider=provider,
        prompt_builder=prompt_builder or PromptBuilder(),
        parsers=parsers,
        validator=CaptionValidator(),
    )


def test_service_orchestrates_dependencies_and_returns_validated_result() -> None:
    provider = RecordingProvider(ProviderResponse("raw", "fake"))
    parser = RecordingParser(CaptionResponse(CaptionTask.CAPTION, "  Final caption  "))
    builder = RecordingPromptBuilder()
    service = _service(provider, {ResponseFormat.TEXT: parser}, builder)

    result = service.generate(_request())

    assert result.text == "Final caption"
    assert builder.prompts[0].task is CaptionTask.CAPTION
    assert provider.requests[0].prompt is not builder.prompts[0]
    assert parser.calls[0][1].provider_name == "fake"


def test_service_uses_the_parser_matching_the_requested_response_format() -> None:
    provider = RecordingProvider(ProviderResponse("raw", "fake"))
    text_parser = RecordingParser(CaptionResponse(CaptionTask.CAPTION, "text"))
    json_parser = RecordingParser(CaptionResponse(CaptionTask.CAPTION, "json"))
    service = _service(
        provider,
        {ResponseFormat.TEXT: text_parser, ResponseFormat.JSON: json_parser},
    )

    result = service.generate(_request(ResponseFormat.JSON))

    assert result.text == "json"
    assert text_parser.calls == []
    assert len(json_parser.calls) == 1


def test_service_rejects_missing_parser_before_calling_provider() -> None:
    provider = RecordingProvider(ProviderResponse("raw", "fake"))
    service = _service(provider, {})

    with pytest.raises(CaptionParseError, match="No response parser"):
        service.generate(_request())

    assert provider.requests == []


def test_service_surfaces_existing_result_validation_errors() -> None:
    provider = RecordingProvider(ProviderResponse("raw", "fake"))
    parser = RecordingParser(CaptionResponse(CaptionTask.CAPTION, ""))
    service = _service(provider, {ResponseFormat.TEXT: parser})

    with pytest.raises(CaptionValidationError, match="must not be empty"):
        service.generate(_request())


def test_service_rejects_a_value_that_is_not_a_caption_request() -> None:
    service = _service(
        RecordingProvider(ProviderResponse("raw", "fake")),
        {
            ResponseFormat.TEXT: RecordingParser(
                CaptionResponse(CaptionTask.CAPTION, "ok")
            )
        },
    )

    with pytest.raises(CaptionValidationError, match="CaptionRequest"):
        service.generate(cast(CaptionRequest, object()))
