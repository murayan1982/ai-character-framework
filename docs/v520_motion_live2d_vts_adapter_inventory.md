# v5.2.0 Motion / Live2D / VTS Adapter Inventory

This document starts priority 4 of the DRC-driven v5.2.0 work:

```text
Public motion / Live2D / VTS adapter
```

Priorities 1-3 now have mock-safe public conformance gates:

1. Public voice-input / STT session
2. Unified realtime lifecycle / event contract
3. Hard cancel / TTS queue / flush / barge-in

The next step is to define a public character-motion adapter boundary that DRC
can use without owning FW internals, Live2D implementation details, VTube Studio
WebSocket state, token files, or provider-specific payloads.

## Driver

DRC RT-1 and later character UI work need a public runtime boundary for motion
and expression output.

DRC should be able to request provider-neutral character actions such as:

- expression change;
- emotion tag update;
- mouth / speaking state;
- idle motion;
- gesture trigger;
- look direction;
- interruption / stop motion;
- motion adapter preflight.

DRC should not implement this by directly depending on FW internals, VTube Studio
WebSocket ownership, Live2D plugin internals, token paths, model files, or
provider-specific event payloads.

## Current integration risk

Without a public motion / Live2D / VTS adapter contract, host apps may be
tempted to depend on:

- internal motion plugin classes;
- direct VTube Studio WebSocket messages;
- token file paths;
- model-specific parameter names;
- raw Live2D model paths;
- app-side VTS authentication state;
- private adapter lifecycle state;
- provider-specific exceptions;
- ad-hoc expression names;
- motion output state coupled to TTS internals.

v5.2.0 should turn these into public provider-neutral motion contracts.

## Public boundary target

Candidate public API:

```python
import framework

session = framework.create_motion_session(adapter="mock")
result = session.apply_motion(...)
```

Candidate public symbols:

- `create_motion_session`
- `MotionSession`
- `MotionSessionInfo`
- `MotionAdapterStatus`
- `MotionCapability`
- `MotionRequest`
- `MotionResult`
- `MotionEventType`
- `MotionState`
- `MotionErrorCode`

Candidate realtime integration:

- `RealtimeSession.motion(...)`
- `RealtimeSession.set_motion_adapter(...)`
- `RealtimeSession.get_motion_capabilities(...)`

The exact names may still change during implementation, but this inventory
establishes the public boundary direction.

## Candidate motion states

The public contract should be able to represent:

- `idle`
- `preparing`
- `speaking`
- `expressing`
- `gesturing`
- `interrupted`
- `failed`
- `closed`
- `unavailable`

These states should be provider-neutral and app-facing.

## Candidate motion event types

The public event contract should provide stable event types such as:

- `motion.session.created`
- `motion.adapter.preflight.completed`
- `motion.requested`
- `motion.started`
- `motion.completed`
- `motion.interrupted`
- `motion.failed`
- `motion.unsupported`
- `motion.session.closed`

Realtime bridge events may also be needed:

- `realtime.motion.started`
- `realtime.motion.completed`
- `realtime.motion.failed`
- `realtime.motion.unsupported`

## Candidate request types

A public `MotionRequest` should support provider-neutral intents such as:

- `expression`
- `emotion`
- `speaking_state`
- `idle_motion`
- `gesture`
- `look_at`
- `stop_motion`
- `reset_expression`

The request should be app-facing and safe for logs.

Candidate fields:

- `intent`
- `expression`
- `emotion`
- `gesture`
- `speaking`
- `intensity`
- `duration_ms`
- `character_id`
- `model_id`
- `public_metadata`

It should not expose provider raw messages, VTS tokens, private model paths, or
plugin handles.

## Candidate result types

A public `MotionResult` should report:

- `outcome`
- `state`
- `adapter_status`
- `public_error_code`
- `safe_message`
- `retryable`
- `request_id`
- `session_id`
- `public_metadata`

Outcomes should distinguish:

- `completed`
- `unsupported`
- `unavailable`
- `not_configured`
- `not_implemented`
- `interrupted`
- `failed`
- `closed`

## Adapter preflight requirements

A public motion adapter preflight should be able to report:

- adapter disabled;
- mock adapter available;
- Live2D adapter not configured;
- VTS adapter not configured;
- VTS token missing;
- provider execution not allowed;
- adapter runtime not installed;
- model not selected;
- real adapter not implemented yet.

Preflight must not read or expose token values.

## Safety rules

Public motion contracts must not expose:

- VTube Studio auth tokens;
- token file paths;
- raw VTS WebSocket payloads;
- Live2D model private paths;
- provider SDK objects;
- websocket handles;
- local private filesystem paths;
- internal exception repr containing secrets;
- app private character storage paths.

## Relationship to existing public contracts

The motion adapter contract should compose with:

- `RealtimeSession`
- `RealtimeEvent`
- `RealtimeTurnResult`
- `BargeInPolicy`
- `InterruptRequest`
- `InterruptResult`
- `VoiceOutputSession`
- `VoiceOutputResult`
- `VoiceArtifactRef`

It should not bypass or replace the existing public realtime and output-control
contracts.

## Initial scope

The first implementation should be a mock-safe skeleton only.

It should:

- export public motion request/result/capability types;
- provide a mock-safe motion session factory;
- not connect to real VTube Studio;
- not load Live2D or model runtime;
- not read VTS token files;
- not open websocket connections;
- not expose private model paths;
- not claim real adapter readiness;
- integrate with realtime events later through public bridge events.

## Out of scope for this inventory

This inventory does not implement:

- real VTube Studio WebSocket connection;
- real VTS authentication;
- real Live2D model control;
- real expression parameter mapping;
- real mouth sync;
- real motion interruption;
- model-specific preset management.

Those are later checkpoints after the public boundary is fixed.

## Next implementation checkpoint

The next implementation checkpoint should add public motion request/result and
capability type skeletons.

Suggested next commit:

```text
feat/test: add public motion adapter types
```
