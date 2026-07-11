# Channel Manager

`content_pipeline.core.channels` is the sole owner of publishing-destination records. It manages platform-neutral channel data only; it does not authenticate, call providers, upload content, or handle credentials themselves.

Construct `ChannelManager` with a `ChannelRepository`. `JsonChannelRepository(Path(...))` is the default local persistence adapter and stores a UTF-8 JSON array using atomic file replacement. Replacing it with SQLite or PostgreSQL requires only another implementation of `ChannelRepository`; the manager and `Channel` model remain unchanged.

`PlatformRegistry` is injected into the manager. Its default registration contains `youtube`, `instagram`, `tiktok`, and `facebook`. Register a future platform during application composition before channels are created, rather than editing the model or manager.

The manager enforces unique ids, case-insensitively unique friendly names, valid registered platforms, a single enabled default channel, valid metadata, and valid tags. `ChannelUpdate` supports typed partial updates; omitted fields remain unchanged and `credential_reference=None` explicitly clears the reference.
