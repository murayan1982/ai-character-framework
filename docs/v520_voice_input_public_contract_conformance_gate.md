# v5.2.0 Voice Input Public Contract Conformance Gate

This checkpoint adds a conformance gate for the public voice-input / STT
contract added so far in v5.2.0.

The gate is intentionally mock-safe. It does not execute real STT providers,
microphone capture, audio runtime, or provider SDKs.

## Covered public contract

The gate verifies the public `framework` root exposes:

- `VoiceInputOutcome`
- `VoiceInputErrorCode`
- `VoiceInputRequest`
- `VoiceInputResult`
- `VoiceInputProviderStatus`
- `VoiceInputProviderConfig`
- `VoiceInputCapabilities`
- `resolve_voice_input_provider_config`
- `get_voice_input_capabilities`
- `create_voice_input_session`
- `VoiceInputSession`
- `VoiceInputSessionInfo`

## Public import rule

The gate verifies that host apps can use:

```python
import framework
```

without eager STT provider imports.

The public root import must not load microphone, Whisper, speech-recognition,
or provider runtime modules.

## Factory signature rule

The gate verifies `create_voice_input_session(...)` is keyword-only.

This keeps the host-app integration boundary explicit and stable before DRC
consumes it.

## Typed result rule

The gate verifies:

- `VoiceInputRequest` is provider-neutral and secret-safe
- `VoiceInputResult.completed(...)` returns typed completed result
- `VoiceInputResult.no_input(...)` returns retryable typed no-input result
- `VoiceInputResult.interrupted(...)` returns retryable typed interrupted result
- `VoiceInputResult.unavailable(...)` returns typed unavailable result
- `VoiceInputResult.failed(...)` returns typed failed result
- `VoiceInputResult.closed(...)` returns typed closed result

## Capability preflight rule

The gate verifies public capability preflight reports:

- disabled default state
- missing credentials
- provider execution guard
- unsupported provider
- real STT not implemented

It must not overclaim real STT support.

## Session rule

The gate verifies `VoiceInputSession`:

- exposes `info`
- exposes `capabilities`
- exposes `is_closed`
- supports `listen_result(...)`
- supports `text_fallback_result(...)`
- supports `on_event(...)`
- supports `close()`
- supports `dispose()`
- supports context manager cleanup
- returns status-specific provider-neutral results
- keeps closed-session result precedence

## Host-app example rule

The gate verifies public host-app examples exist and use only public
`import framework` style.

The examples must not import FW STT internals, provider SDKs, microphone
libraries, token files, raw audio paths, or checkout-layout workarounds.

## Current limitation

This gate does not require real STT execution.

At this point, the public contract must honestly report real STT as unavailable
or not implemented rather than claiming provider readiness.
