# v5.2.0 Public Realtime Lifecycle Event Types

This checkpoint adds the first public realtime lifecycle / event contract
skeleton.

It is intentionally limited to provider-neutral public data types. It does not
add `RealtimeSession` or real realtime provider orchestration yet.

## Public symbols

The following symbols are exported from `framework`:

- `RealtimeState`
- `RealtimeEventType`
- `RealtimeErrorCode`
- `RealtimeEvent`
- `RealtimeTurn`
- `RealtimeTurnResult`

## Lifecycle states

`RealtimeState` includes:

- `idle`
- `listening`
- `transcribing`
- `thinking`
- `speaking`
- `motion`
- `interrupted`
- `failed`
- `completed`
- `closed`

These are public app-facing lifecycle states for DRC and other host apps.

## Event types

`RealtimeEventType` includes:

- `realtime.session.created`
- `realtime.turn.started`
- `realtime.voice_input.started`
- `realtime.voice_input.completed`
- `realtime.text_chat.started`
- `realtime.text_chat.completed`
- `realtime.voice_output.started`
- `realtime.voice_output.completed`
- `realtime.motion.started`
- `realtime.motion.completed`
- `realtime.turn.completed`
- `realtime.turn.interrupted`
- `realtime.turn.failed`
- `realtime.session.closed`

## Event contract

`RealtimeEvent` exposes:

- `type`
- `state`
- `previous_state`
- `turn_id`
- `session_id`
- `boundary`
- `public_error_code`
- `safe_message`
- `retryable`
- `public_metadata`

`as_dict()` returns an immutable public-safe event mapping for host-app
callbacks.

Metadata redacts secret-like keys such as token, secret, password, credential,
authorization, and API key.

## Turn contract

`RealtimeTurn` provides a public turn descriptor:

- `turn_id`
- `input_text`
- `state`
- `session_id`
- `public_metadata`

`RealtimeTurnResult` provides a public result shape for future realtime session
orchestration:

- `turn_id`
- `outcome`
- `input_text`
- `output_text`
- `voice_input_result`
- `text_chat_result`
- `voice_output_result`
- `motion_result`
- `public_error_code`
- `safe_message`
- `retryable`
- `public_metadata`

Helper constructors:

- `RealtimeTurnResult.completed(...)`
- `RealtimeTurnResult.interrupted(...)`
- `RealtimeTurnResult.failed(...)`
- `RealtimeTurnResult.closed(...)`

## Import safety

`import framework` must not eagerly import STT, LLM, TTS, motion, Live2D,
VTube Studio, websocket, microphone, audio runtime, or provider SDK modules.

This checkpoint keeps the public realtime types in `framework.realtime` with no
provider imports.

## Next checkpoint

The next checkpoint should add a mock-safe public `RealtimeSession` skeleton and
factory:

- `create_realtime_session(...)`
- `RealtimeSession`
- `RealtimeSessionInfo`

The session should emit provider-neutral `RealtimeEvent` values without running
real runtime stages by default.
