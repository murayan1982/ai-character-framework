# v5.5.0 Motion Adapter Configuration and Status

## Status

```text
work name: FW-VTS
checkpoint: FW-VTS-0b
baseline:
ab5b83cbbaeb88cff9bba352e6b4f46ef5d08294

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

FW-VTS-0b adds an explicit-only, provider-neutral configuration and capability
foundation. It does not bind a transport or execute VTube Studio.

## Public symbols

The Framework root exports:

```python
from framework import (
    MotionAdapterExecutionConfig,
    get_motion_adapter_execution_capability,
    resolve_motion_adapter_execution_config,
)
```

## Explicit-only configuration

`MotionAdapterExecutionConfig` contains only public-safe declarations:

```text
adapter
real_adapter_enabled
allow_provider_execution
endpoint_configured
runtime_available
token_available
model_selected
configured_intents
```

The four readiness fields are boolean availability assertions. This checkpoint
does not accept endpoint values, token values or paths, model values or paths,
hotkey IDs, provider clients, SDK objects, WebSocket objects, or raw provider
payloads.

Configuration source:

```text
explicit_arguments_only
```

There is no process-environment, dotenv, filesystem, import-discovery, token,
model, endpoint, or network fallback.

## Adapter normalization

```text
None / empty:
not configured

disabled / none:
disabled

mock:
mock

vts / vtube_studio / live2d:
canonical adapter = vts

other:
unsupported adapter
```

The `live2d` name remains a compatibility alias. The initial real transport
target is VTube Studio.

## Typed status matrix

```text
adapter missing
  -> NOT_CONFIGURED

adapter disabled
  -> DISABLED

adapter mock
  -> MOCK_AVAILABLE

unsupported adapter
  -> UNSUPPORTED_ADAPTER

vts + real adapter disabled
  -> DISABLED

vts + provider execution denied
  -> PROVIDER_EXECUTION_NOT_ALLOWED

vts + endpoint assertion false
  -> NOT_CONFIGURED

vts + runtime assertion false
  -> RUNTIME_NOT_INSTALLED

vts + token assertion false
  -> TOKEN_MISSING

vts + model assertion false
  -> MODEL_NOT_SELECTED

all explicit assertions true
  -> CONFIGURED
```

`MotionAdapterStatus.CONFIGURED` means only that the explicit declarations are
complete. It does not mean a provider SDK was imported, a client was created, a
network connection exists, or real motion is available.

Even in `CONFIGURED` state:

```text
supports_real_adapter = False
real transport bound = False
real motion available = False
```

## Complete intent capability

`MotionCapability` gains additive fields:

```text
supports_idle_motion
supports_reset_expression
```

It also gains:

```python
capability.supports_intent(intent)
```

The mapping covers all eight `MotionIntent` values:

```text
expression
emotion
speaking_state
idle_motion
gesture
look_at
stop_motion
reset_expression
```

The mock adapter reports all eight as supported.

## Hotkey-first configured intents

The initial VTS configuration accepts only intents that can be represented by
the proven legacy hotkey-list/hotkey-trigger flow:

```text
expression
emotion
gesture
stop_motion
reset_expression
```

The following remain unproven and fail closed with `ValueError` when declared
for VTS:

```text
speaking_state
idle_motion
look_at
```

This checkpoint does not silently claim parameter, mouth/speaking, idle, or
look-at support.

## Capability versus availability

A VTS failure state may retain configured intent flags.

Example:

```text
adapter_status = TOKEN_MISSING
supports_expression = True
supports_emotion = True
supports_real_adapter = False
```

Interpretation:

- an intent flag says that the provider-neutral configuration contains a
  mapping for that intent;
- `adapter_status` says why execution cannot proceed;
- `supports_real_adapter` says whether a real Framework transport is actually
  implemented and available.

Host apps must not execute based on an intent flag alone.

## Public-safe metadata

Capability metadata may include only:

```text
boundary
configuration_source
adapter
adapter_configured
real_adapter_enabled
provider_execution_allowed
endpoint_configured
runtime_available
token_available
model_selected
configuration_complete
configured_intents
provider_sdk_imported=false
provider_client_created=false
network_executed=false
authentication_material_read=false
authentication_location_read=false
model_location_read=false
real_motion_executed=false
reason
```

It must not include endpoint values, token values or paths, model values or
paths, hotkey names or IDs, raw exceptions, provider objects, or raw payloads.

## MotionSession boundary

MotionSession composition remains deferred to FW-VTS-0e.

FW-VTS-0b does not change:

```text
framework/motion_session.py
MotionSession.__init__
MotionSession._resolve_capability
MotionSession.preflight
MotionSession.apply_motion
create_motion_session
MotionSessionInfo.api_version
```

Therefore, after FW-VTS-0b:

```python
session = create_motion_session(
    adapter="vts",
    real_adapter_enabled=True,
    allow_provider_execution=True,
)

session.preflight().adapter_status
# MotionAdapterStatus.NOT_IMPLEMENTED
```

The standalone configuration resolver may return `CONFIGURED`, while the public
session remains `NOT_IMPLEMENTED` until FW-VTS-0e composition.

## Exact nine-file surface

```text
README.md
docs/public_facade.md
docs/v550_real_motion_adapter_readiness.md
docs/v550_motion_adapter_configuration_status.md
framework/__init__.py
framework/motion.py
framework/motion_adapter_execution.py
scripts/smoke_v550_motion_adapter_configuration_status.py
scripts/check_v550_motion_adapter_configuration_status.py
```

## Non-actions

FW-VTS-0b:

- does not read environment variables;
- does not read or write files;
- does not inspect token or model paths;
- does not import pyvts or WebSocket modules;
- does not create a provider client;
- does not connect to VTube Studio;
- does not authenticate;
- does not discover a model;
- does not trigger a hotkey;
- does not update a parameter;
- does not execute real motion;
- does not change legacy VTS runtime;
- does not change requirements or release metadata;
- does not change DRC;
- did not automatically authorize FW-VTS-0c;
- does not commit or push.

## Acceptance markers

```text
v550_motion_adapter_configuration_status: implemented-awaiting-review
v550_exact_change_surface: True
v550_configuration_source: explicit_arguments_only
v550_motion_status_configured_added: True
v550_motion_intent_capability_complete: True
v550_mock_all_intents_supported: True
v550_vts_hotkey_first_intents_only: True
v550_motion_session_composition_changed: False
v550_environment_read: False
v550_filesystem_read: False
v550_actual_pyvts_imported: False
v550_websocket_imported: False
v550_network_executed: False
v550_token_value_read: False
v550_token_path_read: False
v550_model_path_read: False
v550_provider_client_created: False
v550_real_motion_executed: False
v550_legacy_vts_runtime_changed: False
v550_requirements_changed: False
v550_release_metadata_changed: False
v550_drc_changed: False
v550_commit_created: False
v550_push_performed: False
v550_next_authorization: exact-review-required-for-FW-VTS-0c
```

## FW-VTS-0c transport separation

```text
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

The accepted FW-VTS-0b resolver remains unchanged. A `CONFIGURED` capability
still means only that explicit declarations are complete and no transport is
bound.

FW-VTS-0c adds a provider-specific internal async Protocol and in-memory fake in
`framework.vtube_studio_transport`. The transport symbols are not exported from
the Framework root, and MotionSession composition remains deferred to
FW-VTS-0e.

FW-VTS-0c exact eight-file surface:

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

## FW-VTS-0d guarded transport separation

```text
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

The accepted FW-VTS-0b explicit-only resolver remains unchanged. Its
`CONFIGURED` status still represents declaration completeness only.

FW-VTS-0d consumes `MotionAdapterExecutionConfig` inside an internal transport.
All failed adapter, opt-in, endpoint, runtime, authentication-material, and
model-selection guards return before lazy pyvts import or provider-client
creation.

The configuration resolver does not learn endpoint values, authentication
material, pyvts objects, WebSocket objects, or provider responses. MotionSession
composition remains deferred to FW-VTS-0e.

## FW-VTS-0e root-public composition status

```text
FW-VTS-0d:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0e:
IMPLEMENTED / AWAITING_REVIEW

FW-VTS-0f:
NOT_AUTHORIZED

real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

FW-VTS-0e consumes the frozen explicit-only
`MotionAdapterExecutionConfig` without changing its fields or resolver. The
root-public session derives its boolean declarations only from explicitly
supplied VTS arguments and binding intent inventory.

A `CONFIGURED` resolver result still represents declaration completeness. The
session reports `supports_real_adapter=true` only after the injected internal
transport returns `READY` from explicit preflight. Failed static guards return
before importing the composition module or starting its worker thread.

No environment, dotenv, endpoint file, token file, model file, provider payload,
or legacy VTS runtime fallback is added.
