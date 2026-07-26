# v5.2.0 Public Motion Adapter Types

This checkpoint adds the first public motion / Live2D / VTS adapter contract
skeleton.

It is intentionally limited to provider-neutral public data types. It does not
add `MotionSession`, realtime motion wiring, real Live2D runtime, or real VTube
Studio WebSocket behavior yet.

## Public symbols

The following symbols are exported from `framework`:

- `MotionAdapterStatus`
- `MotionState`
- `MotionEventType`
- `MotionErrorCode`
- `MotionIntent`
- `MotionOutcome`
- `MotionCapability`
- `MotionRequest`
- `MotionResult`

## Adapter status

`MotionAdapterStatus` can represent public preflight states such as:

- `disabled`
- `mock_available`
- `not_configured`
- `token_missing`
- `provider_execution_not_allowed`
- `runtime_not_installed`
- `model_not_selected`
- `not_implemented`
- `unsupported_adapter`
- `closed`

These statuses let FW be honest about real adapter readiness without exposing
VTS tokens, model paths, or provider internals.

## Motion states and events

`MotionState` includes:

- `idle`
- `preparing`
- `speaking`
- `expressing`
- `gesturing`
- `interrupted`
- `failed`
- `closed`
- `unavailable`

`MotionEventType` includes:

- `motion.session.created`
- `motion.adapter.preflight.completed`
- `motion.requested`
- `motion.started`
- `motion.completed`
- `motion.interrupted`
- `motion.failed`
- `motion.unsupported`
- `motion.session.closed`

## Motion request

`MotionRequest` supports provider-neutral intents:

- `expression`
- `emotion`
- `speaking_state`
- `idle_motion`
- `gesture`
- `look_at`
- `stop_motion`
- `reset_expression`

Helper constructors include:

- `MotionRequest.expression_change(...)`
- `MotionRequest.emotion_update(...)`
- `MotionRequest.speaking_state(...)`
- `MotionRequest.stop_motion(...)`

## Motion result

`MotionResult` supports outcomes:

- `completed`
- `unsupported`
- `unavailable`
- `not_configured`
- `not_implemented`
- `interrupted`
- `failed`
- `closed`

Helper constructors include:

- `MotionResult.completed(...)`
- `MotionResult.unavailable(...)`
- `MotionResult.not_implemented(...)`
- `MotionResult.closed(...)`

## Capability snapshot

`MotionCapability` describes provider-neutral public adapter readiness.

Helper constructors include:

- `MotionCapability.disabled(...)`
- `MotionCapability.mock_available()`

`supports_real_adapter` remains false in this checkpoint.

## Safety rules

These public types must not expose:

- VTube Studio auth tokens;
- token file paths;
- raw VTS WebSocket payloads;
- Live2D model private paths;
- provider SDK objects;
- websocket handles;
- local private filesystem paths;
- internal exception repr containing secrets;
- app private character storage paths.

Secret-like metadata keys are redacted.

## Import safety

`import framework` must not eagerly import Live2D, VTube Studio, websocket,
model runtime, audio, microphone, or provider SDK modules.

This checkpoint keeps the public motion types in `framework.motion` with no
provider imports.

## Next checkpoint

The next checkpoint should add a mock-safe public `MotionSession` skeleton and
factory:

- `create_motion_session(...)`
- `MotionSession`
- `MotionSessionInfo`

The session should return typed unavailable / mock-completed / closed results
without connecting to real VTS or loading Live2D runtime.
