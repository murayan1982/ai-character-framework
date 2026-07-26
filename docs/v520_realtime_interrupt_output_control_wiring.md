# v5.2.0 Realtime Interrupt / Output Control Wiring

This checkpoint wires the public interrupt / output-control types into the
mock-safe public `RealtimeSession` skeleton.

It still does not execute real hard cancellation, real TTS queue flush, real
playback stop, real provider cancellation, or real barge-in detection.

## What changed

`RealtimeSession` now exposes:

- `get_tts_queue_state()`
- `interrupt(...)`
- `cancel_current_turn(...)`
- `flush_output(...)`
- `set_barge_in_policy(...)`
- `decide_barge_in(...)`
- `barge_in_policy`

`RealtimeSessionInfo` now reports:

- `supports_interrupt=True`
- `supports_output_flush=True`
- `supports_barge_in_policy=True`
- `hard_cancel_supported=False`
- `tts_queue_flush_supported=False`

This means the public control surface exists, but true provider-level hard
cancellation and real queue flushing are not claimed yet.

## New realtime events

`RealtimeEventType` now includes:

- `realtime.interrupt.requested`
- `realtime.interrupt.accepted`
- `realtime.interrupt.completed`
- `realtime.interrupt.unsupported`
- `realtime.output.flush.requested`
- `realtime.output.flush.completed`
- `realtime.output.flush.unsupported`
- `realtime.barge_in.detected`
- `realtime.barge_in.accepted`
- `realtime.barge_in.rejected`

These events are provider-neutral and public-safe.

## Interrupt behavior

`interrupt(...)` returns typed public results:

- closed session -> `InterruptResult.already_closed(...)`
- no active turn -> `InterruptResult.no_active_turn(...)`
- explicit active turn id -> `InterruptResult.not_implemented(...)`

The last case is intentional. FW must not overclaim provider-level hard
cancellation before real runtime support exists.

## Output flush behavior

`flush_output(...)` returns typed public results:

- closed session -> `OutputFlushResult.closed(...)`
- empty mock queue -> `OutputFlushResult.nothing_to_flush(...)`
- future non-empty queue without implementation -> `OutputFlushResult.not_implemented(...)`

The mock session does not expose raw audio paths, playback handles, queue
internals, or provider payloads.

## Barge-in behavior

`set_barge_in_policy(...)` stores a public `BargeInPolicy`.

`decide_barge_in(...)` emits:

- `realtime.barge_in.detected`
- `realtime.barge_in.rejected` when disabled
- `realtime.barge_in.accepted` when policy allows it

Accepted decisions describe whether the host should stop output, flush queue,
and cancel the current turn through public booleans.

## Import safety

`import framework` and `create_realtime_session(...)` must not eagerly import
LLM, TTS, audio playback, motion, Live2D, VTube Studio, websocket, microphone,
or provider SDK modules.

## Next checkpoint

The next checkpoint should add host-app examples for:

- interrupt result handling
- output flush result handling
- barge-in policy and decision handling
