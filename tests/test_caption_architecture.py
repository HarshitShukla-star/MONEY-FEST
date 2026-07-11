"""Contract tests for the provider-independent caption architecture."""

from collections.abc import Mapping

import pytest

from content_pipeline.core.captions import (
    CaptionProvider,
    JsonResponseParser,
    PlainTextResponseParser,
    StructuredResponseParser,
)
from content_pipeline.domain.captions import (
    CaptionGenerationOptions,
    CaptionParseError,
    CaptionRequest,
    CaptionResponse,
    CaptionTask,
    CaptionValidationError,
    CaptionValidator,
    PromptBuilder,
    PromptRequest,
    ProviderResponse,
    ResponseFormat,
)
from content_pipeline.domain.models.json import FrozenJsonValue


def _request(
    task: CaptionTask = CaptionTask.CAPTION,
    *,
    maximum_characters: int | None = None,
) -> CaptionRequest:
    prompt = PromptBuilder().build(
        PromptRequest(
            task=task,
            subject="A practical automation tip",
            language="pt-br",
            tone="friendly",
            style="concise",
            target_length=80,
            platform="custom_platform",
            custom_variables={"audience": "creators"},
        )
    )
    return CaptionRequest(
        prompt,
        CaptionGenerationOptions(
            response_format=ResponseFormat.TEXT,
            maximum_characters=maximum_characters,
        ),
    )


def test_prompt_builder_supports_every_task_and_context() -> None:
    builder = PromptBuilder()
    request = PromptRequest(
        task=CaptionTask.CAPTION, subject="Automation", language="en", platform="web"
    )

    assert builder.build_title(request).task is CaptionTask.TITLE
    assert builder.build_caption(request).task is CaptionTask.CAPTION
    assert builder.build_description(request).task is CaptionTask.DESCRIPTION
    assert builder.build_hashtags(request).task is CaptionTask.HASHTAGS
    prompt = builder.build(request)
    assert "Language: en" in prompt.user_instruction
    assert "Platform: web" in prompt.user_instruction


def test_prompt_request_validates_language_and_configuration() -> None:
    with pytest.raises(CaptionValidationError, match="BCP 47"):
        PromptRequest(CaptionTask.CAPTION, "Subject", "English")
    with pytest.raises(CaptionValidationError, match="positive"):
        CaptionGenerationOptions(maximum_characters=0)


def test_mock_provider_satisfies_business_port_without_network() -> None:
    class FakeProvider:
        def generate(self, request: CaptionRequest) -> ProviderResponse:
            assert request.prompt.task is CaptionTask.CAPTION
            return ProviderResponse("Useful caption", provider_name="fake")

    provider: CaptionProvider = FakeProvider()
    response = provider.generate(_request())

    assert response.content == "Useful caption"


def test_parsers_support_plain_json_and_structured_responses() -> None:
    caption_request = _request()
    hashtag_request = _request(CaptionTask.HASHTAGS)

    plain = PlainTextResponseParser().parse(
        caption_request, ProviderResponse("Useful caption", "fake")
    )
    hashtags = PlainTextResponseParser().parse(
        hashtag_request, ProviderResponse("#one, #two", "fake")
    )
    json_response = JsonResponseParser().parse(
        caption_request,
        ProviderResponse('{"text": "JSON caption", "fields": {"score": 1}}', "fake"),
    )
    structured = StructuredResponseParser().parse(
        caption_request,
        ProviderResponse({"text": "Structured caption"}, "fake"),
    )

    assert plain.text == "Useful caption"
    assert hashtags.hashtags == ("#one", "#two")
    assert json_response.fields == {"score": 1}
    assert structured.text == "Structured caption"


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", '{"text": 1}', '{"hashtags": "not-a-list"}'],
)
def test_json_parser_rejects_malformed_structured_responses(content: str) -> None:
    with pytest.raises(CaptionParseError):
        JsonResponseParser().parse(_request(), ProviderResponse(content, "fake"))


def test_structured_parser_rejects_wrong_response_kind() -> None:
    with pytest.raises(CaptionParseError, match="object"):
        StructuredResponseParser().parse(_request(), ProviderResponse("text", "fake"))


def test_validator_checks_empty_duplicate_length_and_title_rules() -> None:
    validator = CaptionValidator()

    with pytest.raises(CaptionValidationError, match="must not be empty"):
        validator.validate(_request(), CaptionResponse(CaptionTask.CAPTION, "  "))
    with pytest.raises(CaptionValidationError, match="unique"):
        validator.validate(
            _request(CaptionTask.HASHTAGS),
            CaptionResponse(CaptionTask.HASHTAGS, hashtags=("news", "#NEWS")),
        )
    with pytest.raises(CaptionValidationError, match="exceed 5"):
        validator.validate(
            _request(maximum_characters=5),
            CaptionResponse(CaptionTask.CAPTION, "longer"),
        )
    with pytest.raises(CaptionValidationError, match="exceed 100"):
        validator.validate(
            _request(CaptionTask.TITLE), CaptionResponse(CaptionTask.TITLE, "x" * 101)
        )


def test_validator_returns_normalized_hashtags() -> None:
    validated = CaptionValidator().validate(
        _request(CaptionTask.HASHTAGS),
        CaptionResponse(CaptionTask.HASHTAGS, hashtags=("automation",)),
    )

    assert validated.hashtags == ("#automation",)


def test_response_fields_are_immutable_json_values() -> None:
    fields: Mapping[str, FrozenJsonValue] = {"nested": {"score": 1}}
    response = CaptionResponse(CaptionTask.CAPTION, "Text", fields=fields)

    with pytest.raises(TypeError):
        response.fields["new"] = "value"  # type: ignore[index]
