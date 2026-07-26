# v5.2.0 Public Interrupt / Output Control Types

This checkpoint adds the first public hard-cancel / TTS queue / flush /
barge-in contract skeleton.

It is intentionally limited to provider-neutral public data types. It does not
add realtime session methods or real cancellation / queue / playback behavior
yet.

## Public symbols

The following symbols are exported from `framework`:

- `InterruptScope`
- `InterruptReason`
- `InterruptOutcome`
- `InterruptRequest`
- `InterruptResult`
- `TTSQueueState`
- `OutputFlushOutcome`
- `OutputFlushRequest`
- `OutputFlushResult`
- `BargeInPolicyMode`
- `BargeInPolicy`
- `BargeInDecision`

## Interrupt contract

`InterruptRequest` describes host-app intent:

- `scope`
- `reason`
- `turn_id`
- `flush_output`
- `cancel_tts_queue`
- `cancel_llm_stream`
- `stop_motion`
- `public_metadata`

`InterruptResult` describes provider-neutral outcomes:

- `accepted`
- `unsupported`
- `no_active_turn`
- `already_closed`
- `not_implemented`
- `failed`

The current helper constructors intentionally include safe not-yet-implemented
and lifecycle cases:

- `InterruptResult.not_implemented(...)`
- `InterruptResult.already_closed(...)`
- `InterruptResult.no_active_turn(...)`

These prevent the public contract from overclaiming true provider-level hard
cancellation before it exists.

## TTS queue / flush contract

`TTSQueueState` describes a public-safe queue snapshot:

- `queued_count`
- `current_item_id`
- `is_playing`
- `supports_flush`
- `supports_provider_cancel`
- `playback_stop_required`
- `safe_message`
- `public_metadata`

`OutputFlushRequest` describes host-app flush intent.

`OutputFlushResult` describes provider-neutral outcomes:

- `flushed`
- `nothing_to_flush`
- `unsupported`
- `not_implemented`
- `failed`
- `closed`

Helper constructors include:

- `OutputFlushResult.not_implemented(...)`
- `OutputFlushResult.nothing_to_flush(...)`
- `OutputFlushResult.closed(...)`

## Barge-in contract

`BargeInPolicyMode` describes public policy modes:

- `disabled`
- `soft_interrupt`
- `flush_output`
- `hard_cancel`
- `turn_takeover`

`BargeInPolicy` provides policy helpers:

- `BargeInPolicy.disabled()`
- `BargeInPolicy.soft_interrupt()`
- `BargeInPolicy.flush_output()`
- `BargeInPolicy.hard_cancel()`
- `BargeInPolicy.turn_takeover()`

`BargeInDecision` describes whether a detected barge-in should stop output,
flush queued audio, cancel the current turn, or reject the barge-in.

## Safety rules

These public types must not expose:

- raw local audio paths;
- private voice artifact paths;
- playback handles;
- provider SDK objects;
- provider raw payloads;
- API keys;
- token files;
- credentials;
- websocket handles.

Secret-like metadata keys are redacted.

## Import safety

`import framework` must not eagerly import LLM, TTS, audio playback, motion,
Live2D, VTube Studio, websocket, microphone, or provider SDK modules.

This checkpoint keeps the public interrupt/output-control types in
`framework.output_control` with no provider imports.

## Next checkpoint

The next checkpoint should wire these public types into mock-safe
`RealtimeSession` methods:

- `interrupt(...)`
- `cancel_current_turn(...)`
- `flush_output(...)`
- `set_barge_in_policy(...)`

Those methods should return typed not-yet-implemented / no-active-turn /
closed-session results and emit provider-neutral realtime events.
