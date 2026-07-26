# v5.2.0 Realtime Public Contract Conformance Gate

This checkpoint adds a conformance gate for the public realtime lifecycle /
event contract added so far in v5.2.0.

The gate is intentionally mock-safe. It does not execute real STT, LLM, TTS,
motion, Live2D, VTube Studio, websocket, microphone, audio runtime, or provider
SDK code.

## Covered public contract

The gate verifies the public `framework` root exposes:

- `RealtimeState`
- `RealtimeEventType`
- `RealtimeErrorCode`
- `RealtimeEvent`
- `RealtimeTurn`
- `RealtimeTurnResult`
- `create_realtime_session`
- `RealtimeSession`
- `RealtimeSessionInfo`

## Public import rule

The gate verifies that host apps can use:

```python
import framework
```

without eager realtime provider imports.

The public root import must not load STT, LLM provider, TTS provider, websocket,
microphone, Whisper, speech-recognition, or VTube Studio runtime modules.

## Factory signature rule

The gate verifies `create_realtime_session(...)` is keyword-only.

This keeps the host-app integration boundary explicit and stable before DRC
consumes it.

## Type rule

The gate verifies:

- `RealtimeState` contains the public lifecycle states
- `RealtimeEventType` contains the public event names
- `RealtimeErrorCode` contains provider-neutral public error codes
- `RealtimeEvent` is public-safe and metadata-redacting
- `RealtimeTurn` is public-safe and metadata-redacting
- `RealtimeTurnResult` helper constructors return typed terminal results

## Session rule

The gate verifies `RealtimeSession`:

- exposes `info`
- exposes `state`
- exposes `is_closed`
- supports `on_event(...)`
- supports `emit_created()`
- supports `run_turn(...)`
- supports `close()`
- supports `dispose()`
- supports context manager cleanup
- emits deterministic provider-neutral mock events
- returns a completed typed mock turn result
- returns a typed closed result after close
- does not overclaim real provider runtime execution

## Host-app example rule

The gate verifies public realtime host-app examples exist and use only public
`import framework` style.

The examples must not import FW internals, provider SDKs, microphone libraries,
websocket modules, token files, raw audio paths, or checkout-layout workarounds.

## Current limitation

This gate does not require real realtime orchestration.

At this point, the public contract must honestly remain a mock-safe lifecycle
and event boundary rather than claiming real STT / LLM / TTS / motion runtime
readiness.
