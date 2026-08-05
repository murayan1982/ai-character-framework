# AI Character Framework v6.0.0 Current Source Gap Inventory

## FW-RT6-0a

```text
checkpoint: FW-RT6-0a
baseline head: f56697b6de066b062794ac7bb01330d2d9e91759
status: IMPLEMENTED / AWAITING_REVIEW
release baseline: v5.5.0
target release: v6.0.0
theme: Unified Realtime Character Runtime
runtime implementation: NOT_STARTED
next checkpoint: FW-RT6-0b
next checkpoint implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

This document records observable facts from the v5.5.0 source. It does not
claim that missing v6 behavior already exists.

## Source layout

```text
public SDK: framework/**
legacy/runtime-oriented code: core/**, llm/**, stt/**, tts/**, live2d/**, plugins/**
contract and release verification: scripts/smoke_*.py, scripts/check_*.py
normal unit-test directory: tests/ exists but contains no test files
```

## Confirmed foundation

The v5.5.0 source already contains provider-neutral public models and session
boundaries for text chat, voice input, voice output, realtime lifecycle, output
control, and motion. Real OpenAI STT and real VTube Studio adapter code also
exist behind explicit guards.

These pieces are not yet composed into one real unified turn runtime.

## G-01 — RealtimeSession remains a mock-safe skeleton

`framework/realtime_session.py` describes itself as a skeleton and its
`run_turn()` method emits deterministic mock stage events without executing real
STT, LLM, TTS, or motion stages.

```text
real unified turn orchestration: False
```

## G-02 — Session and turn identity are not shared across all stages

`RealtimeSession` owns a `session_id` and `RealtimeTurn` owns a `turn_id`, but
the standalone TextChat, VoiceInput, VoiceOutput, and Motion boundaries do not
share one common session/turn/generation context.

```text
stable unified generation identity: False
```

## G-03 — RealtimeEvent lacks v6 ordering fields

The current `RealtimeEvent` includes type, state, previous state, turn ID,
session ID, public error code, safe message, retryability, and public metadata.
It does not include the required v6 fields below.

```text
monotonic sequence: False
generation: False
typed payload union: False
terminal flag: False
```

## G-04 — Exactly-once terminal enforcement is absent

`RealtimeTurnResult.is_terminal` classifies terminal outcomes, but there is no
per-session terminal registry, atomic first-terminal commit, duplicate terminal
suppression, or state-regression gate.

## G-05 — Provider-neutral stale-result rejection is absent

The realtime skeleton has no generation gate for late transcript, response,
voice artifact, or motion completion. The VTube Studio implementation contains
a narrower lifecycle-generation and late-completion pattern that may inform a
future provider-neutral primitive.

## G-06 — Global capability snapshot is stale

`framework/capabilities.py` still reports schema `v5.1.capabilities` and returns
voice input, realtime, and motion as missing public boundaries even though later
public modules and guarded implementations exist.

```text
capability truthfulness across modules: False
```

## G-07 — VoiceInputSession and real STT are not normally composed

`framework/voice_input_session.py` still describes real STT as intentionally not
executed by the session skeleton. Separate OpenAI real-provider executor and
adapter modules exist. Normal host use still lacks a single provider-neutral
composition root that selects and owns the real stage.

## G-08 — Text streaming has no cancellation protocol

`llm/base.py` exposes `ask_stream()` as a synchronous generator. It does not
return a cooperative cancellation handle, provider hard-cancel capability, or
typed stream cleanup result.

## G-09 — Voice generation, queue, and playback responsibilities are split

The public voice-output boundary performs per-request artifact generation. The
legacy `tts/voice_engine.py` owns provider-specific synthesis, queueing, local
playback, and temporary files. `RealtimeSession` does not own a provider-neutral
bounded voice-output work queue.

## G-10 — Voice artifact handoff has a path-contract mismatch

`VoiceArtifactRef` rejects local/private path-looking identifiers, but the real
voice-output provider adapter currently assigns `str(artifact_path)` to
`audio_artifact_ref`. v6 requires an opaque Framework-owned artifact store and
resolver contract.

## G-11 — VoiceOutputSession contains repeated compatibility overrides

The current class defines `close`, `is_closed`, `create_output`, and `speak`
more than once. The effective behavior depends on later method overrides rather
than one clear lifecycle implementation.

## G-12 — Public text-chat error events may include raw exception text

The text-chat streaming boundary includes exception-derived text/type in an
app-facing event. v6 requires stable safe error classification without raw
provider exception exposure.

## G-13 — Metadata redaction helpers are shallow and duplicated

Multiple modules implement separate shallow redaction helpers. Nested mappings,
collections, or objects are not covered by one recursive public-safe utility.

## G-14 — Installable SDK and resource-root contract are incomplete

The source does not contain `pyproject.toml`. Existing smoke scripts add the
repository root to `sys.path`, and parts of the runtime resolve presets,
characters, output, or temporary resources relative to a checkout/CWD.

## G-15 — Legacy runtime and public SDK coexist without a composition layer

`core/pipeline.py` contains real streaming, interruption checks, TTS waits, and
emotion handling. It is not the implementation behind the public
`RealtimeSession`. v6 must extract provider-neutral stage protocols instead of
exposing legacy internals.

## G-16 — Verification is concentrated in release smoke scripts

The source includes many versioned smoke/check scripts, while `tests/` contains
no normal unit tests. Deterministic race, duplicate terminal, stale result, and
fake-clock behavior need a fast unit-test layer.

## G-17 — Version and schema values are distributed

Public types expose several historical version strings (`4.0`, `5.2.0`,
`v5.lazy_provider_adapter`, `v5.1.capabilities`, and `5.5.0`). v6 needs a
central package version and separately versioned public schemas.

## Baseline verification outcome

```text
compileall framework/core/llm/stt/tts/scripts: REQUIRED
v5.2 realtime and output-control smokes: REQUIRED
v5.3 VoiceInputSession adapter smoke: REQUIRED
v5.4 OpenAI real-provider source-safe smoke: REQUIRED
v5.5 MotionSession real-adapter composition smoke: REQUIRED
legacy smoke_public_facade current-surface sync: KNOWN_GAP
```

## Scope lock

FW-RT6-0a is an exact six-file docs/test-only checkpoint.

```text
README.md
docs/roadmap_feature_v6.0.0.md
docs/v600_current_source_gap_inventory.md
docs/v600_tasklist.md
scripts/smoke_v600_current_source_gap_inventory.py
scripts/check_v600_tasklist_contract.py
```

Protected runtime and configuration surfaces must not change in this checkpoint.

```text
framework/**: NO CHANGE
core/**: NO CHANGE
llm/**: NO CHANGE
stt/**: NO CHANGE
tts/**: NO CHANGE
live2d/**: NO CHANGE
plugins/**: NO CHANGE
registry/**: NO CHANGE
config/**: NO CHANGE
presets/**: NO CHANGE
characters/**: NO CHANGE
requirements.txt: NO CHANGE
.env.example: NO CHANGE
release/**: NO CHANGE
```

No network, provider, microphone, playback, private configuration, private
evidence, application repository access, commit, push, tag, or publication is
authorized by this checkpoint.

<!-- FW-RT6-0b-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-0b public SDK hygiene resolution sync

This sync records the result of Controls A through C against the original
FW-RT6-0a inventory. Historical source observations above remain preserved.

```text
baseline head: 136be27c9f6fe62b7753c64f4fed02ae94f98da9
legacy smoke_public_facade expected-surface drift: RESOLVED
framework.__all__ fragmented construction: RESOLVED
provider-specific compatibility exports: PRESERVED / LAZY
G-11 repeated VoiceOutputSession compatibility overrides: RESOLVED
G-17 distributed version/schema literal definitions: RESOLVED
G-14 installable SDK/resource-root contract: UNRESOLVED / FW-RT6-0c
G-16 normal unit-test architecture: UNRESOLVED / FW-RT6-3c
capability truthfulness across modules: UNRESOLVED / FW-RT6-1d
unified realtime orchestration: UNRESOLVED
```

G-17 resolution means the existing compatibility values now come from one
central module; it does not mean every historical API/schema value was changed
to `6.0.0`. G-16 remains open because release smokes were strengthened, but a
normal deterministic unit-test layer is still absent.
<!-- FW-RT6-0b-D-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-0c-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-0c installable SDK gap resolution sync

This sync records the accepted public-SDK portion of G-14 while preserving the
historical source observations above.

```text
baseline head: cf9949579d971de68b2b763928f1c8052cf49921
G-14 installable SDK/package metadata: RESOLVED
G-14 preset/character public CWD dependency: RESOLVED
G-14 public VoiceOutput artifact CWD dependency: RESOLVED
G-14 public example sys.path bootstrap: RESOLVED
editable install outside checkout: VERIFIED
wheel install outside checkout: VERIFIED
public resource lookup outside CWD: VERIFIED
legacy main.py/runtime CWD-relative paths: UNRESOLVED / OUT OF FW-RT6-0c SCOPE
G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
capability truthfulness across modules: UNRESOLVED / FW-RT6-1d
unified realtime orchestration: UNRESOLVED
```

G-14 is resolved for the installable public SDK boundary only. The legacy
interactive runtime remains intentionally outside this checkpoint, and v6.0.0
is not released by this sync.
<!-- FW-RT6-0c-D-GAP-RESOLUTION-SYNC:END -->


<!-- FW-RT6-1a-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-1a public identity gap resolution sync

This sync records the accepted identity foundation while preserving the
remaining all-stage correlation and realtime-ordering gaps.

```text
baseline head: 9d955955d4462006ed8aacc8e4c6e43ae487fb35
G-02 common public identity primitives: RESOLVED
G-02 Framework-generated Realtime SessionId: RESOLVED
G-02 Framework-generated Realtime TurnId: RESOLVED
G-02 Framework-generated Motion SessionId: RESOLVED
G-02 provider ID / Framework ID separation: RESOLVED
G-02 TextChat result correlation wiring: UNRESOLVED / LATER STAGE INTEGRATION
G-02 VoiceInput result correlation wiring: UNRESOLVED / LATER STAGE INTEGRATION
G-02 VoiceOutput result correlation wiring: UNRESOLVED / LATER STAGE INTEGRATION
G-02 Motion turn/generation correlation: UNRESOLVED / LATER STAGE INTEGRATION
stable unified generation runtime identity: UNRESOLVED
all-stage shared correlation context: UNRESOLVED
G-03 RealtimeEvent sequence: UNRESOLVED / FW-RT6-1c
G-03 RealtimeEvent generation: UNRESOLVED / FW-RT6-1c
G-03 typed payload / terminal flag: UNRESOLVED / FW-RT6-1c
phase/outcome/recovery separation: UNRESOLVED / FW-RT6-1b
capability truthfulness across modules: UNRESOLVED / FW-RT6-1d
unified realtime orchestration: UNRESOLVED
```

FW-RT6-1a resolves the common identity vocabulary and the Framework-generated
Realtime/Motion adoption paths. It does not claim that Text, VoiceInput,
VoiceOutput, and Motion already share one runtime-owned generation context.
<!-- FW-RT6-1a-D-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-1b-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-1b lifecycle foundation gap resolution sync

This sync records the accepted phase, terminal outcome, and recovery foundation
while preserving the remaining ordered-event, exactly-once, stale-result,
capability, and orchestration gaps.

```text
baseline head: 8bc71a990762c8161d262bc7617a44e0dfb2c8e3
common RealtimePhase model: RESOLVED
common TurnOutcome model: RESOLVED
common RecoveryAction model: RESOLVED
rejected/cancelled/interrupted semantics: RESOLVED
RealtimeTurnResult canonical terminal outcome: RESOLVED
RealtimeTurnResult normalized recovery action: RESOLVED
RealtimeSession canonical phase: RESOLVED
RealtimeSessionInfo canonical phase: RESOLVED
RealtimeTurn canonical phase: RESOLVED
phase transition matrix: RESOLVED
invalid transition typed failure: RESOLVED
terminal duplicate/regression validation primitive: RESOLVED
G-04 per-session terminal registry: UNRESOLVED
G-04 atomic first-terminal commit: UNRESOLVED
G-04 duplicate terminal result/event suppression: UNRESOLVED
G-04 exactly-once terminal enforcement: UNRESOLVED
G-03 RealtimeEvent sequence: UNRESOLVED / FW-RT6-1c
G-03 RealtimeEvent generation: UNRESOLVED / FW-RT6-1c
G-03 RealtimeEvent terminal flag: UNRESOLVED / FW-RT6-1c
G-03 typed payload union: UNRESOLVED / FW-RT6-1c
G-05 stale-result rejection: UNRESOLVED
G-06 capability truthfulness: UNRESOLVED / FW-RT6-1d
G-01 real unified turn orchestration: UNRESOLVED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-1c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

The terminal transition validator establishes the meaning of first, duplicate,
and regressive terminal attempts. It is not a per-session registry and does not
provide atomic exactly-once result or event commitment.
<!-- FW-RT6-1b-D-GAP-RESOLUTION-SYNC:END -->
