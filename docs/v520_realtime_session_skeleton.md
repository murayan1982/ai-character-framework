# v5.2.0 Public Realtime Session Skeleton

This checkpoint adds the first public realtime session skeleton.

It provides a mock-safe app-facing lifecycle and event boundary for DRC and
other host apps, without running real STT, LLM, TTS, motion, Live2D, VTube
Studio, websocket, microphone, or provider SDK code.

## Public symbols

The following symbols are exported from `framework`:

- `create_realtime_session`
- `RealtimeSession`
- `RealtimeSessionInfo`

These build on the public realtime lifecycle / event types:

- `RealtimeState`
- `RealtimeEventType`
- `RealtimeErrorCode`
- `RealtimeEvent`
- `RealtimeTurn`
- `RealtimeTurnResult`

## Factory

Host apps can create a public realtime session through the framework root:

```python
import framework

session = framework.create_realtime_session()
```

The factory is keyword-only and mock-safe.

## Session lifecycle

The public session skeleton exposes:

- `info`
- `state`
- `is_closed`
- `on_event(callback)`
- `emit_created()`
- `run_turn(...)`
- `close()`
- `dispose()`
- context manager support

`close()` and `dispose()` are idempotent. Calling `run_turn(...)` after close
returns a provider-neutral `RealtimeTurnResult.closed(...)` result.

## Mock-safe default behavior

`run_turn(...)` does not execute real runtime providers.

It emits stable public realtime events in a deterministic mock flow:

1. `realtime.turn.started`
2. `realtime.voice_input.started`
3. `realtime.voice_input.completed`
4. `realtime.text_chat.started`
5. `realtime.text_chat.completed`
6. `realtime.voice_output.started`
7. `realtime.voice_output.completed`
8. `realtime.turn.completed`

The turn result is a completed `RealtimeTurnResult` with `mock_runtime=True`
public metadata.

## Events

Callbacks receive `RealtimeEvent` objects.

Events are provider-neutral, secret-safe, and app-facing. They include:

- event type
- current state
- previous state
- turn id
- session id
- public error code
- safe message
- retryable flag
- public metadata

## Import safety

`import framework` and `create_realtime_session(...)` must not eagerly import
STT, LLM, TTS, motion, Live2D, VTube Studio, websocket, microphone, audio
runtime, or provider SDK modules.

## Next checkpoint

The next checkpoint should add public realtime host-app examples showing event
callbacks, mock turn execution, and closed-session behavior.
