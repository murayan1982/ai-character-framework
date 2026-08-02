# v5.5.0 Candidate Real Motion Adapter Readiness

## Status

```text
work name: FW-VTS
release line: v5.5.0 candidate
FW-VTS-0a: COMPLETED / ACCEPTED / PUSHED
FW-VTS-0b: COMPLETED / ACCEPTED / PUSHED
FW-VTS-0c: COMPLETED / ACCEPTED / PUSHED
FW-VTS-0d: COMPLETED / ACCEPTED / PUSHED
FW-VTS-0e: IMPLEMENTED / AWAITING_REVIEW
FW-VTS-0f: NOT_AUTHORIZED
real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

FW-VTS-0a is a docs/test-only inventory and safety-contract checkpoint. It does
not implement or authorize real VTube Studio execution.

Baseline:

```text
FW v5.4.0:
d313eb6acb643103fe25988720ebee5976a04f78
```

The Framework release line may become v5.5.0, while the existing public motion
API remains the v5.2.0 contract until a later exact review explicitly changes
its API version.

## Driver

Daily Rhythm Companion RT-7 already has provider-neutral lifecycle-to-motion
mapping and root-public mock MotionSession integration. DRC must not implement a
VTube Studio client or bypass Framework ownership.

```text
DRC RT-7:
CURRENT / NOT_COMPLETED
BLOCKED_FRAMEWORK_REAL_MOTION_ADAPTER_RELEASE_REQUIRED
```

## Public motion skeleton freeze

The v5.2.0 root-public motion skeleton is frozen as the starting contract:

- `MotionAdapterStatus`
- `MotionCapability`
- `MotionErrorCode`
- `MotionEventType`
- `MotionIntent`
- `MotionOutcome`
- `MotionRequest`
- `MotionResult`
- `MotionState`
- `MotionSession`
- `MotionSessionInfo`
- `create_motion_session`

Host applications import only from `framework`.

```python
from framework import (
    MotionRequest,
    MotionResult,
    create_motion_session,
)
```

Current behavior remains unchanged:

- `adapter="mock"` executes locally;
- VTS aliases are recognized but do not execute;
- a closed provider-execution guard returns typed
  `provider_execution_not_allowed`;
- an open guard still returns typed `not_implemented`;
- `real_adapter_supported` remains false;
- root import and mock operation do not import pyvts or open a WebSocket.

FW-VTS-0a does not change `framework/motion.py`,
`framework/motion_session.py`, or `framework/__init__.py`.

## Legacy VTS call graph

The existing full runtime owns a working legacy VTS hotkey flow:

```text
presets/text_vts.json or presets/voice_vts.json
  -> config.vts_enabled
  -> core.runtime.initialize_components()
  -> live2d.vts_client.VTSClient()
  -> VTSClient.connect()
  -> runtime["vts"]
  -> pipeline emotion event
  -> plugins.builtin.emotion_vts.EmotionVTSPlugin
  -> core.emotion.resolve_emotion_hotkey()
  -> VTSClient.trigger_hotkey()
  -> core.runtime.shutdown_components()
  -> VTSClient.close()
```

## Legacy transport ownership

`live2d/vts_client.py` currently owns all of the following responsibilities:

- eager `pyvts` import;
- pyvts client construction;
- WebSocket connect and close;
- token-directory creation;
- stored-token loading;
- authentication request handling;
- token request, replacement, persistence, and deletion;
- hotkey-list request and hotkey-ID cache;
- named hotkey triggering;
- an `asyncio.Lock` around API requests;
- reconnect behavior;
- internal exception/debug output.

This implementation is an inventory and reuse source. It is not itself the
root-public real adapter.

## Responsibility split

Reusable internal behavior:

- VTS hotkey-list and trigger request knowledge;
- emotion-to-character-hotkey resolution;
- bounded connection/authentication concepts;
- API-call serialization concept;
- explicit close ownership.

Behavior that must not cross directly into the public contract:

- pyvts objects;
- WebSocket objects;
- authentication tokens;
- plugin developer tokens;
- token file paths;
- private model paths;
- raw request/response payloads;
- raw API exceptions;
- internal hotkey IDs;
- private endpoint details;
- credential or environment values.

New public-adapter responsibilities:

- explicit default-off configuration;
- pre-import fail-closed checks;
- provider-neutral typed preflight;
- intent-specific honest capability reporting;
- bounded request/result normalization;
- timeout and single-flight ownership;
- idempotent cleanup;
- bounded public-safe events and messages;
- late-completion suppression after close.

## Hotkey-first initial scope

The legacy implementation proves hotkey-list and hotkey-trigger operations.
It does not currently prove public-safe parameter injection, look-at control,
mouth-parameter control, or model discovery.

The initial real adapter therefore uses a hotkey-first scope.

| Motion intent | Initial real-adapter position |
| --- | --- |
| `expression` | supported only with configured hotkey mapping |
| `emotion` | emotion-to-hotkey mapping |
| `gesture` | supported only with configured hotkey mapping |
| `reset_expression` | supported only with configured reset hotkey |
| `stop_motion` | supported only with configured stop/remove hotkey |
| `speaking_state` | unsupported until separately proven |
| `idle_motion` | unsupported until separately proven |
| `look_at` | unsupported until a parameter API is separately proven |

Current `MotionCapability` does not expose every intent independently. The
exact provider-neutral capability expansion belongs to FW-VTS-0b.

## Guard reservation

FW-VTS-0a reserves the following candidate configuration names:

```env
FRAMEWORK_MOTION_REAL_ADAPTER=0
FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION=0
FRAMEWORK_MOTION_ADAPTER=mock
```

These entries are documentation-only in FW-VTS-0a and have no runtime effect.

Before a future real transport may import pyvts, all of the following must be
true:

1. real adapter is enabled;
2. external/provider execution is allowed;
3. selected adapter is a VTS alias;
4. endpoint configuration is valid;
5. authentication/token readiness is valid;
6. model-selection state is valid;
7. a single-flight apply slot is available.

Normal Framework import, capability inventory, mock session creation, and
closed-guard preflight must stop before pyvts import.

## Token policy

The legacy full runtime can bootstrap and persist a token. The new public
MotionSession adapter does not silently bootstrap a token during ordinary
preflight.

Required future behavior:

- missing token returns typed `token_missing`;
- token values are never returned, logged, committed, or stored in operator
  evidence;
- token path stays internal;
- token bootstrap is operator-only and belongs to FW-VTS-0f;
- DRC does not read or write the token.

Current source safety:

- `.gitignore` excludes `config/tokens/`;
- `.gitignore` excludes `*_token.json`;
- no token file is tracked.

Current package hardening gap:

- the v5.4.0 package builder uses `git ls-files`;
- this excludes an ordinary untracked token;
- it does not yet explicitly reject a force-tracked `config/tokens/` file.

FW-VTS-0f owns an explicit release-package rejection for `config/tokens/` and
`*_token.json`.

## Sync/async bridge

The root-public `MotionSession.apply_motion()` API is synchronous while pyvts is
asynchronous. FW-VTS-0a does not choose or implement the bridge.

FW-VTS-0d and FW-VTS-0e exact reviews must choose a bounded design that:

- does not create a background reconnect loop;
- does not retry automatically in the first release;
- enforces connect/auth/apply/close timeouts;
- permits at most one active apply per session;
- makes close idempotent;
- suppresses late completion after close;
- does not deadlock when called from a host with an active event loop.

## Exact ownership split

### FW-VTS-0b

Provider-neutral real-motion configuration, capability, and status contract.

- fake-only;
- no pyvts import;
- no network;
- pre-import fail-closed states;
- intent-specific honest capability.

### FW-VTS-0c

Injected VTube Studio transport protocol and fake transport/client adapter.

- fake/in-memory only;
- no WebSocket;
- deterministic tests;
- bounded transport request/result contract.

### FW-VTS-0d

Guarded real pyvts/WebSocket transport.

- lazy pyvts import;
- explicit double opt-in;
- bounded connect/auth/apply/close;
- timeout and single-flight;
- safe exception normalization;
- no automatic retry or background reconnect;
- no public token or raw payload.

### FW-VTS-0e

Root-public MotionSession real-adapter composition.

- `create_motion_session(adapter="vts", ...)`;
- root-public imports only for host apps;
- mock compatibility;
- provider-neutral capability/result/event normalization;
- bounded sync/async composition.

### FW-VTS-0f

Configured local VTube Studio operator acceptance and release preparation.

- configured real VTube Studio execution;
- supported expression/emotion/gesture/reset/stop verification;
- cleanup and token privacy;
- aggregate readiness and package gate;
- released DRC handoff contract.

Completion of one checkpoint does not authorize the next checkpoint.

## DRC minimum released contract

DRC may re-evaluate RT-7 only after a Framework release provides:

```python
session = create_motion_session(
    adapter="vts",
    real_adapter_enabled=True,
    allow_provider_execution=True,
)

capability = session.preflight()
result = session.apply_motion(request)
session.close()
```

Required behavior includes:

- real support is reported only when actually available;
- closed guards fail before provider import;
- VTS unavailable, token missing, runtime missing, model missing, unsupported
  intent, and not-implemented cases are typed;
- `apply_motion()` returns provider-neutral outcomes;
- capabilities are honest per intent;
- close releases adapter resources;
- mock behavior remains compatible;
- raw exceptions, tokens, paths, payloads, hotkey IDs, and provider objects
  never reach public results.

## DRC RT-7 stop rule

```text
DRC RT-7 stop rule:
do not begin DRC real-motion integration before FW-VTS-0f is accepted,
the Framework real adapter is released, and its root-public contract is fixed.
```

DRC must not:

- import `framework.motion` or `framework.motion_session` directly;
- import `live2d`, plugins, or internal adapters;
- import or use pyvts;
- implement a WebSocket client;
- operate token files;
- process raw VTS payloads;
- own provider exception normalization.

## FW-VTS-0a exact seven-file surface

```text
README.md
.env.example
docs/public_facade.md
docs/app_integration_contract.md
docs/v550_real_motion_adapter_readiness.md
scripts/smoke_v550_real_motion_adapter_readiness.py
scripts/check_v550_real_motion_adapter_readiness.py
```

No Framework runtime Python, legacy VTS runtime, plugin, preset, character,
requirements/lockfile, release metadata, package metadata, or DRC file changes
belong to this checkpoint.

## Non-actions

FW-VTS-0a:

- does not import pyvts;
- does not open a WebSocket;
- does not authenticate with VTube Studio;
- does not generate, read, update, or remove a token;
- does not discover a model;
- does not trigger a hotkey;
- does not update a parameter;
- does not execute real motion;
- does not access a private model path;
- does not change runtime Python;
- does not change requirements;
- does not change release metadata;
- does not change DRC;
- did not automatically authorize FW-VTS-0b;
- does not commit or push.

## Acceptance markers

```text
v550_real_motion_adapter_readiness_status: implemented-awaiting-review
v550_exact_change_surface: True
v550_framework_runtime_changed: False
v550_legacy_vts_runtime_changed: False
v550_requirements_changed: False
v550_release_metadata_changed: False
v550_drc_changed: False
v550_public_motion_skeleton_frozen: True
v550_legacy_vts_inventory_complete: True
v550_hotkey_first_scope_fixed: True
v550_motion_guards_default_off: True
v550_actual_pyvts_imported: False
v550_websocket_connection_executed: False
v550_token_read: False
v550_token_written: False
v550_model_discovery_executed: False
v550_hotkey_triggered: False
v550_parameter_update_executed: False
v550_real_motion_executed: False
v550_commit_created: False
v550_push_performed: False
v550_next_authorization: exact-review-required-for-FW-VTS-0b
```

## FW-VTS-0b implementation checkpoint

```text
FW-VTS-0a:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0b:
IMPLEMENTED / AWAITING_REVIEW

FW-VTS-0c through FW-VTS-0f:
NOT_AUTHORIZED

real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

FW-VTS-0b baseline:

```text
ab5b83cbbaeb88cff9bba352e6b4f46ef5d08294
```

The checkpoint adds a standalone explicit-only provider-neutral configuration
and capability resolver, `MotionAdapterStatus.CONFIGURED`, complete eight-intent
capability inspection, and hotkey-first VTS configured-intent validation.

MotionSession composition remains deferred to FW-VTS-0e. The existing public
session still reports typed `not_implemented` for an enabled VTS alias.

FW-VTS-0b exact nine-file surface:

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

No environment lookup, filesystem access, pyvts/WebSocket import, provider
client creation, network execution, token/model path access, real motion,
legacy VTS runtime change, requirements change, release metadata change, or DRC
change is authorized.

## FW-VTS-0c implementation checkpoint

```text
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

FW-VTS-0c baseline:

```text
31a6f6abcd4096a07a3719fb937e3a907fd044cd
```

The checkpoint adds an internal async VTube Studio transport Protocol, bounded
hotkey request/result types, a transport factory alias, and a deterministic
in-memory fake.

The symbols are not exported from the Framework root. MotionSession composition
remains deferred to FW-VTS-0e, and the real lazy pyvts/WebSocket transport
remains deferred to FW-VTS-0d.

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

No environment lookup, filesystem access, pyvts/WebSocket import, provider
client creation, network execution, authentication material access, model
discovery, provider hotkey-ID resolution, real hotkey trigger, real motion,
legacy VTS runtime change, requirements change, release metadata change, or DRC
change is authorized.

## FW-VTS-0d implementation checkpoint

```text
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

FW-VTS-0d baseline:

```text
9b22985c5b3b1bf53cea5397baf28e970a5b01a1
```

The checkpoint implements the frozen internal async transport Protocol with a
guarded lazy pyvts transport.

Implemented boundaries:

- explicit double opt-in before provider import;
- explicit endpoint and authentication-material injection;
- no environment or token-file fallback;
- bounded connect, authentication, inventory, trigger, and close operations;
- single-flight preflight/trigger reservation without a waiting queue;
- idempotent close;
- late-completion suppression after close;
- provider-safe result and exception normalization;
- no automatic retry or reconnect;
- no background tasks;
- no public endpoint, authentication material, model identity, hotkey name,
  hotkey ID, raw response, or raw exception.

The dedicated smoke executes the transport only with an injected fake pyvts
module and fake client. Actual pyvts/WebSocket/VTube Studio execution remains
unauthorized.

FW-VTS-0d exact nine-file surface:

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

## FW-VTS-0e implementation checkpoint

```text
baseline:
767a5f428998927c183a4c6040cb948b98f86711

FW-VTS-0d:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0e:
IMPLEMENTED / AWAITING_REVIEW

FW-VTS-0f:
NOT_AUTHORIZED

real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Implemented boundaries:

- root-public `MotionSession` VTS composition behind explicit-only arguments;
- preserved mock and legacy VTS `not_implemented` compatibility paths;
- normalized and bounded hotkey bindings for five accepted intents;
- mandatory explicit preflight before apply;
- one session-owned worker thread and persistent asyncio event loop;
- `asyncio.run_coroutine_threadsafe` submission from the synchronous public API;
- immediate internal single-flight `BUSY` normalization;
- provider-safe capability, result, and event normalization;
- idempotent close, pending-operation cancellation, worker termination, and
  late-completion suppression;
- no root export of composition, bridge, transport, or pyvts symbols.

Validation uses injected in-memory transports only. It blocks network calls and
verifies that actual pyvts/WebSocket modules remain unloaded. Token-file
read/write/bootstrap, retry, reconnect, polling, actual authentication, real
hotkey trigger, and real motion are not performed.

FW-VTS-0e exact eleven-file surface:

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

## FW-VTS-0f1 operator-tooling implementation checkpoint

```text
baseline:
48c25b4cd90478bb4bbd18f9a06daf2f4146c179

FW-VTS-0e:
COMPLETED / ACCEPTED / PUSHED

FW-VTS-0f1:
IMPLEMENTED / AWAITING_REVIEW

FW-VTS-0f2 through FW-VTS-0f4:
NOT_AUTHORIZED

real VTS execution: NOT_AUTHORIZED
private token bootstrap: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

FW-VTS-0f1 adds operator-only source tooling for a later configured local VTube
Studio acceptance. It requires pyvts 0.3.3, loopback only endpoints, exact
five-intent configuration, explicit operator confirmations, manual visual
confirmation, bounded cleanup, and private artifacts repository outside.

The root-public runtime remains unchanged. `MotionSession` still does not read,
write, or bootstrap token files. The real-motion operator calls only the
Framework root-public API, while the separate bootstrap tool owns the later
operator-approved local authentication request.

FW-VTS-0f1 exact eleven-file surface:

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

Validation is source-only and network-free. It does not import actual pyvts,
open a WebSocket, read or write a real token, request authentication material,
trigger a real hotkey, execute real motion, or authorize FW-VTS-0f2.

```text
v550_next_authorization: exact-review-required-for-FW-VTS-0f2
```

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
