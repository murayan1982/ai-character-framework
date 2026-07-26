# v5.2.0 Motion Host-App Examples

This checkpoint adds mock-safe host-app examples for the public motion / Live2D /
VTS adapter boundary.

These examples are intended for DRC-style external app integration. They use
only public `framework` imports and do not import FW internals, character runtime
internals, model runtime code, token files, private model paths, or provider SDKs.

## Examples

### Motion expression and speaking-state flow

```text
examples/app_motion_session_expression_flow.py
```

Shows how a host app can:

- create a public motion session;
- register public event callbacks;
- emit a session-created event;
- request an expression change;
- request a speaking-state change;
- receive typed `MotionResult` values.

The mock adapter returns completed results with `mock_motion=True`.

### Motion adapter preflight

```text
examples/app_motion_adapter_preflight.py
```

Shows how a host app can call `preflight()` and read public
`MotionCapability` information:

- adapter;
- adapter status;
- expression support;
- speaking-state support;
- real adapter support.

The mock adapter reports `mock_available` and `supports_real_adapter=False`.

### Motion closed-session behavior

```text
examples/app_motion_closed_session_behavior.py
```

Shows how a host app can close/dispose a motion session and receive a typed
`MotionResult.closed(...)` result when trying to apply motion afterward.

### Motion real-adapter guard behavior

```text
examples/app_motion_real_adapter_guard.py
```

Shows how a host app can request a real adapter path while provider execution is
not allowed.

The session returns a provider-neutral unavailable result with
`provider_execution_not_allowed` rather than touching real adapter runtime state.

## Integration rule

Host apps should use:

```python
import framework
```

and public symbols such as:

- `framework.create_motion_session(...)`
- `framework.MotionRequest`
- `framework.MotionResult`
- `framework.MotionCapability`
- `framework.MotionAdapterStatus`
- `framework.MotionErrorCode`

Host apps should not use FW internals, direct adapter connections, private model
paths, token files, provider payloads, or checkout-layout workarounds.

## Real runtime status

These examples intentionally do not execute real Live2D, VTS adapter runtime,
model loading, token access, or character runtime control.

At this checkpoint, the public control surface exists and reports honest typed
results for mock-completed / unavailable / not-implemented / closed-session
cases.
