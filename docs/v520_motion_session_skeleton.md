# v5.2.0 Public Motion Session Skeleton

This checkpoint adds the first public motion session skeleton and factory.

It provides a mock-safe app-facing motion / Live2D / VTS adapter boundary for
DRC and other host apps, without connecting to VTube Studio, loading Live2D
runtime, reading token files, opening websockets, accessing private model paths,
or importing provider SDKs.

## Public symbols

The following symbols are exported from `framework`:

- `create_motion_session`
- `MotionSession`
- `MotionSessionInfo`

These build on the public motion adapter types:

- `MotionCapability`
- `MotionRequest`
- `MotionResult`
- `MotionAdapterStatus`
- `MotionState`
- `MotionEventType`
- `MotionErrorCode`

## Factory

Host apps can create a public motion session through the framework root:

```python
import framework

session = framework.create_motion_session(adapter="mock")
```

The factory is keyword-only and mock-safe.

## Session lifecycle

The public session skeleton exposes:

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

`close()` and `dispose()` are idempotent. Calling `apply_motion(...)` after close
returns a provider-neutral `MotionResult.closed(...)` result.

## Mock-safe default behavior

`adapter="mock"` with no real adapter enabled returns `MotionCapability` with
`adapter_status=mock_available`.

`apply_motion(...)` for the mock adapter emits public events and returns a
completed `MotionResult` with `mock_motion=True`.

## Honest real-adapter behavior

Real adapters are not implemented yet.

For `adapter="vts"` or `adapter="live2d"` with `real_adapter_enabled=True`, the
session returns provider-neutral unavailable / not-implemented style results
instead of opening a websocket, reading tokens, loading model paths, or claiming
real adapter readiness.

## Events

Callbacks receive immutable public-safe mapping payloads.

Motion events include:

- `motion.session.created`
- `motion.adapter.preflight.completed`
- `motion.requested`
- `motion.started`
- `motion.completed`
- `motion.unsupported`
- `motion.session.closed`

The payload includes public-safe fields such as event type, session id, request
id, state, adapter, adapter status, outcome, public error code, safe message,
retryable, and public metadata.

## Import safety

`import framework` and `create_motion_session(...)` must not eagerly import
Live2D, VTube Studio, websocket, model runtime, audio, microphone, or provider
SDK modules.

## Next checkpoint

The next checkpoint should add public motion host-app examples showing:

- mock expression / speaking-state requests
- adapter preflight
- closed-session behavior
- real adapter not-implemented / provider-execution guard behavior
