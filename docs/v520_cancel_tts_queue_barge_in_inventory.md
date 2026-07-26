# v5.2.0 Hard Cancel / TTS Queue / Flush / Barge-in Inventory

This document starts priority 3 of the DRC-driven v5.2.0 work:

```text
Hard cancel / TTS queue / flush / barge-in
```

Priority 1, public voice-input / STT session, and priority 2, unified realtime
lifecycle / event contract, now have mock-safe public conformance gates.

The next step is to define the public interruption and output-control contract
that DRC can use without depending on FW internals.

## Driver

DRC RT-1 needs a public runtime boundary for user interruption.

When a user speaks or interrupts while an AI response is being generated or
spoken, DRC needs provider-neutral ways to request:

- current turn interruption;
- LLM streaming cancellation when supported;
- TTS queue cancellation;
- queued audio flush;
- output playback stop handoff;
- barge-in policy handling;
- stable events and typed results.

DRC should not implement this by reaching into internal LLM streaming state, TTS
queue structures, audio artifact paths, player internals, provider SDKs, or
VTube Studio internals.

## Current integration risk

Without a public cancel / queue / flush / barge-in contract, host apps may be
tempted to depend on:

- internal `interrupt()` behavior differences between sessions;
- provider-specific streaming cancellation APIs;
- private TTS queue lists;
- raw voice output artifact paths;
- audio playback implementation details;
- internal state flags;
- race-prone app-side queue clearing;
- exceptions instead of typed public results;
- ad-hoc event names;
- provider-specific unsupported behavior.

v5.2.0 should turn these into a public provider-neutral control surface.

## Public boundary target

Candidate public API:

```python
import framework

session = framework.create_realtime_session()
result = session.interrupt(...)
flush = session.flush_output(...)
```

Candidate public symbols:

- `InterruptScope`
- `InterruptReason`
- `InterruptRequest`
- `InterruptResult`
- `TTSQueueState`
- `OutputFlushRequest`
- `OutputFlushResult`
- `BargeInPolicy`
- `BargeInDecision`

Candidate session methods:

- `RealtimeSession.interrupt(...)`
- `RealtimeSession.cancel_current_turn(...)`
- `RealtimeSession.flush_output(...)`
- `RealtimeSession.set_barge_in_policy(...)`

The exact names may still change during implementation, but this inventory
establishes the public boundary direction.

## Candidate interrupt scopes

The public contract should be able to represent:

- `current_turn`
- `llm_stream`
- `tts_queue`
- `voice_output`
- `motion`
- `all`

A request for a scope must be allowed even if a provider or stage does not
support true hard cancellation. Unsupported or not-yet-implemented behavior must
return a typed public result, not an uncaught provider exception.

## Candidate reasons

The public contract should be able to represent:

- `user_barge_in`
- `user_cancel`
- `new_turn_started`
- `session_closed`
- `timeout`
- `host_app_request`
- `provider_failure`

## TTS queue / flush requirements

A public TTS queue contract should report:

- queue state;
- queued item count;
- current item id when public-safe;
- whether flush is supported;
- whether playback stop handoff is required;
- whether provider cancellation is supported;
- safe message;
- public error code;
- public metadata.

A public flush result should distinguish:

- `flushed`
- `nothing_to_flush`
- `unsupported`
- `failed`
- `closed`

It must not expose raw local audio paths, private artifact paths, provider
payloads, token files, or playback handles.

## Barge-in requirements

A public barge-in policy should describe how the runtime should behave when new
user input appears while output is in progress.

Candidate policy modes:

- `disabled`
- `soft_interrupt`
- `flush_output`
- `hard_cancel`
- `turn_takeover`

A public barge-in decision should report:

- accepted / rejected;
- policy mode;
- requested scope;
- whether output should stop;
- whether queued TTS should flush;
- whether current turn should cancel;
- public event to emit;
- safe message;
- retryable flag.

## Event requirements

The realtime event contract should add stable event types such as:

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

Events must be provider-neutral, secret-safe, and safe for app logs.

## Honest capability requirements

The public contract must not overclaim hard cancellation.

For each scope, FW should be able to report:

- supported;
- unsupported;
- not configured;
- provider does not support hard cancel;
- not implemented yet;
- already closed;
- no active turn;
- no queued output.

This is important because true hard cancellation depends on provider and stage
capabilities.

## Relationship to existing public contracts

The cancel / queue / flush / barge-in contract should compose:

- `RealtimeSession`
- `RealtimeEvent`
- `RealtimeTurnResult`
- `VoiceOutputSession`
- `VoiceOutputResult`
- `VoiceArtifactRef`
- `VoiceInputSession`
- `VoiceInputResult`
- `TextChatSession`
- `TextChatResult`

It should not bypass or replace these contracts. It should define a public
control layer above them.

## Initial scope

The first implementation should be a mock-safe skeleton only.

It should:

- export public interruption / queue / flush / barge-in types;
- provide provider-neutral typed results;
- not call real providers;
- not stop real playback;
- not flush real audio queues;
- not claim provider-level hard cancel;
- integrate with `RealtimeSession` as mock-safe methods;
- emit stable public realtime events.

## Out of scope for this inventory

This inventory does not implement:

- real LLM streaming cancellation;
- real TTS queue cancellation;
- real audio playback stop;
- real provider cancellation;
- real barge-in audio detection;
- VTS / Live2D motion interruption.

Those are later v5.2.0 implementation checkpoints.

## Next implementation checkpoint

The next implementation checkpoint should add public interruption and output
control type skeletons.

Suggested next commit:

```text
feat/test: add public interrupt and output control types
```
