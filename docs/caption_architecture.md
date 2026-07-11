# Caption architecture

The caption framework is provider-independent. It does not include an AI SDK, API call, credential, provider selection, or network activity. It also includes an FFmpeg-backed subtitle burn-in adapter for existing SRT files.

## Boundaries

`content_pipeline.domain.captions` contains immutable business contracts and rules:

- `PromptRequest` captures title, caption, description, or hashtag intent along with language, tone, style, target length, platform, and JSON-safe custom variables.
- `PromptBuilder` turns that input into a neutral `CaptionPrompt`. Its explicit `build_title`, `build_caption`, `build_description`, and `build_hashtags` methods are convenience entry points over one deterministic builder.
- `CaptionRequest` couples a prompt with `CaptionGenerationOptions`; the options define only response representation and an optional character limit, never a vendor model or credential.
- `ProviderResponse` is a sanitized raw value, while `CaptionResponse` is the normalized value used by future business workflows.
- `CaptionValidator` checks empty content, title and caption limits, and duplicate hashtags. The shared domain language/title/hashtag rules are also used by Metadata, so these invariants cannot drift.

`content_pipeline.core.captions` owns the consumer-facing ports and media adapter:

- `CaptionProvider` is the `Protocol` used by a future caption use case.
- `AbstractCaptionProvider` is optional support for adapters that share implementation.
- `ResponseParser` and `AbstractResponseParser` define response conversion. Built-in plain-text, JSON, and structured parsers establish the stable response shape; another format needs only another parser implementation.
- `SubtitleBurner` invokes FFmpeg without a shell, validates file paths and SRT extensions, rejects accidental overwrite or input/output aliasing, and applies a bounded process timeout.

The domain never imports `core`, and provider adapters are not implemented here.

## Typical future flow

```python
prompt = PromptBuilder().build_caption(
    PromptRequest(
        task=CaptionTask.CAPTION,
        subject="A short tutorial about keyboard shortcuts",
        language="en",
        tone="helpful",
        platform="short_video",
    )
)
request = CaptionRequest(prompt)

# A future workflow receives a CaptionProvider through dependency injection.
raw = provider.generate(request)
result = PlainTextResponseParser().parse(request, raw)
caption = CaptionValidator().validate(request, result)
```

The workflow only handles `CaptionProvider`, `CaptionRequest`, and `CaptionResponse`; it does not branch on a vendor. An OpenAI, Gemini, Claude, or local-model adapter will implement `generate`, translate its SDK response into `ProviderResponse`, and translate SDK failures into `CaptionProviderError`. Application composition selects and injects that adapter. The parser is selected from the expected `ResponseFormat`, independently of the provider.

## Extension guidance

To add a provider later, create an adapter beside the `CaptionProvider` port in `core.captions`, implement `generate(request)`, map the neutral prompt/options to the provider SDK, return only `ProviderResponse`, and chain native exceptions into `CaptionProviderError`. Do not add provider fields to domain models.

To add a response format, implement `ResponseParser`; malformed data must raise `CaptionParseError`. To add platform behavior, pass a normalized platform name and platform-specific custom variables to `PromptRequest`; the core model remains unchanged.
