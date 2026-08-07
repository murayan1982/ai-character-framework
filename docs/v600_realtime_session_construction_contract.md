# FW-RT6-4a RealtimeSession Construction Contract

This document fixes the provider-neutral public construction/config vocabulary
for AI Character Framework v6.0.0. Controls A and B establish immutable models,
construction adoption, preflight composition, and capability aggregation. Control
C exposes the typed construction result, prevents silent mock fallback for explicit
real-runtime requests, and synchronizes aggregate FW-RT6-4a acceptance. Commit
and push remain separately authorized.

<!-- FW-RT6-4a-A-CONSTRUCTION-MODELS:BEGIN -->
## Control A — public construction and config models

### Public models

Control A appends three names to the canonical Framework root-public API:

```text
RealtimeSessionConfig
RealtimeSessionConstructionStatus
RealtimeSessionConstructionResult
```

The accepted 121-name prefix remains unchanged. The exact root-public count is
therefore 124.

### `RealtimeSessionConfig`

The immutable config contains only provider-neutral composition intent:

```text
real_runtime_enabled: bool = False
voice_input_stage
text_generation_stage
voice_output_stage
motion_stage
```

All stage bindings are excluded from `repr`. The config contains no provider
selector, credential, endpoint, private path, provider client, raw payload, or
provider-specific handle. Control A does not validate, preflight, execute,
close, or adopt a supplied stage.

### Construction status

```text
mock_ready
real_configuration_ready
configuration_incomplete
preflight_failed
```

### Construction result

The immutable typed result carries:

```text
status
session_id
configuration_complete
runtime_executable
real_runtime_requested
real_runtime_enabled
missing_stage_kinds
failed_stage_kinds
safe_message
retryable
public_metadata
```

`session_id` must be one Framework `SessionId`. Stage-kind diagnostics accept
only the four canonical provider-neutral values and reject duplicates. Public
metadata is recursively sanitized and immutable. Private-path-like safe messages
are replaced by one stable public-safe message.

Logical invariants prevent an enabled real runtime from being reported unless
it is requested, configured, and executable. `configuration_incomplete` requires
at least one missing stage kind. `preflight_failed` requires at least one failed
stage kind.

### Realtime error vocabulary

Control A adds the provider-neutral code:

```text
RealtimeErrorCode.CONFIGURATION_MISSING = "configuration_missing"
```

No current `RealtimeSession.run_turn()` path uses the new code in Control A.
Runtime adoption and no-silent-fallback behavior remain Controls B/C.

### Deferred boundaries

```text
RealtimeSession constructor config parameter: DEFERRED / Control B
legacy argument normalization: DEFERRED / Control B
stage protocol validation through config: DEFERRED / Control B
stage preflight execution: DEFERRED / Control B
capability snapshot aggregation: DEFERRED / Control B
construction_result session property: DEFERRED / Control C
real-request typed run_turn rejection: DEFERRED / Control C
mock fallback guard: DEFERRED / Control C
tasklist checkbox completion: DEFERRED / aggregate acceptance
```

### Control A status

```text
checkpoint: FW-RT6-4a Control A
baseline head: 0192f941e3a2009d203535ec0c97a6ceb69050ed
baseline subject: unavailable in git archive / source snapshot verified
status: ACCEPTED / CONTROL B AUTHORIZED
root-public names: 124 / ADDITIVE THREE-NAME SUFFIX
RealtimeSessionConfig default real runtime: False
stage objects exposed by repr: False
construction result immutable: True
configuration missing typed code: True
RealtimeSession runtime adoption: False / DEFERRED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
Control B: AUTHORIZED / IMPLEMENTED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-4a-A-CONSTRUCTION-MODELS:END -->

<!-- FW-RT6-4a-B-CONSTRUCTION-ADOPTION:BEGIN -->
## Control B — RealtimeSession construction adoption

### Additive constructor and factory surface

`RealtimeSession` and `create_realtime_session()` append one keyword-only
parameter after the accepted seven legacy parameters:

```text
config: RealtimeSessionConfig | None = None
```

The existing parameters, order, defaults, and `RealtimeSession` return type are
preserved. A supplied config cannot be combined with
`real_runtime_enabled` or any direct stage argument. Wrong config types and
ambiguous mixed inputs remain programmer errors raised as public-safe
`TypeError` values.

When config is absent, the seven legacy inputs are normalized into one immutable
`RealtimeSessionConfig`. The legacy `real_runtime_enabled=None` behavior remains
explicitly default-off.

### Construction ownership and ordering

One construction owns and fixes the following session-scoped objects:

```text
SessionId
RealtimeEventHub
RealtimeTerminalRegistry
RealtimeGenerationGate
RealtimeCapabilitySnapshot(snapshot_generation=1)
```

The construction order is:

```text
1. normalize config
2. generate SessionId
3. validate stage protocols and exact stage_kind values
4. create event hub / terminal registry / generation gate
5. call preflight() exactly once for every injected stage
6. build one immutable session capability snapshot
7. build one internal typed construction result
8. publish snapshot-derived RealtimeSessionInfo
```

Construction never calls stage `capability()`, `start()`, or `cancel()`. Stage
`close()` remains once-only session cleanup. Raw stage exceptions are not
propagated through construction status, snapshot metadata, or session info.

### Default-off mock construction

When `config.real_runtime_enabled` is false, injected stages are validated and
preflighted once but the selected runtime remains the accepted deterministic
mock runtime. The accepted mock snapshot facts remain:

```text
supports_text_chat: True
supports_voice_input: True
supports_voice_output: True
supports_motion: False
real_runtime_enabled: False
```

`RealtimeSessionInfo` derives all four support summaries, hard-cancel support,
and TTS queue-flush support from the fixed session snapshot. Injection presence
is reported separately through `injected_stage_kinds`; it is not itself a claim
that the selected runtime executes the stage.

### Explicit real-runtime composition

When real runtime is requested, each provider-neutral preflight capability is
projected only when it reports a usable real runtime. Wrong-type, unusable, or
fake-runtime capability reports are classified as safe preflight failures. Missing or failed stages receive
provider-neutral unavailable capability models with one of these safe reasons:

```text
stage_not_configured
stage_preflight_failed
```

A text-generation stage is the minimum required real composition input. Voice
input, voice output, and motion remain optional capabilities. Summary support is
derived from each projected capability's `runtime.usable` property.

The snapshot intentionally reports:

```text
real_runtime_requested: True
real_runtime_enabled: False
provider_execution_performed: False
```

Control B validates composition only. Real stage orchestration and real-request
no-fallback rejection remain Control C.

### Internal typed construction result

Control B creates one immutable internal
`RealtimeSessionConstructionResult` correlated to the session ID:

```text
default mock path:
mock_ready

real request without text-generation stage:
configuration_incomplete / missing text_generation

real request with stage preflight exception or wrong capability type:
preflight_failed / failed canonical stage kinds

real request with required stage configuration:
real_configuration_ready / runtime_executable=False
```

The public `session.construction_result` property remains deferred to Control C.
This keeps Control B additive while preparing the exact typed no-fallback guard.

### Control B verification status

```text
checkpoint: FW-RT6-4a Control B
baseline HEAD / origin/main: 0192f941e3a2009d203535ec0c97a6ceb69050ed
Control A: ACCEPTED
status: ACCEPTED / CONTROL C AUTHORIZED
Control B exact delta: 5 files
combined uncommitted Control A+B surface: 14 files
factory / constructor parameters: 8 / keyword-only
stage preflight: exactly once per injected stage
stage capability/start/cancel at construction: 0
capability snapshot generation: 1 / stable
snapshot session ID correlation: PASS
mock runtime default-off contract: PASS
focused construction tests: 25 / PASS
full unit suite: 70 / PASS
real provider execution at construction: False
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
Control C: AUTHORIZED / IMPLEMENTED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-4a-B-CONSTRUCTION-ADOPTION:END -->

<!-- FW-RT6-4a-C-RUNTIME-GUARD-ACCEPTANCE:BEGIN -->
## Control C — public construction result and no-silent-fallback guard

### Public construction result

`RealtimeSession.construction_result` exposes the immutable
`RealtimeSessionConstructionResult` created during construction. The property is
read-only, session-ID correlated, provider-neutral, and does not rebuild or probe
capabilities on access. The root-public name set remains the accepted 124 names;
Control C adds a session property rather than a new root symbol.

### Explicit real-runtime request guard

An explicit real-runtime request is never allowed to execute the deterministic
mock turn path. `run_turn()` resolves the construction status before generation
admission or any mock lifecycle emission:

```text
configuration_incomplete:
TurnOutcome.REJECTED / RealtimeErrorCode.CONFIGURATION_MISSING
reason: real_runtime_configuration_missing

preflight_failed:
TurnOutcome.REJECTED / RealtimeErrorCode.UNAVAILABLE
reason: real_runtime_preflight_failed

real_configuration_ready but orchestration unavailable:
TurnOutcome.REJECTED / RealtimeErrorCode.UNAVAILABLE
reason: real_runtime_orchestration_not_available
```

Every rejection reports `mock_runtime=False` and
`provider_execution_performed=False`. No generation is started and no stage
`capability()`, `start()`, or `cancel()` method is called. Construction-time
`preflight()` remains exactly once per injected stage.

### Terminal and lifecycle behavior

A guarded real-runtime turn commits exactly one terminal
`TurnOutcome.REJECTED` record and emits exactly one canonical
`RealtimeEventType.TURN_REJECTED` event. Duplicate submission of the same turn
returns the original terminal result without a second terminal event. After the
terminal rejection, the session returns to `idle` and remains reusable. This does
not implement FW-RT6-4b single-active-turn orchestration.

The rejection event carries the same public error code, safe message, retryable
flag, and provider-neutral metadata as the terminal result. Raw preflight
exceptions, provider names, credentials, paths, payloads, transcripts, and stage
objects are not exposed.

### Aggregate FW-RT6-4a acceptance

```text
checkpoint: FW-RT6-4a Control C
baseline HEAD / origin/main: 0192f941e3a2009d203535ec0c97a6ceb69050ed
Control A: ACCEPTED
Control B: ACCEPTED
status: IMPLEMENTED / AWAITING_REVIEW
Control C exact delta: 6 files
combined uncommitted Control A+B+C surface: 18 files
accepted task count: 7
root-public names: 124 / UNCHANGED FROM CONTROL A
construction_result public property: True
mock session creation: PASS
real-request mock fallback: False
configuration missing typed turn rejection: PASS
preflight failure typed turn rejection: PASS
real configuration without orchestration typed rejection: PASS
rejection generation start: 0
rejection stage capability/start/cancel calls: 0
focused construction tests: 35 / PASS
full unit suite: 80 / PASS
capability snapshot available: True
real provider execution at construction or guarded turn: False
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-4b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-4a-C-RUNTIME-GUARD-ACCEPTANCE:END -->
