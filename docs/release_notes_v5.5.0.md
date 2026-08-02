# AI Character Framework v5.5.0 Release Notes

## Real Motion Adapter / VTube Studio

v5.5.0 adds the released root-public real-motion adapter boundary for configured
VTube Studio integrations.

The release keeps the existing provider-neutral public motion contract and adds
an explicit, guarded real adapter path backed by lazy `pyvts==0.3.3`
composition.

## Highlights

- Root-public real-motion session construction through
  `create_motion_session(adapter="vts", ...)`.
- Explicit double opt-in before provider/VTube Studio execution.
- Lazy pyvts import and bounded loopback WebSocket ownership.
- Typed provider-neutral configuration, preflight, capability, result, event,
  timeout, and cleanup boundaries.
- Hotkey-first support for configured expression, emotion, gesture, and reset
  intents.
- Optional `stop_motion` behavior with honest capability reporting.
- Deterministic v5.5.0 source-package builder and SHA-256 sidecar.
- Hard rejection of tracked private VTube Studio token, configuration, and
  evidence paths.
- Fixed public-only DRC RT-7 release handoff contract.

## Public host-app contract

Host applications import motion APIs only from the Framework root:

```python
from framework import (
    MotionRequest,
    create_motion_session,
)

session = create_motion_session(
    adapter="vts",
    real_adapter_enabled=True,
    allow_provider_execution=True,
)

try:
    capability = session.preflight()
    result = session.apply_motion(
        MotionRequest(
            intent="emotion",
            value="happy",
        )
    )
finally:
    session.close()
```

Host applications must branch from typed Framework capability and result
objects. They must not depend on pyvts objects, WebSocket objects, internal
hotkey identifiers, token files, private model paths, or raw provider payloads.

## Explicit execution boundary

Real VTube Studio execution remains default-off. Both the real adapter and
external/provider execution must be explicitly enabled before the transport may
import pyvts or connect.

Closed guards fail before provider import. Normal Framework root import, mock
session creation, capability inspection, source-tree readiness, package gates,
and DRC handoff checks remain provider-safe and network-free.

## Accepted real-motion scope

The accepted configured local VTube Studio run verified:

```text
expression: VERIFIED
emotion: VERIFIED
gesture: VERIFIED
reset_expression: VERIFIED
required four intents: VERIFIED
```

For the accepted model:

```text
stop_motion_supported: False
stop_motion_verified: False
optional stop_motion contract: ACCEPTED
```

Host applications must not infer support for:

```text
speaking_state
idle_motion
look_at
```

Support is reported only through the public capability result.

## Privacy and safety boundary

The following remain outside the repository and release package:

```text
authentication token values
token file paths
private VTS configuration values
private selector values
private model identity
private hotkey names and identifiers
raw WebSocket/provider payloads
raw exceptions
operator evidence
screenshots
```

The public acceptance record contains only bounded safe markers. The v5.5.0
builder rejects tracked:

```text
config/tokens/**
*_token.json
vts_private_config.json
bootstrap_evidence.json
real_motion_operator_evidence.json
operator_evidence/**
```

The package and tag gates do not read those files.

## Compatibility

- The mock motion adapter remains available.
- Framework root import remains provider-safe.
- Existing v5.2 provider-neutral motion types remain the host-app contract.
- Unsupported and unavailable states remain typed rather than raising raw
  provider exceptions.
- Session cleanup remains explicit and idempotent.
- Legacy full-runtime VTS behavior is not exposed as the root-public adapter.
- DRC must consume the released Framework boundary rather than implementing a
  VTube Studio client or importing Framework internals.

## DRC RT-7 handoff

DRC RT-7 may re-evaluate real-motion integration only after the `v5.5.0` tag is
created and pushed.

DRC must use a fixed released Framework artifact and root-public imports only.
It must not:

```text
import framework.motion or framework.motion_session directly
import live2d or internal VTS modules
import pyvts
own the VTube Studio WebSocket
read or write token files
process raw VTube Studio payloads
normalize provider exceptions
```

The accepted capability handoff is:

```text
expression: configured support
emotion: configured support
gesture: configured support
reset_expression: configured support
stop_motion: optional; current accepted model reports false
speaking_state: do not assume support
idle_motion: do not assume support
look_at: do not assume support
```

## Release verification

After the FW-VTS-0f4b source checkpoint is committed and pushed, rebuild the
final package from that clean commit:

```powershell
python scripts\build_v550_release_package.py

python scripts\smoke_v550_final_release_tag_readiness.py `
  --require-clean-tree `
  --require-package
```

The strict gate verifies:

```text
clean main HEAD and origin/main match
v5.5.0 tag absent
ZIP and SHA-256 sidecar present
sidecar digest matches ZIP
ZIP integrity and duplicate-entry checks pass
ZIP membership matches the exact committed package set
temporary deterministic rebuild matches byte-for-byte
private VTS artifacts are absent
DRC released handoff is public-only
```

Only after that strict gate passes may the operator create and push `v5.5.0`.

## Release state recorded by this source checkpoint

```text
FW-VTS-0f4a: ACCEPTED / PUSHED
FW-VTS-0f4b: IMPLEMENTED / AWAITING_REVIEW
final package: REBUILD_REQUIRED_AFTER_COMMIT
v5.5.0 tag: NOT_CREATED
DRC RT-7: READY_AFTER_V5.5.0_TAG_PUSH
```

This document contains no private token, configuration, evidence, selector,
hotkey, model, endpoint, provider payload, raw exception, or screenshot value.
