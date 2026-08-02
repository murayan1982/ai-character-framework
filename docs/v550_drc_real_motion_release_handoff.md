# v5.5.0 DRC Real-Motion Release Handoff

## Status

```text
Framework v5.5.0 real-motion contract: FIXED_FOR_RELEASE
DRC RT-7: READY_AFTER_V5.5.0_TAG_PUSH
DRC repository changed by this checkpoint: False
```

## Release condition

DRC RT-7 may re-evaluate real-motion integration only after all of the following
are true:

```text
FW-VTS-0f4b committed and pushed
final v5.5.0 package rebuilt from that clean commit
strict final tag-readiness gate accepted
v5.5.0 tag created and pushed
DRC pins a fixed released Framework artifact or tag
```

A source checkout, untagged moving branch, private operator artifact, or
uncommitted Framework tree is not the released handoff.

## Root-public import boundary

DRC imports motion types only from `framework`:

```python
from framework import (
    MotionRequest,
    create_motion_session,
)
```

Minimum released flow:

```python
session = create_motion_session(
    adapter="vts",
    real_adapter_enabled=True,
    allow_provider_execution=True,
)

try:
    capability = session.preflight()
    result = session.apply_motion(request)
finally:
    session.close()
```

DRC branches only from public typed capabilities, outcomes, error codes, safe
messages, and events.

## Capability handoff

The released capability contract is honest per intent:

```text
expression: available only when configured and reported supported
emotion: available only when configured and reported supported
gesture: available only when configured and reported supported
reset_expression: available only when configured and reported supported
stop_motion: optional
speaking_state: do not assume support
idle_motion: do not assume support
look_at: do not assume support
```

The accepted model-specific result is:

```text
expression: VERIFIED
emotion: VERIFIED
gesture: VERIFIED
reset_expression: VERIFIED
stop_motion_supported: False
stop_motion_verified: False
```

DRC must not convert the optional stop result into a required feature. It must
degrade safely when `stop_motion` is unavailable.

## DRC ownership

DRC may own:

- lifecycle-to-motion intent mapping;
- app UI state and character behavior policy;
- selection of a provider-neutral Framework motion request;
- display of bounded public-safe status;
- session lifecycle and idempotent cleanup calls;
- app-level fallback when an intent is unsupported or unavailable.

## Framework ownership

Framework owns:

- guard evaluation;
- pyvts dependency and client construction;
- loopback WebSocket lifecycle;
- authentication and token use;
- model and hotkey inventory;
- configured intent mapping;
- timeout and single-flight behavior;
- public-safe exception normalization;
- provider-neutral capabilities, results, events, and cleanup.

## Prohibited DRC workarounds

DRC must not:

```text
import framework.motion directly
import framework.motion_session directly
import framework.vtube_studio_* modules
import live2d modules
import internal plugins
import pyvts
implement or own a VTube Studio WebSocket
read, create, replace, or delete VTube Studio token files
read private Framework operator configuration or evidence
process raw VTube Studio request or response payloads
expose internal hotkey identifiers
normalize raw provider exceptions
depend on private model paths or endpoint details
add checkout/CWD/sys.path workarounds for this release boundary
```

Missing capability must remain a Framework release concern rather than a DRC
provider-specific bypass.

## Guard and privacy behavior

Normal root import, mock operation, capability inspection, and closed-guard
preflight stop before pyvts import and network execution.

The following never cross the public DRC handoff:

```text
token values or token paths
private selector values
private model identity
hotkey names or identifiers
raw provider payloads
raw exceptions
private evidence
screenshots
private endpoint values
```

## DRC RT-7 start rule

```text
Before v5.5.0 tag push:
DRC RT-7 remains blocked.

After v5.5.0 tag push:
DRC RT-7 may begin exact contract review against the fixed released artifact.

A tag push does not automatically authorize DRC implementation:
DRC must still perform its own exact contract review and stage authorization.
```

## Public verification markers

```text
v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag
v550_drc_rt7_public_only_contract_fixed: True
v550_drc_fixed_release_artifact_required: True
v550_drc_required_four_intents_fixed: True
v550_drc_stop_motion_optional: True
v550_drc_unsupported_intents_not_assumed: True
v550_drc_internal_import_allowed: False
v550_drc_pyvts_ownership_allowed: False
v550_drc_websocket_ownership_allowed: False
v550_drc_token_ownership_allowed: False
v550_drc_raw_payload_handling_allowed: False
v550_drc_repository_changed: False
```
