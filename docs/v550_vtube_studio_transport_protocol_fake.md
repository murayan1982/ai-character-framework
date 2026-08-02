# v5.5.0 VTube Studio Transport Protocol and Fake

## Status

```text
work name: FW-VTS
checkpoint: FW-VTS-0c
baseline:
31a6f6abcd4096a07a3719fb937e3a907fd044cd

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

FW-VTS-0c defines an internal async VTube Studio transport Protocol and a
deterministic in-memory fake. It does not implement a real pyvts/WebSocket
transport and does not compose the transport into MotionSession.

## Internal-only symbols

```python
from framework.vtube_studio_transport import (
    FakeVTubeStudioTransport,
    VTubeStudioHotkeyRequest,
    VTubeStudioTransport,
    VTubeStudioTransportFactory,
    VTubeStudioTransportOperation,
    VTubeStudioTransportOutcome,
    VTubeStudioTransportResult,
)
```

These symbols are not exported from the Framework root. Host applications and
DRC must not import this internal provider-specific module. They continue to
consume only root-public provider-neutral APIs.

## Internal async Protocol

```python
@runtime_checkable
class VTubeStudioTransport(Protocol):
    @property
    def transport_name(self) -> str:
        ...

    @property
    def is_closed(self) -> bool:
        ...

    async def preflight(self) -> VTubeStudioTransportResult:
        ...

    async def trigger_hotkey(
        self,
        request: VTubeStudioHotkeyRequest,
    ) -> VTubeStudioTransportResult:
        ...

    async def close(self) -> VTubeStudioTransportResult:
        ...
```

Factory alias:

```python
VTubeStudioTransportFactory = Callable[[], VTubeStudioTransport]
```

FW-VTS-0c does not invoke a factory, create a provider client, connect, or
authenticate.

## Operations and outcomes

Operations:

```text
preflight
trigger_hotkey
close
```

Outcomes:

```text
ready
completed
unavailable
not_found
busy
timed_out
failed
closed
```

`busy` and `timed_out` are reserved for the later bounded real transport. The
FW-VTS-0c fake does not generate them.

## Bounded hotkey request

`VTubeStudioHotkeyRequest` accepts:

```text
intent
hotkey_name
request_id
public_metadata
```

Hotkey-first intents:

```text
expression
emotion
gesture
stop_motion
reset_expression
```

Unproven intents fail closed:

```text
speaking_state
idle_motion
look_at
```

The internal hotkey name is trimmed and validated, but omitted from dataclass
repr, public request dictionaries, result metadata, safe messages, and result
repr. Provider hotkey IDs are not represented by the request or result types.

## Provider-safe result

`VTubeStudioTransportResult` contains:

```text
operation
outcome
request_id
safe_message
retryable
public_metadata
```

It exposes `is_success` and `is_terminal`. It does not contain a provider
client, WebSocket object, endpoint, authentication material, model location,
hotkey name, hotkey ID, raw exception, or raw provider payload.

## Deterministic in-memory fake

`FakeVTubeStudioTransport` stores only synthetic in-memory fixtures:

```text
available
available hotkey names
failing hotkey names
closed state
operation call counts
received internal requests
```

Hotkey lookup trims fixture values and is case-insensitive. No hotkey ID
conversion occurs.

### Preflight matrix

```text
open + available
  -> READY

open + unavailable
  -> UNAVAILABLE

closed
  -> CLOSED
```

### Trigger matrix

```text
closed
  -> CLOSED

unavailable
  -> UNAVAILABLE

unknown synthetic hotkey
  -> NOT_FOUND

configured failing synthetic hotkey
  -> FAILED

configured normal synthetic hotkey
  -> COMPLETED
```

`COMPLETED` means only that an in-memory fake protocol call completed. It does
not mean VTube Studio received a request or a Live2D model moved.

### Close matrix

```text
first close
  -> COMPLETED
  -> already_closed=false

second and later close
  -> COMPLETED
  -> already_closed=true
```

Close is idempotent.

## Result metadata

Provider-safe fake result metadata may include:

```text
boundary=vts_transport
transport=fake_vts
fake_transport=true
fake_protocol_call_executed
available_hotkey_count
hotkey_resolved
already_closed
provider_sdk_imported=false
provider_client_created=false
network_executed=false
authentication_material_accessed=false
authentication_location_accessed=false
model_location_accessed=false
raw_payload_exposed=false
hotkey_identifier_exposed=false
hotkey_name_exposed=false
real_hotkey_triggered=false
real_motion_executed=false
reason
```

It does not include fixture hotkey names, failing hotkey names, provider
hotkey IDs, endpoints, authentication material or locations, model names or
locations, raw exceptions, raw requests, or raw responses.

## Concurrency boundary

FW-VTS-0c fixes only the async method shape.

```text
background task creation:
forbidden

async lock:
not created

sleep:
not executed

timeout execution:
not executed

retry:
not executed

reconnect:
not executed

single-flight enforcement:
deferred to FW-VTS-0d
```

All fake operations complete immediately and deterministically.

## MotionSession boundary

MotionSession composition remains deferred to FW-VTS-0e.

FW-VTS-0c does not change:

```text
framework/__init__.py
framework/motion.py
framework/motion_session.py
framework/motion_adapter_execution.py
```

The root-public VTS alias remains typed `NOT_IMPLEMENTED`, and the standalone
FW-VTS-0b `CONFIGURED` status still means that no transport is bound.

## FW-VTS-0d handoff

FW-VTS-0d may implement this internal Protocol with a lazy pyvts transport only
after separate exact review and authorization.

Required future properties include:

```text
explicit double opt-in before provider import
bounded connect/auth/preflight/trigger/close
timeout normalization
single-flight enforcement
idempotent cleanup
safe exception normalization
no automatic retry
no background reconnect
no public authentication material
no raw provider payload
```

## Exact eight-file surface

```text
README.md
docs/public_facade.md
docs/v550_motion_adapter_configuration_status.md
docs/v550_real_motion_adapter_readiness.md
docs/v550_vtube_studio_transport_protocol_fake.md
framework/vtube_studio_transport.py
scripts/smoke_v550_vtube_studio_transport_protocol_fake.py
scripts/check_v550_vtube_studio_transport_protocol_fake.py
```

## Non-actions

FW-VTS-0c:

- does not read environment variables;
- does not read or write files;
- does not import pyvts or WebSocket modules;
- does not create a provider client;
- does not connect or authenticate;
- does not inspect or write authentication material;
- does not discover a model;
- does not resolve or expose a provider hotkey ID;
- does not trigger a real hotkey;
- does not execute real motion;
- does not create background tasks or locks;
- does not retry or reconnect;
- does not change the root-public API;
- does not change MotionSession or the 0b resolver;
- does not change legacy VTS runtime;
- does not change requirements or release metadata;
- does not change DRC;
- does not authorize FW-VTS-0d automatically;
- does not commit or push.

## Acceptance markers

```text
v550_vtube_studio_transport_protocol_fake_status: implemented-awaiting-review
v550_exact_change_surface: True
v550_transport_protocol_async: True
v550_transport_protocol_runtime_checkable: True
v550_transport_factory_defined: True
v550_transport_root_public_exported: False
v550_fake_transport_in_memory_only: True
v550_fake_transport_deterministic: True
v550_fake_protocol_call_executed: True
v550_hotkey_request_bounded: True
v550_hotkey_first_intents_only: True
v550_transport_result_provider_safe: True
v550_hotkey_names_exposed_in_results: False
v550_hotkey_ids_exposed: False
v550_raw_payload_exposed: False
v550_raw_exception_exposed: False
v550_close_idempotent: True
v550_background_tasks_created: False
v550_async_lock_created: False
v550_retry_executed: False
v550_reconnect_executed: False
v550_motion_session_composition_changed: False
v550_configuration_resolver_changed: False
v550_root_public_api_changed: False
v550_environment_read: False
v550_filesystem_read: False
v550_actual_pyvts_imported: False
v550_websocket_imported: False
v550_network_executed: False
v550_token_read: False
v550_token_written: False
v550_model_discovery_executed: False
v550_real_hotkey_triggered: False
v550_real_motion_executed: False
v550_legacy_vts_runtime_changed: False
v550_requirements_changed: False
v550_release_metadata_changed: False
v550_drc_changed: False
v550_commit_created: False
v550_push_performed: False
v550_next_authorization: exact-review-required-for-FW-VTS-0d
```

## FW-VTS-0d guarded implementation handoff

```text
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

The FW-VTS-0c Protocol and result enums remain frozen. FW-VTS-0d implements the
Protocol in `framework.vtube_studio_pyvts_transport` without changing this
module or exporting provider-specific symbols from the Framework root.

The implementation adds lazy pyvts import, explicit private configuration,
bounded connect/authentication/inventory/trigger/close operations,
single-flight enforcement, idempotent cleanup, and late-completion suppression.

MotionSession composition remains deferred to FW-VTS-0e.

## FW-VTS-0e composition handoff

The FW-VTS-0c async Protocol and result enums remain frozen. FW-VTS-0e binds an
implementation of that Protocol behind root-public `MotionSession` using an
internal persistent sync/async bridge.

The dedicated composition smoke substitutes deterministic in-memory Protocol
implementations. It verifies preflight, trigger outcome normalization,
single-flight behavior, close during an active trigger, and late-completion
suppression without importing pyvts or opening a network connection.

The Protocol, fake transport, hotkey request, and transport result remain
internal and are not exported from the Framework root.
