# v5.5.0 VTube Studio Operator Acceptance Tooling

## Status

```text
work name: FW-VTS
checkpoint: FW-VTS-0f1
baseline:
48c25b4cd90478bb4bbd18f9a06daf2f4146c179

FW-VTS-0a through FW-VTS-0e:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0f1:
IMPLEMENTED / AWAITING_REVIEW

FW-VTS-0f2 through FW-VTS-0f4:
NOT_AUTHORIZED

real VTS execution: NOT_AUTHORIZED
private token bootstrap: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

FW-VTS-0f1 adds operator-only source tooling. Its smoke and checker are
network-free and do not import actual pyvts, connect a WebSocket, request or
read a real token, authenticate to VTube Studio, trigger a hotkey, or execute
real motion.

## Separation from the public runtime

The root-public `MotionSession` remains explicit-only. It does not read token
files, bootstrap tokens, inspect environment variables, or persist private
configuration. The operator commands are separate executable scripts and are
not imported by `framework`.

The real-motion operator command uses only:

```python
from framework import (
    MotionIntent,
    MotionOutcome,
    MotionRequest,
    create_motion_session,
)
```

It must not import `framework.motion`, `framework.motion_session`, internal VTS
composition/transport modules, `live2d`, pyvts, or WebSocket packages directly.

## Accepted local environment

The later private operator run requires:

```text
pyvts 0.3.3
VTube Studio running locally
VTube Studio API enabled
endpoint host: loopback only
accepted hosts: localhost / 127.0.0.1 / ::1
```

No LAN address, remote host, public WebSocket endpoint, or automatic endpoint
discovery is accepted.

## Private artifact rule

The following must be repository outside artifacts:

```text
private VTube Studio token
private VTube Studio configuration JSON
bootstrap evidence JSON
real-motion operator evidence JSON
```

In other words, every private artifact must use an absolute path outside the
repository. These files must never be staged, committed, copied into a release
package, or pasted into operator logs.

Private evidence may contain bounded booleans, public outcome values, intent
category names, a random run ID, the Framework commit SHA, and the pyvts
version. It must not contain:

```text
token or token hash
token filename or path
endpoint value or WebSocket URL
hotkey name or hotkey ID
selector value
model identity
raw request or response
raw provider exception
screenshots
```

## Operator-only token bootstrap

Tool:

```text
scripts/operator_v550_vtube_studio_token_bootstrap.py
```

Required confirmations:

```text
I_ACCEPT_LOCAL_VTUBE_STUDIO_TOKEN_BOOTSTRAP
I_WILL_KEEP_VTS_TOKEN_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY
```

The tool validates a clean repository, absolute private output paths, loopback
endpoint, positive bounded timeouts, and exact pyvts 0.3.3 before lazily
importing pyvts. It then:

```text
creates a local pyvts client
connects to local VTube Studio
requests operator-approved authentication material
authenticates the returned material
closes the provider client
atomically writes the private token outside the repository
writes bounded bootstrap evidence outside the repository
revalidates repository cleanliness
```

Plugin identity is fixed to the accepted FW-VTS-0d transport identity:

```text
plugin_name: AI Character Framework
developer: murayan
```

Existing token output is not overwritten unless `--overwrite` is explicitly
provided. The console never prints the token, private path, endpoint value, raw
payload, or raw exception.

Example shape only; private paths are deliberately placeholders:

```powershell
python scripts\operator_v550_vtube_studio_token_bootstrap.py `
  --token-output "<absolute-private-token-path>" `
  --evidence-root "<absolute-private-evidence-root>" `
  --confirm-real-vts-execution "I_ACCEPT_LOCAL_VTUBE_STUDIO_TOKEN_BOOTSTRAP" `
  --confirm-private-artifacts-outside-repo "I_WILL_KEEP_VTS_TOKEN_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY"
```

Do not run this command until private token bootstrap is separately authorized.

## Private configuration

The real-motion operator accepts one private JSON file outside the repository:

```json
{
  "schema": "ai-character-framework-v550-vts-private-config-v1",
  "endpoint": {
    "host": "localhost",
    "port": 8001
  },
  "authentication_token_file": "<absolute-private-token-path>",
  "hotkey_bindings": {
    "expression:<private-value>": "<private-hotkey-name>",
    "emotion:<private-value>": "<private-hotkey-name>",
    "gesture:<private-value>": "<private-hotkey-name>",
    "reset_expression": "<private-hotkey-name>",
    "stop_motion": "<private-hotkey-name>"
  }
}
```

Exactly one binding for each of the five accepted intent categories is
required. Hotkey names and selector values remain private and are never copied
into evidence or console output.

## Root-public real-motion acceptance

Tool:

```text
scripts/operator_v550_vtube_studio_real_motion_acceptance.py
```

Required confirmations:

```text
I_ACCEPT_LOCAL_VTUBE_STUDIO_REAL_MOTION_EXECUTION
I_WILL_KEEP_VTS_TOKEN_CONFIG_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY
```

The tool creates the accepted root-public VTS session, performs explicit
`preflight()`, and requires:

```text
adapter_status == configured
supports_real_adapter == true
connected == true
authenticated == true
model_loaded == true
hotkey_inventory_loaded == true
five configured intent capabilities == true
```

It then sends exactly these public intent categories:

```text
expression
emotion
gesture
reset_expression
stop_motion
```

Each result must be `completed` and report public-safe confirmation that a
provider protocol call executed and a configured hotkey resolved. Physical
hotkey and motion execution are accepted only from the combination of that
completed provider request and the operator visual observation. After each
operation the operator must type the corresponding observation phrase:

```text
I_OBSERVED_EXPRESSION_EFFECT
I_OBSERVED_EMOTION_EFFECT
I_OBSERVED_GESTURE_EFFECT
I_OBSERVED_RESET_EFFECT
I_OBSERVED_STOP_EFFECT
```

The prompt identifies only the intent category. It never displays a private
selector or hotkey name.

The run closes the session twice to verify idempotence, confirms
`session.is_closed`, confirms termination of the
`framework-vts-motion-bridge` worker thread, and verifies that the repository
remains clean.

Do not run this command until real VTS execution is separately authorized.

## Private evidence validator

Tool:

```text
scripts/verify_v550_vtube_studio_private_evidence.py
```

The validator accepts only private evidence paths outside the repository and
requires both evidence documents to reference the same 40-character Framework
commit SHA and exact pyvts 0.3.3. It validates the five public intent categories,
manual observation booleans, cleanup, privacy markers, and repository
cleanliness.

It rejects evidence containing data-bearing keys for token material, private
paths, hotkey identities, selector values, model identities, raw payloads, raw
exceptions, or WebSocket URLs.

Run the validator from the clean accepted Framework commit and bind both
private evidence documents to that exact commit:

```powershell
python scripts\verify_v550_vtube_studio_private_evidence.py `
  --bootstrap-evidence-json "<absolute-private-bootstrap-evidence>" `
  --acceptance-evidence-json "<absolute-private-acceptance-evidence>" `
  --expected-head "<accepted-FW-VTS-0f1-commit>"
```

Successful safe markers include:

```text
v550_vts_private_evidence_status: accepted-by-validator
v550_actual_pyvts_imported: True
v550_actual_websocket_connected: True
v550_actual_vts_authenticated: True
v550_actual_model_loaded: True
v550_actual_hotkey_inventory_loaded: True
v550_expression_verified: True
v550_emotion_verified: True
v550_gesture_verified: True
v550_reset_expression_verified: True
v550_stop_motion_verified: True
v550_real_hotkey_execution_verified: True
v550_operator_visual_confirmation_complete: True
v550_session_close_verified: True
v550_bridge_thread_terminated: True
v550_token_material_exposed: False
v550_token_path_exposed: False
v550_hotkey_name_exposed: False
v550_hotkey_identifier_exposed: False
v550_model_identity_exposed: False
v550_provider_payload_exposed: False
v550_raw_exception_exposed: False
v550_private_evidence_outside_repo: True
v550_repo_clean_before_operator_run: True
v550_repo_clean_after_operator_run: True
v550_drc_repo_changed: False
```

## Source-only validation boundary

The FW-VTS-0f1 smoke:

- parses operator imports and rejects eager pyvts/internal Framework imports;
- validates a synthetic private configuration outside the repository;
- validates bounded synthetic evidence structures in memory;
- runs only `--help` paths for operator commands;
- does not import actual pyvts;
- does not connect a WebSocket;
- does not read or write an actual token;
- does not request authentication material;
- does not trigger a real hotkey or motion.

## FW-VTS-0f1 exact eleven-file surface

```text
README.md
docs/public_facade.md
docs/v550_real_motion_adapter_readiness.md
docs/v550_motion_session_real_adapter_composition.md
docs/v550_vtube_studio_pyvts_transport.md
docs/v550_vtube_studio_operator_acceptance.md
scripts/operator_v550_vtube_studio_token_bootstrap.py
scripts/operator_v550_vtube_studio_real_motion_acceptance.py
scripts/verify_v550_vtube_studio_private_evidence.py
scripts/smoke_v550_vtube_studio_operator_acceptance.py
scripts/check_v550_vtube_studio_operator_acceptance.py
```

No Framework runtime, accepted transport/composition source, legacy VTS runtime,
requirements, release metadata, package builder, DRC file, private token,
private configuration, or private evidence belongs to this checkpoint.

## Stop rule

```text
FW-VTS-0f1 source implementation:
allowed only after exact contract authorization

private token bootstrap:
NOT_AUTHORIZED

real pyvts / WebSocket / VTube Studio execution:
NOT_AUTHORIZED

FW-VTS-0f2 public acceptance sync:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

The next checkpoint remains `exact-review-required-for-FW-VTS-0f2` only after
FW-VTS-0f1 source review, commit, push, separately authorized private operator
execution, and accepted private evidence validation.

<!-- FW-VTS-0f1c-OPTIONAL-STOP-CORRECTIVE -->
## FW-VTS-0f1c optional stop_motion corrective

Baseline:

```text
1f737128554d701150427da4ce1c146759881255
```

Status:

```text
implementation: COMPLETED / AWAITING REVIEW
private token bootstrap: COMPLETED / ACCEPTED / REUSE
real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

This corrective supersedes the earlier operator-only exact-five requirement.
VTube Studio hotkey acceptance now has four required intents:

```text
expression
emotion
gesture
reset_expression
```

`stop_motion` is optional and may be configured only when the selected adapter
and model have an actually proven stop operation. A four-binding private config
is valid and must report `supports_stop_motion == false`. A five-binding private
config is valid only when its fifth binding is a real stop operation; renaming
`RemoveAllExpressions` or `TriggerAnimation` to `stop_motion` does not prove
stop support.

The operator executes and visually verifies the four required intents. It
executes and verifies `stop_motion` only when the optional binding is present.
Private evidence records:

```text
required_four_intents_verified
stop_motion_supported
stop_motion_verified
optional_stop_motion_contract
```

Accepted bootstrap evidence may remain tied to the accepted bootstrap commit
when that commit is an ancestor of the corrective acceptance commit and
`scripts/operator_v550_vtube_studio_token_bootstrap.py` is unchanged between
the two commits.

The corrective is an exact ten-file surface limited to six documentation files
and four operator/checker scripts. Framework runtime, public API, pyvts
transport, token bootstrap tooling, release files, and DRC are frozen.

<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:BEGIN -->
## FW-VTS-0f2 public real-motion acceptance sync

This block supersedes earlier pre-execution authorization status for the
FW-VTS-0f operator checkpoint. It records only public-safe facts already
accepted by the private evidence validator.

```text
checkpoint: FW-VTS-0f2
status: IMPLEMENTED / AWAITING_REVIEW
accepted framework head: b7b9639dfa1f675ba04a33cd8ce297429f98fd15
accepted bootstrap head: 1f737128554d701150427da4ce1c146759881255
pyvts version: 0.3.3
actual pyvts import: VERIFIED
actual WebSocket connection: VERIFIED
actual VTube Studio authentication: VERIFIED
model loaded: VERIFIED
hotkey inventory loaded: VERIFIED
expression: VERIFIED
emotion: VERIFIED
gesture: VERIFIED
reset_expression: VERIFIED
required four intents: VERIFIED
stop_motion_supported: False
stop_motion_verified: False
optional stop_motion contract: VERIFIED
real hotkey execution: VERIFIED
real motion execution: VERIFIED
operator visual confirmation: COMPLETE
session close: VERIFIED
bridge thread termination: VERIFIED
bootstrap evidence reused: VERIFIED
bootstrap operator unchanged: VERIFIED
private evidence: ACCEPTED_BY_VALIDATOR
DRC repository changed: False
private values recorded in repository: False
real VTS execution repeated by this sync: False
private evidence read by this sync: False
commit / push: NOT_AUTHORIZED
```

No token material, private path, endpoint value, hotkey identity, selector
value, model identity, provider payload, raw exception, evidence document,
or screenshot is part of this public acceptance record.
<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:END -->

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
