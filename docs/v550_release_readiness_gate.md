# v5.5.0 Source-Tree Release Readiness Gate

<!-- FW-VTS-0f3-RELEASE-READINESS:BEGIN -->
## FW-VTS-0f3 aggregate release readiness

This block records only public, repository-safe facts. It does not repeat the
private VTube Studio operator run and does not read private token,
configuration, or evidence files.

```text
checkpoint: FW-VTS-0f3
status: IMPLEMENTED / AWAITING_REVIEW
baseline head: a1c39369bd35b21196b25a93a82798f47f1dad30
accepted real-motion head: b7b9639dfa1f675ba04a33cd8ce297429f98fd15
accepted bootstrap head: 1f737128554d701150427da4ce1c146759881255
FW-VTS-0a: ACCEPTED / PUSHED
FW-VTS-0b: ACCEPTED / PUSHED
FW-VTS-0c: ACCEPTED / PUSHED
FW-VTS-0d: ACCEPTED / PUSHED
FW-VTS-0e: ACCEPTED / PUSHED
FW-VTS-0f1: ACCEPTED / PUSHED
FW-VTS-0f2: ACCEPTED / PUSHED
required four intents: ACCEPTED
stop_motion_supported: False
stop_motion_verified: False
optional stop_motion contract: ACCEPTED
private real-motion evidence: ACCEPTED_BY_PUBLIC_SYNC
release package created: False
v5.5.0 tag created: False
DRC repository changed: False
release package authorization: READY_FOR_FW-VTS-0f4_AFTER_REVIEW
commit / push: NOT_AUTHORIZED
```
<!-- FW-VTS-0f3-RELEASE-READINESS:END -->

## Purpose

FW-VTS-0f3 aggregates the accepted v5.5.0 real-motion adapter line into a
source-tree release-readiness gate. It verifies the current committed public
contract and source-only regressions without importing actual pyvts, opening a
WebSocket, reading private VTube Studio artifacts, or executing motion.

## Accepted inputs

The gate accepts the committed FW-VTS-0a through FW-VTS-0f2 checkpoints,
including the public safe-marker synchronization of the separately validated
real local VTube Studio run.

The accepted operator result contains four required intents:

```text
expression
emotion
gesture
reset_expression
```

The selected model has no proven generic stop operation, so the accepted
optional contract is:

```text
stop_motion_supported: False
stop_motion_verified: False
```

## Source-only dependency set

<!-- FW-VTS-0f3c1-DEPENDENCY-SYNC:BEGIN -->
The gate executes exactly these seven current-compatible source-only
dependencies:

```text
scripts/smoke_app_sdk.py
scripts/smoke_v550_vtube_studio_transport_protocol_fake.py
scripts/smoke_v550_vtube_studio_pyvts_transport.py
scripts/smoke_v550_motion_session_real_adapter_composition.py
scripts/smoke_v550_vtube_studio_operator_acceptance.py
scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py
scripts/check_release_package.py
```

All dependency runs are local and source-only. Provider execution guards are
forced closed for the gate.

The following historical smokes are deliberately excluded from the aggregate
v5.5.0 gate because later accepted checkpoints superseded their exact
assumptions:

- `scripts/smoke_public_facade.py` requires the pre-v5.2 exact
  `framework.__all__` list;
- `scripts/smoke_v550_real_motion_adapter_readiness.py` requires the
  pre-real-adapter `not_implemented` behavior;
- `scripts/smoke_v550_motion_adapter_configuration_status.py` freezes an
  earlier configuration checkpoint superseded by the accepted transport and
  root-public composition checkpoints.

The executable dependency tuple and this public list must remain identical.
<!-- FW-VTS-0f3c1-DEPENDENCY-SYNC:END -->

## Private artifact rejection

Tracked source is rejected when it contains any of the following:

```text
config/tokens/**
*_token.json
vts_private_config.json
bootstrap_evidence.json
real_motion_operator_evidence.json
operator_evidence/**
```

The gate inspects only tracked repository paths. It does not inspect private
directories outside the repository.

## Release state

The gate requires:

```text
v5.4.0 tag: present
v5.5.0 tag: absent
release/ai-character-framework_v5.5.0.zip: absent
release/ai-character-framework_v5.5.0.zip.sha256: absent
```

FW-VTS-0f3 does not build the release package. Deterministic package construction,
strict package verification, release notes, final tag readiness, and released
DRC handoff remain reserved for FW-VTS-0f4.

## Explicit non-actions

FW-VTS-0f3:

- does not read a VTube Studio token;
- does not read private configuration or evidence;
- does not connect to VTube Studio;
- does not execute a real hotkey or motion;
- does not modify Framework runtime or operator tooling;
- does not create a release ZIP or checksum;
- does not create or push a tag;
- does not modify DRC.

<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:BEGIN -->
## FW-VTS-0f4a deterministic release-package gate

This checkpoint adds the deterministic v5.5.0 source-package builder and
temporary package gate. It does not create the final release package, tag,
push, publish, connect to VTube Studio, or read private VTS artifacts.

```text
checkpoint: FW-VTS-0f4a
status: IMPLEMENTED / AWAITING_REVIEW
baseline head: a83f7efe85d489887b1d97122b2756e2a1b57ff5
package version: 5.5.0
deterministic temporary builds required: 2
tracked private VTS artifact rejection: REQUIRED
final release ZIP created: False
final SHA-256 sidecar created: False
v5.5.0 tag created: False
DRC repository changed: False
next authorization: READY_FOR_FW-VTS-0f4b_AFTER_REVIEW
commit / push: NOT_AUTHORIZED
```
<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:END -->
