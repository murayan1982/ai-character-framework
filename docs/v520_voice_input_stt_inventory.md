# v5.2.0 Voice Input / STT Internal Inventory

This document records the current voice-input / STT integration inventory for
the v5.2.0 public runtime boundary work.

The purpose of this checkpoint is not to implement the final public voice input
API yet. It records what DRC must not depend on, what FW should own, and what the
next public contract should expose.

## Driver

DRC RT-1 requires a public FW voice-input boundary before DRC returns to
realtime implementation.

DRC should not directly own or import FW internal STT, microphone capture,
provider clients, raw audio handling, token files, or provider-specific result
payloads.

## Current integration risk

Without a public voice-input contract, a host app may be tempted to depend on:

- internal STT modules;
- provider-specific STT clients;
- microphone capture implementation details;
- local raw audio files;
- temporary CWD or source checkout layout assumptions;
- provider payload fields;
- ad-hoc unavailable / missing credential handling;
- app-side lifecycle cleanup that should belong to FW.

v5.2.0 should turn this into a provider-neutral public session boundary.

## Public boundary target

Candidate public API:

```python
import framework

session = framework.create_voice_input_session()
result = session.listen_result()
```

Candidate public symbols:

- `create_voice_input_session`
- `VoiceInputSession`
- `VoiceInputSessionInfo`
- `VoiceInputRequest`
- `VoiceInputResult`
- `VoiceInputEvent`
- `VoiceInputEventType`
- `VoiceInputState`
- `VoiceInputErrorCode`

The exact names may still change during implementation, but this inventory
establishes the boundary direction.

## Required public behavior

A public voice-input / STT session should provide:

- mock-safe construction;
- no eager provider SDK import on `import framework`;
- provider-neutral capability reporting;
- provider-neutral missing credential behavior;
- guarded real STT execution;
- typed result object;
- safe public error code and message;
- lifecycle methods: `close()`, `dispose()`, `is_closed`;
- context manager support;
- app-facing state / event boundary;
- secret-free public metadata;
- no raw provider payload exposure;
- no token file exposure;
- no local private audio path exposure.

## Candidate result shape

`VoiceInputResult` should describe the public outcome without leaking provider
internals.

Candidate public fields:

- `outcome`
- `text`
- `language`
- `confidence`
- `started_at`
- `ended_at`
- `duration_ms`
- `public_error_code`
- `safe_message`
- `retryable`
- `public_metadata`

Result outcome examples:

- `completed`
- `no_input`
- `interrupted`
- `failed`
- `unavailable`
- `closed`

## Candidate request shape

`VoiceInputRequest` should describe host-app intent, not provider internals.

Candidate public fields:

- `language`
- `timeout_ms`
- `max_duration_ms`
- `vad_enabled`
- `input_device_id`
- `metadata`

Provider-specific options should remain FW-owned or be represented through a
provider-neutral config layer.

## Lifecycle requirements

The voice-input session should match the public lifecycle style introduced in
v5.1.0:

- `close()` is idempotent;
- `dispose()` aliases cleanup behavior safely;
- `is_closed` is public;
- context manager exit closes the session;
- calling listen/transcribe after close returns a provider-neutral closed result;
- cleanup never requires DRC to know internal recorder/provider state.

## Event requirements

The voice-input boundary should be compatible with the upcoming unified
realtime event contract.

Candidate event types:

- `voice_input.started`
- `voice_input.listening`
- `voice_input.detected`
- `voice_input.transcribing`
- `voice_input.completed`
- `voice_input.no_input`
- `voice_input.interrupted`
- `voice_input.failed`
- `voice_input.closed`

Event payloads must be provider-neutral and safe for app logs.

## Guarded real execution

Real STT execution should require explicit opt-in guards.

Candidate guards:

- framework config / factory option enabling real STT;
- provider config resolution;
- credentials available;
- optional environment guard for provider execution;
- mock-safe default when no real provider is configured.

Missing credentials must produce a typed provider-neutral result or capability
status, not an uncaught provider exception.

## DRC must not depend on

DRC must not depend on:

- `stt.*` internals;
- provider SDK object types;
- raw microphone recorder implementation;
- raw audio temp file paths;
- token files or private `.env` files;
- STT provider payload schema;
- current FW repository layout;
- CWD / sys.path / import cache workarounds.

## Next implementation checkpoint

The next implementation checkpoint should add the public voice-input type
skeleton and mock-safe session object without real provider execution.

Suggested next commit:

```text
feat/test: add public voice input result and request types
```
