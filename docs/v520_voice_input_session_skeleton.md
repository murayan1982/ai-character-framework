# v5.2.0 Public Voice Input Session Skeleton

This checkpoint adds the first public voice-input / STT session skeleton.

It provides a mock-safe app-facing boundary for DRC and other host apps, without
running real STT providers yet.

## Public symbols

The following symbols are exported from `framework`:

- `create_voice_input_session`
- `VoiceInputSession`
- `VoiceInputSessionInfo`

These build on the public request/result types added earlier:

- `VoiceInputRequest`
- `VoiceInputResult`
- `VoiceInputOutcome`
- `VoiceInputErrorCode`

## Factory

Host apps can create a public voice-input session through the framework root:

```python
import framework

session = framework.create_voice_input_session(language="ja-JP")
result = session.listen_result()
```

The factory is keyword-only and mock-safe.

## Session lifecycle

The public session skeleton exposes:

- `info`
- `is_closed`
- `listen_result(...)`
- `text_fallback_result(...)`
- `on_event(callback)`
- `close()`
- `dispose()`
- context manager support

`close()` and `dispose()` are idempotent. Calling `listen_result()` after close
returns a provider-neutral `VoiceInputResult.closed()` result.

## Mock-safe default behavior

The session does not execute real STT yet.

When real STT is disabled, `listen_result()` returns a provider-neutral
`unavailable` result with public metadata:

```text
boundary=voice_input
reason=real_stt_disabled
```

When `real_stt_enabled=True`, this skeleton still does not call a real provider.
It returns `unavailable` with `reason=real_stt_not_implemented`.

This keeps the public boundary safe while implementation proceeds.

## Text fallback

`text_fallback_result(text)` allows host apps to route app-provided text through
the voice-input result boundary while real STT is unavailable.

This is useful for DRC integration tests that need a voice-input-like public
result without depending on microphone or STT provider internals.

## Events

The skeleton provides provider-neutral app-facing events:

- `voice_input.started`
- `voice_input.unavailable`
- `voice_input.text_fallback`
- `voice_input.closed`

Event payloads are public-safe and redact secret-like keys.

## Import safety

`import framework` must not eagerly import microphone libraries, STT providers,
audio runtimes, or provider SDKs.

This skeleton imports only public framework types and standard-library modules.

## Next checkpoint

The next checkpoint should add a voice-input provider configuration / capability
preflight so the public session can report whether real STT could be enabled
without executing the provider.
