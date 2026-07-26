# v5.2.0 Realtime Lifecycle / Event Contract Inventory

This document starts priority 2 of the DRC-driven v5.2.0 work:

```text
Unified realtime lifecycle / event contract
```

Priority 1, the mock-safe public voice-input / STT session contract, now has a
public conformance gate. The next step is to define a unified public realtime
lifecycle and event model that can connect voice input, text chat, voice output,
and future motion output without requiring DRC to own framework internals.

## Driver

DRC RT-1 needs a public runtime surface that can coordinate:

- voice input / STT session state;
- text chat / LLM turn state;
- voice output / TTS state;
- future motion / Live2D / VTube Studio state;
- interruption and failure transitions;
- host-app observable events.

DRC should not stitch these together through internal imports, provider payloads,
raw audio paths, direct VTS WebSocket ownership, or ad-hoc event names.

## Current integration risk

Without a unified realtime lifecycle / event contract, host apps may be tempted
to depend on:

- internal text-chat state;
- internal voice-input state;
- internal voice-output state;
- TTS queue implementation details;
- provider-specific streaming callbacks;
- raw provider payloads;
- local artifact paths;
- app-side event naming conventions;
- direct VTS / Live2D event ownership;
- manual coordination of close / interrupt / failure behavior.

v5.2.0 should turn these into public provider-neutral runtime events.

## Public boundary target

Candidate public API:

```python
import framework

session = framework.create_realtime_session()
session.on_event(lambda event: print(event.type, event.state))
result = session.run_turn(...)
```

Candidate public symbols:

- `create_realtime_session`
- `RealtimeSession`
- `RealtimeSessionInfo`
- `RealtimeState`
- `RealtimeEventType`
- `RealtimeEvent`
- `RealtimeTurn`
- `RealtimeTurnResult`
- `RealtimeErrorCode`

The exact names may still change during implementation, but this inventory
establishes the public boundary direction.

## Candidate lifecycle states

The unified lifecycle should be able to represent:

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

These states should be provider-neutral and app-facing. They should not expose
provider-specific object types or internal queue structures.

## Candidate event types

The public event contract should provide stable event types such as:

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

The naming may be refined later, but DRC must be able to listen to one stable
public event surface.

## Event payload rules

Public realtime event payloads must be:

- provider-neutral;
- immutable or treated as read-only;
- secret-safe;
- safe for host-app logs;
- stable enough for DRC UI state transitions;
- independent of raw provider payloads;
- independent of local private audio paths;
- independent of VTS token / WebSocket internals.

Payloads should include public context such as:

- event type;
- current state;
- previous state;
- turn id;
- session id;
- provider-neutral boundary name;
- safe message;
- public error code;
- retryable flag;
- public metadata.

Payloads should not include:

- API keys;
- credentials;
- provider raw JSON;
- internal exception repr containing secrets;
- token file paths;
- raw audio temp paths;
- provider SDK objects;
- socket handles;
- app private filesystem paths.

## Turn model

A public realtime turn should represent a single host-app interaction unit.

Candidate fields:

- `turn_id`
- `input_text`
- `voice_input_result`
- `text_chat_result`
- `voice_output_result`
- `motion_result`
- `started_at`
- `ended_at`
- `state`
- `public_error_code`
- `safe_message`
- `public_metadata`

The initial implementation can be mock-safe and may not run all runtime stages.
The contract should still reserve the public shape that DRC can depend on.

## Relationship to existing public contracts

The unified realtime boundary should compose the existing public contracts:

- `TextChatSession`
- `TextChatResult`
- `VoiceOutputSession`
- `VoiceOutputResult`
- `VoiceArtifactRef`
- `VoiceInputSession`
- `VoiceInputResult`
- `VoiceInputCapabilities`

It should not bypass or replace these lower-level public contracts. It should
orchestrate them through provider-neutral state and event semantics.

## Lifecycle requirements

A public realtime session should provide:

- mock-safe construction;
- no eager provider SDK import on `import framework`;
- `info`;
- `is_closed`;
- `on_event(callback)`;
- `close()`;
- `dispose()`;
- context manager support;
- idempotent cleanup;
- stable closed-session result behavior;
- provider-neutral event emission;
- explicit unsupported / unavailable results when a runtime stage is not ready.

## Initial scope

The first implementation should be a mock-safe skeleton only.

It should:

- export public realtime types;
- provide a session factory;
- emit stable provider-neutral events;
- not call real STT / LLM / TTS / VTS providers;
- not depend on DRC;
- not import provider SDKs eagerly;
- not overclaim hard cancel / queue flush / barge-in readiness.

## Out of scope for this inventory

This inventory does not implement:

- real realtime provider execution;
- real LLM streaming orchestration;
- hard cancel semantics;
- TTS queue flush semantics;
- barge-in;
- Live2D / VTS adapter implementation.

Those are later v5.2.0 priorities.

## Next implementation checkpoint

The next implementation checkpoint should add public realtime lifecycle and
event type skeletons.

Suggested next commit:

```text
feat/test: add public realtime lifecycle event types
```
