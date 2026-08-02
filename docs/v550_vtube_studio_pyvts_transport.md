# v5.5.0 Guarded Lazy pyvts Transport

## Status

```text
work name: FW-VTS
checkpoint: FW-VTS-0d
baseline:
9b22985c5b3b1bf53cea5397baf28e970a5b01a1

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

FW-VTS-0d implements the frozen FW-VTS-0c internal async transport Protocol with
a guarded lazy pyvts transport. Validation uses an injected fake pyvts module
and fake client only.

## Internal-only symbols

```python
from framework.vtube_studio_pyvts_transport import (
    VTubeStudioPyvtsClient,
    VTubeStudioPyvtsClientFactory,
    VTubeStudioPyvtsModuleImporter,
    VTubeStudioPyvtsTransport,
    VTubeStudioPyvtsTransportConfig,
)
```

These symbols are not exported from the Framework root. Host applications and
DRC must not import the provider-specific module. MotionSession composition
remains deferred to FW-VTS-0e.

## Private transport configuration

`VTubeStudioPyvtsTransportConfig` accepts:

```text
execution_config
endpoint_host
endpoint_port
authentication_token
plugin_name
plugin_developer
connect_timeout_seconds
authenticate_timeout_seconds
request_timeout_seconds
close_timeout_seconds
```

Endpoint values and authentication material are internal-only and omitted from
repr and public metadata.

The configuration does not read:

```text
process environment
dotenv files
token files
model files
endpoint files
```

The configuration does not write or bootstrap authentication tokens.

## Pre-import guards

The transport returns before lazy provider import when any of the following is
false or invalid:

```text
adapter is VTS
real adapter enabled
provider execution allowed
endpoint configured
runtime available
authentication material available
model selected
endpoint value valid
authentication material present
```

This is the required double opt-in:

```text
real_adapter_enabled=true
allow_provider_execution=true
```

Normal Framework import, configuration construction, failed-guard preflight,
and closed-transport preflight do not import pyvts.

## Lazy pyvts and client factory

The default module importer performs:

```python
importlib.import_module("pyvts")
```

only after every explicit guard passes.

The default client factory constructs a pyvts client with an explicitly
injected host and port. Token-file persistence is disabled:

```text
authentication_token_path=""
```

The transport never calls token-file read/write or token-request APIs.
Authentication uses only the explicitly injected material.

## Bounded preflight

Preflight sequence:

```text
guard checks
single-flight reservation
lazy pyvts import
client creation
bounded connect
bounded authentication request
bounded hotkey inventory request
model-loaded validation
case-insensitive hotkey-name inventory
READY
```

Preflight outcomes include:

```text
READY
BUSY
UNAVAILABLE
TIMED_OUT
FAILED
CLOSED
```

An already-ready transport returns `READY` without reconnecting.

A failed preflight closes and discards an already-created client on a
best-effort bounded path.

## Hotkey inventory privacy

The transport reads only enough of the provider response to validate:

```text
data.modelLoaded
data.availableHotkeys
availableHotkeys[*].name
```

It keeps only trimmed case-insensitive hotkey-name lookup keys.

It does not retain or expose:

```text
model name
model ID
model path
hotkey ID
hotkey file
key combination
raw inventory response
```

Provider hotkey IDs are not created, stored, or exposed.

## Bounded trigger

`trigger_hotkey()` requires:

```text
valid VTubeStudioHotkeyRequest
transport ready
single-flight slot free
hotkey present in preflight inventory
```

Known names are sent through the pyvts request builder. Unknown names return
`NOT_FOUND` without a provider call.

Trigger outcomes include:

```text
COMPLETED
NOT_FOUND
BUSY
TIMED_OUT
FAILED
CLOSED
```

There is no automatic inventory refresh, retry, authentication refresh, or
reconnect.

## Single-flight

Preflight and trigger share one immediate reservation flag.

```text
one active preflight or trigger:
allowed

second operation:
BUSY
```

The transport creates no waiting queue and no background task. It does not use
an async lock.

## Timeout ownership

Individual `asyncio.wait_for()` boundaries cover:

```text
connect
authentication request
hotkey inventory request
hotkey trigger request
provider close
```

Timeout results identify only the public-safe stage. They do not expose
provider payloads or exceptions.

## Late-completion suppression

Every provider operation records the current lifecycle generation.

Close marks the transport closed and advances the generation before awaiting
provider cleanup. A provider call that finishes after close returns `CLOSED`
with late completion suppressed instead of returning success.

## Idempotent close

First close:

```text
mark closed
advance lifecycle generation
clear readiness and hotkey inventory
detach provider client
bounded provider close
```

Second and later close:

```text
COMPLETED
already_closed=true
no provider call
```

A close timeout or provider exception leaves the transport closed and
non-reopenable.

## Provider-safe metadata

Results may contain only bounded declarations and booleans such as:

```text
boundary=pyvts_transport
transport=pyvts
reason
provider_import_attempted
provider_sdk_imported
provider_client_factory_invoked
provider_client_created
provider_protocol_call_executed
network_execution_attempted
connected
authenticated
model_loaded
hotkey_inventory_loaded
available_hotkey_count
hotkey_resolved
single_flight_enforced
late_completion_suppressed
already_ready
already_closed
timeout_stage
```

All results keep these false:

```text
raw_payload_exposed
raw_exception_exposed
endpoint_exposed
authentication_material_exposed
authentication_location_exposed
model_identity_exposed
hotkey_name_exposed
hotkey_identifier_exposed
real_hotkey_triggered
real_motion_executed
```

Results and safe messages never include endpoint values, authentication
material, token locations, model identities, hotkey names, hotkey IDs, raw
provider responses, raw provider exceptions, pyvts clients, or WebSocket
objects.

## Fake-pyvts-only validation

The dedicated smoke injects:

```text
fake pyvts module marker
fake pyvts client marker
fake request builder
synthetic responses
synthetic delays and failures
```

It verifies:

```text
guard-before-import
default client-factory shape
connect/authentication/inventory success
case-insensitive hotkey trigger
not-found short circuit
import and provider failure normalization
connect/authentication/inventory/trigger/close timeouts
single-flight BUSY result
close during active trigger
late-completion suppression
idempotent close
privacy
```

Actual pyvts, WebSocket, network, and VTube Studio are not used.

## MotionSession and FW-VTS-0e

FW-VTS-0d does not change:

```text
framework/__init__.py
framework/motion.py
framework/motion_session.py
framework/motion_adapter_execution.py
framework/vtube_studio_transport.py
```

The root-public VTS alias remains typed `NOT_IMPLEMENTED`.

FW-VTS-0e must separately review and implement:

```text
root-public MotionSession composition
MotionRequest to configured-hotkey mapping
bounded synchronous-to-asynchronous bridge
MotionCapability normalization
MotionResult and event normalization
transport lifecycle ownership per session
```

## Exact nine-file surface

```text
README.md
docs/public_facade.md
docs/v550_motion_adapter_configuration_status.md
docs/v550_real_motion_adapter_readiness.md
docs/v550_vtube_studio_transport_protocol_fake.md
docs/v550_vtube_studio_pyvts_transport.md
framework/vtube_studio_pyvts_transport.py
scripts/smoke_v550_vtube_studio_pyvts_transport.py
scripts/check_v550_vtube_studio_pyvts_transport.py
```

## Non-actions

FW-VTS-0d:

- does not change the root-public API;
- does not compose MotionSession;
- does not read environment variables or dotenv files;
- does not read or write token files;
- does not request or bootstrap a token;
- does not discover model files;
- does not store model identities or provider hotkey IDs;
- does not expose endpoint, authentication, model, hotkey, payload, or
  exception values;
- does not automatically retry or reconnect;
- does not create background tasks or waiting queues;
- does not change the legacy VTS runtime;
- does not change requirements or release metadata;
- does not change DRC;
- does not authorize FW-VTS-0e automatically;
- does not execute actual pyvts/WebSocket/VTube Studio during validation;
- does not commit or push.

## Acceptance markers

```text
v550_vtube_studio_pyvts_transport_status: implemented-awaiting-review
v550_exact_change_surface: True
v550_pyvts_transport_internal_only: True
v550_pyvts_transport_protocol_conforms: True
v550_lazy_pyvts_import_implemented: True
v550_preimport_guards_fail_closed: True
v550_double_opt_in_required: True
v550_injected_authentication_material_only: True
v550_token_file_read: False
v550_token_file_write: False
v550_token_bootstrap_executed: False
v550_endpoint_values_exposed: False
v550_authentication_material_exposed: False
v550_model_identity_exposed: False
v550_hotkey_names_exposed_in_results: False
v550_hotkey_ids_created: False
v550_hotkey_ids_stored: False
v550_hotkey_ids_exposed: False
v550_provider_response_exposed: False
v550_provider_exception_exposed: False
v550_connect_timeout_enforced: True
v550_authenticate_timeout_enforced: True
v550_request_timeout_enforced: True
v550_close_timeout_enforced: True
v550_single_flight_enforced: True
v550_waiting_operation_queue_created: False
v550_automatic_retry_executed: False
v550_automatic_reconnect_executed: False
v550_background_tasks_created: False
v550_close_idempotent: True
v550_late_completion_suppressed: True
v550_fake_pyvts_module_used: True
v550_fake_pyvts_client_used: True
v550_fake_provider_protocol_call_executed: True
v550_actual_pyvts_imported: False
v550_websocket_imported: False
v550_network_executed: False
v550_real_hotkey_triggered: False
v550_real_motion_executed: False
v550_motion_session_composition_changed: False
v550_configuration_resolver_changed: False
v550_root_public_api_changed: False
v550_legacy_vts_runtime_changed: False
v550_requirements_changed: False
v550_release_metadata_changed: False
v550_drc_changed: False
v550_commit_created: False
v550_push_performed: False
v550_next_authorization: exact-review-required-for-FW-VTS-0e
```

## FW-VTS-0e MotionSession composition

FW-VTS-0e composes this accepted transport without changing its frozen source.
The transport is constructed only after the root-public session has passed all
explicit adapter, provider-execution, endpoint, runtime, authentication, model,
and hotkey-binding guards.

The synchronous public API does not create a new event loop for each call.
Instead, each composed session lazily owns one worker thread and one persistent
asyncio event loop. Preflight, hotkey trigger, and transport close are submitted
to that same loop. Closing the session marks it closed first, invokes bounded
transport cleanup, cancels remaining session operations, stops the loop, and
joins the worker thread.

The FW-VTS-0e smoke replaces `VTubeStudioPyvtsTransport` with an in-memory
Protocol implementation. Therefore actual lazy pyvts import, WebSocket
connection, VTube Studio authentication, and real hotkey execution remain
NOT_AUTHORIZED and are not performed by this checkpoint.

## FW-VTS-0f1 operator acceptance boundary

FW-VTS-0f1 does not modify this accepted transport. The separate token bootstrap
operator uses the same public plugin identity and exact pyvts 0.3.3 against a
loopback only endpoint. It persists authentication material only to an explicit
private path repository outside.

The later real-motion operator does not import this module. It injects private
authentication material through the root-public `MotionSession`, which lazily
constructs this transport after all existing guards pass.

The FW-VTS-0f1 smoke validates source structure only. It does not import actual
pyvts, create a provider client, connect a WebSocket, request/authenticate a
token, enumerate real hotkeys, or execute real motion.

```text
real VTS execution: NOT_AUTHORIZED
private token bootstrap: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
