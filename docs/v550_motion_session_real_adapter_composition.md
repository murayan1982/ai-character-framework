# v5.5.0 MotionSession Real-Adapter Composition

## Status

```text
work name: FW-VTS
checkpoint: FW-VTS-0e
baseline:
767a5f428998927c183a4c6040cb948b98f86711

FW-VTS-0a:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0b:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0c:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0d:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0e:
IMPLEMENTED / AWAITING_REVIEW

FW-VTS-0f:
NOT_AUTHORIZED

real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

## Purpose

FW-VTS-0e composes the accepted internal asynchronous VTube Studio transport
behind the existing synchronous root-public `MotionSession` boundary:

```text
root-public MotionSession
    -> internal VTS composition
    -> persistent sync/async bridge
    -> frozen VTubeStudioTransport Protocol
    -> guarded VTubeStudioPyvtsTransport
```

Provider-specific composition, bridge, transport, client, and configuration
types remain internal and are not exported from `framework`.

## Public API

`MotionSession` and `create_motion_session()` retain their existing keyword-only
arguments and add default-off VTS composition arguments:

```text
runtime_available
model_selected
vts_endpoint_host
vts_endpoint_port
vts_authentication_token
vts_hotkey_bindings
vts_connect_timeout_seconds
vts_authenticate_timeout_seconds
vts_request_timeout_seconds
vts_close_timeout_seconds
```

`MotionSessionInfo.api_version` is `5.5.0`.

The legacy call with only adapter and double opt-in remains typed
`not_implemented`. This prevents an older host from entering a partially
configured real path accidentally.

## Explicit-only configuration

The composition reads no environment variables, dotenv files, endpoint files,
token files, model files, or legacy runtime state. It derives readiness only
from explicit arguments.

The session does not import the composition module or start a worker thread when
an adapter, provider-execution, endpoint, runtime, authentication-material, or
model guard fails.

Endpoint and authentication values are private fields. They are never copied to
public metadata, safe messages, results, events, or repr-bearing public types.

## Hotkey binding contract

The maximum binding count is 256. Selectors and hotkey names are trimmed and
bounded to 128 characters. Selectors are normalized case-insensitively and
normalization collisions are rejected.

Accepted selectors:

```text
expression:<value>
emotion:<value>
gesture:<value>
stop_motion
reset_expression
```

Unproven intents remain unsupported:

```text
speaking_state
idle_motion
look_at
```

Missing intent values or missing configured bindings return typed local failures
without calling the transport. Provider hotkey names remain internal.

## Preflight

An explicitly composed session must complete preflight before apply. Static
guards and binding validation occur before lazy composition. A transport `READY`
result produces a public `CONFIGURED` capability with
`supports_real_adapter=true` and only the configured hotkey-first intent flags.

Failed preflight results remain provider-safe. They do not expose endpoint,
authentication, model, hotkey, payload, or exception values.

## Persistent sync/async bridge

Each composed session lazily owns at most one worker thread and one persistent
asyncio event loop. The synchronous public methods submit transport coroutines
with `asyncio.run_coroutine_threadsafe`.

This design deliberately does not use per-call `asyncio.run` or
`run_until_complete`. A pyvts/WebSocket client created during preflight therefore
stays on the same event loop for later trigger and close calls.

The public API can be called while the host thread already has an active asyncio
event loop because provider operations execute on the separate session-owned
loop.

No reconnect loop, retry loop, polling loop, waiting-operation queue, or detached
background task is created.

## Apply normalization

```text
transport COMPLETED -> public COMPLETED / NONE
transport NOT_FOUND -> public NOT_CONFIGURED / NOT_CONFIGURED
transport BUSY -> public UNAVAILABLE / UNAVAILABLE / retryable
transport TIMED_OUT -> public FAILED / PROVIDER_ERROR / retryable
transport FAILED -> public FAILED / PROVIDER_ERROR
transport UNAVAILABLE -> public UNAVAILABLE / UNAVAILABLE
transport CLOSED -> public CLOSED / SESSION_CLOSED
```

The accepted internal transport single-flight boundary remains authoritative.
A concurrent second apply is submitted to the same event loop and returns
`BUSY` immediately instead of waiting in a Framework-owned queue.

## Close and late completion

Close is idempotent. The first call:

```text
marks the public session closed
marks the internal composition closed
invokes bounded transport close when the bridge exists
cancels remaining session-owned operations
stops the persistent event loop
joins the worker thread
emits one motion.session.closed event
```

A trigger finishing after close cannot publish success. It normalizes to
`CLOSED` with `late_completion_suppressed=true` when the marker is available.
Later close calls do nothing.

## Validation boundary

The dedicated smoke patches the internal transport constructor with
in-memory Protocol implementations and blocks socket connections. It validates:

- public signature and `5.5.0` API version;
- mock and legacy VTS compatibility;
- failed-guard import/thread laziness;
- binding normalization and privacy;
- mandatory preflight;
- one persistent event-loop identity across calls;
- all public transport outcome mappings;
- immediate single-flight `BUSY`;
- active-host-event-loop safety;
- close idempotence and worker termination;
- close during apply and late-completion suppression;
- absence of actual pyvts/WebSocket/network/token-file/real-motion execution.

## Exact change surface

```text
README.md
docs/public_facade.md
docs/v550_motion_adapter_configuration_status.md
docs/v550_real_motion_adapter_readiness.md
docs/v550_vtube_studio_transport_protocol_fake.md
docs/v550_vtube_studio_pyvts_transport.md
docs/v550_motion_session_real_adapter_composition.md
framework/motion_session.py
framework/vtube_studio_motion_composition.py
scripts/smoke_v550_motion_session_real_adapter_composition.py
scripts/check_v550_motion_session_real_adapter_composition.py
```

## Non-actions

FW-VTS-0e does not:

- change the frozen FW-VTS-0c Protocol;
- change the accepted FW-VTS-0d pyvts transport;
- export provider-specific symbols from the Framework root;
- read or write token files;
- bootstrap or request a token;
- read environment or dotenv configuration;
- retry, reconnect, or poll automatically;
- change the legacy VTS runtime;
- change requirements, release metadata, or DRC;
- import actual pyvts or open a WebSocket during validation;
- authenticate to VTube Studio or execute a real hotkey/motion;
- authorize FW-VTS-0f;
- commit or push.

## Acceptance markers

```text
v550_motion_session_real_adapter_composition_status: implemented-awaiting-review
v550_exact_change_surface: True
v550_public_motion_api_version: 5.5.0
v550_root_public_motion_session_composed: True
v550_internal_transport_root_exported: False
v550_persistent_session_event_loop: True
v550_asyncio_run_per_call_used: False
v550_active_host_event_loop_safe: True
v550_mock_compatibility_preserved: True
v550_legacy_vts_not_implemented_compatibility_preserved: True
v550_preflight_required_before_apply: True
v550_hotkey_binding_normalization_complete: True
v550_single_flight_enforced: True
v550_close_idempotent: True
v550_bridge_thread_terminated: True
v550_late_completion_suppressed: True
v550_actual_pyvts_imported: False
v550_websocket_imported: False
v550_network_executed: False
v550_token_file_read: False
v550_token_file_write: False
v550_token_bootstrap_executed: False
v550_real_hotkey_triggered: False
v550_real_motion_executed: False
v550_commit_created: False
v550_push_performed: False
v550_next_authorization: exact-review-required-for-FW-VTS-0f
```
