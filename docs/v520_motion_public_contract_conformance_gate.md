# v5.2.0 Motion Public Contract Conformance Gate

This checkpoint adds a conformance gate for the public motion / Live2D / VTS
adapter contract added so far in v5.2.0.

The gate is intentionally mock-safe. It does not execute real Live2D, VTube
Studio WebSocket, token access, model loading, provider SDK behavior, audio
runtime, or character runtime control.

## Covered public contract

The gate verifies the public `framework` root exposes:

- `MotionAdapterStatus`
- `MotionState`
- `MotionEventType`
- `MotionErrorCode`
- `MotionIntent`
- `MotionOutcome`
- `MotionCapability`
- `MotionRequest`
- `MotionResult`
- `create_motion_session`
- `MotionSession`
- `MotionSessionInfo`

## Public import rule

The gate verifies that host apps can use:

```python
import framework
```

without eager motion provider imports.

The public root import must not load Live2D, VTube Studio, websocket, model
runtime, audio, microphone, or provider SDK modules.

## Type rule

The gate verifies:

- motion adapter status / state / event / error enums;
- `MotionCapability.disabled(...)`;
- `MotionCapability.mock_available()`;
- `MotionRequest.expression_change(...)`;
- `MotionRequest.emotion_update(...)`;
- `MotionRequest.speaking_state(...)`;
- `MotionRequest.stop_motion(...)`;
- `MotionResult.completed(...)`;
- `MotionResult.unavailable(...)`;
- `MotionResult.not_implemented(...)`;
- `MotionResult.closed(...)`.

All public metadata must be secret-safe.

## Session rule

The gate verifies `MotionSession` exposes:

- `info`
- `capability`
- `state`
- `is_closed`
- `on_event(callback)`
- `emit_created()`
- `preflight()`
- `apply_motion(...)`
- `close()`
- `dispose()`
- context manager support

The gate also verifies honest adapter behavior:

- mock adapter completes locally;
- real adapter path does not overclaim readiness;
- provider execution guard returns typed unavailable result;
- unsupported adapter returns typed unavailable result;
- closed session returns typed closed result.

## Host-app example rule

The gate verifies public motion host-app examples exist and use only public
`import framework` style.

The examples must not import FW internals, Live2D/VTS modules, websocket modules,
token files, private model paths, or provider SDKs.

## Current limitation

This gate does not require real Live2D, real VTS WebSocket, token access, model
loading, or character runtime control.

At this point, the public contract must honestly return mock-completed /
unavailable / not-implemented / closed-session results rather than claiming real
motion adapter readiness.
