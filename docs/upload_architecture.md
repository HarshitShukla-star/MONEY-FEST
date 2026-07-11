# Upload architecture

The upload architecture is provider-independent except for clearly isolated provider adapters. The upload service and domain contracts contain no platform SDK, OAuth flow, API key, HTTP client, or network request.

## Responsibilities

`content_pipeline.domain.uploads` owns immutable request and response values. `UploadRequest` references the canonical `Metadata`; `UploadResponse`, `UploadResult`, and `UploadStatus` normalize every provider's outcome.

`content_pipeline.core.uploads.UploadProvider` is the consumer-owned port. It declares platform support and accepts a validated request with its resolved `Channel`.

`UploadService` is the orchestration layer. It verifies the request and canonical metadata, requires the referenced video file to exist, loads the referenced channel with `ChannelManager`, rejects disabled channels, checks provider platform support, and invokes only the injected provider. Provider failures are converted to `UploadProviderError`, so platform-specific exceptions do not escape the business layer.

## Dependency flow

```text
UploadRequest -> UploadService -> ChannelManager -> Channel
                    |
                    v
             injected UploadProvider -> UploadResponse
```

The service never creates a provider. Application composition selects an adapter and passes it to `UploadService(provider, channels)`.

## YouTube provider

`YouTubeUploadProvider` implements `UploadProvider` using an injected authenticated YouTube Data API client. It maps canonical title, description, tags, hashtags, and visibility to `videos.insert`, advances the resumable request with bounded retries for transient failures, and translates Google authentication and API exceptions into project exceptions. Google SDK imports are confined to this adapter; OAuth client construction, token storage, and timeout policy remain outside the provider and are supplied at application composition.
