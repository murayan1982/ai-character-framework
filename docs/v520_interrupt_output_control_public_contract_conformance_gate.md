# v5.2.0 Interrupt / Output-Control Public Contract Conformance Gate

This checkpoint adds a conformance gate for the public hard cancel / TTS queue /
flush / barge-in control contract added so far in v5.2.0.

The gate is intentionally mock-safe. It does not execute real LLM streaming
cancellation, real TTS queue flush, real playback stop, real provider
cancellation, real audio barge-in detection, motion interruption, websocket, or
provider SDK code.

## Covered public contract

The gate verifies the public `framework` root exposes:

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
- `RealtimeSession.get_tts_queue_state()`
- `RealtimeSession.interrupt(...)`
- `RealtimeSession.cancel_current_turn(...)`
- `RealtimeSession.flush_output(...)`
- `RealtimeSession.set_barge_in_policy(...)`
- `RealtimeSession.decide_barge_in(...)`

## Public import rule

The gate verifies that host apps can use:

```python
import framework
```

without eager provider imports.

The public root import must not load LLM provider, TTS provider, audio playback,
websocket, microphone, Whisper, speech-recognition, or VTube Studio runtime
modules.

## Type rule

The gate verifies:

- interrupt scope / reason / outcome enums;
- `InterruptRequest.user_barge_in(...)`;
- `InterruptResult.not_implemented(...)`;
- `InterruptResult.already_closed(...)`;
- `InterruptResult.no_active_turn(...)`;
- `TTSQueueState`;
- `OutputFlushRequest`;
- `OutputFlushResult.not_implemented(...)`;
- `OutputFlushResult.nothing_to_flush(...)`;
- `OutputFlushResult.closed(...)`;
- `BargeInPolicy` helpers;
- `BargeInDecision` helpers.

All public metadata must be secret-safe.

## Realtime session rule

The gate verifies `RealtimeSession` exposes public output-control methods and
honest capability flags:

- `supports_interrupt=True`
- `supports_output_flush=True`
- `supports_barge_in_policy=True`
- `hard_cancel_supported=False`
- `tts_queue_flush_supported=False`

This means the public control surface exists, but true provider-level hard
cancellation and real queue flush are not claimed yet.

## Event rule

The gate verifies stable realtime event types for:

- interrupt request / unsupported;
- output flush request / completed;
- barge-in detected / accepted / rejected.

## Host-app example rule

The gate verifies public host-app examples exist and use only public
`import framework` style.

The examples must not import FW internals, provider SDKs, microphone libraries,
websocket modules, token files, raw audio paths, playback handles, or queue
implementation details.

## Current limitation

This gate does not require real hard cancel, real TTS queue flush, real playback
stop, real provider cancel, or real barge-in detection.

At this point, the public contract must honestly return typed not-yet-implemented
/ no-active-turn / empty-queue / closed-session results rather than claiming real
runtime control readiness.
