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

<!-- FW-RT6-1c-E-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-1c ordered realtime event gap resolution sync

This sync records the accepted public ordered-event foundation while preserving
the remaining exactly-once, stale-result, queue, capability, and real-runtime
gaps.

```text
baseline head: 80e5c550bbb994bc8dfc3340340691c881f0449d
G-03 typed payload model vocabulary: RESOLVED
G-03 canonical RealtimeEvent v6 envelope: RESOLVED
G-03 RealtimeEvent sequence field: RESOLVED
G-03 RealtimeEvent generation field: RESOLVED
G-03 RealtimeEvent terminal flag: RESOLVED
G-03 timestamp / monotonic timestamp fields: RESOLVED
G-03 partial/final transcript public distinction: RESOLVED
G-03 response started/delta/completed public distinction: RESOLVED
G-03 synthesis/audio/stale/overflow public categories: RESOLVED
G-03 explicit v5 event projection: RESOLVED
G-03 RealtimeSession canonical ordered callback: RESOLVED
G-03 RealtimeSession legacy mapped callback: RESOLVED
G-03 session-lifetime EventSequence allocation: RESOLVED
G-03 per-admitted-turn GenerationId allocation: RESOLVED
all-stage shared correlation context: UNRESOLVED / LATER STAGE INTEGRATION
provider partial transcript runtime callback: UNRESOLVED / LATER STAGE INTEGRATION
provider response delta runtime callback: UNRESOLVED / LATER STAGE INTEGRATION
G-04 per-session terminal registry: UNRESOLVED
G-04 atomic first-terminal commit: UNRESOLVED
G-04 duplicate terminal result/event suppression: UNRESOLVED
G-04 exactly-once terminal enforcement: UNRESOLVED
G-05 automatic stale-result rejection: UNRESOLVED
bounded event queue / overflow runtime: UNRESOLVED
G-06 capability truthfulness: UNRESOLVED / FW-RT6-1d
G-01 real unified turn orchestration: UNRESOLVED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-1d
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

G-03 is resolved for the public model and mock-safe `RealtimeSession` emission
boundary. This does not imply real STT/LLM/TTS/motion composition, provider
partial/delta delivery, stale-result enforcement, or bounded queue behavior.
<!-- FW-RT6-1c-E-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-1d-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-1d detailed capability snapshot gap resolution sync

This sync records the accepted public capability model, global aggregation, and
session-scoped adoption while preserving the remaining real-runtime composition
work.

```text
baseline head: 753748d463f800647b251c788d217a5c5adc4049
G-06 stale global capability summary: RESOLVED
G-06 global/session capability mismatch: RESOLVED FOR CURRENT PUBLIC BOUNDARIES
G-06 configured/runtime_available/guarded separation: RESOLVED
G-06 fake runtime/real runtime separation: RESOLVED
G-06 cooperative cancel/provider hard cancel distinction: RESOLVED
G-06 snapshot scope/generation: RESOLVED
G-06 v5 summary compatibility fields: PRESERVED
voice input current public status: ACCURATE
realtime current public status: ACCURATE
motion current public status: ACCURATE
unsupported capability overclaim: False
G-07 normal real STT session composition: UNRESOLVED / FW-RT6-7a+
G-01 real unified turn orchestration: UNRESOLVED
G-04 per-session terminal registry/exactly-once enforcement: UNRESOLVED
G-05 automatic stale-result rejection: UNRESOLVED
bounded event queue / overflow runtime: UNRESOLVED
provider hard cancellation: UNRESOLVED
motion wired into RealtimeSession: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

The global snapshot reports standalone mock-safe public boundaries. The session
snapshot reports only the stages actually wired into the current
`RealtimeSession`. A host request for real runtime remains intent metadata and
does not become a runtime-availability claim.
<!-- FW-RT6-1d-D-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-2a-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-2a recursive public-safety gap resolution sync

This sync records the accepted recursive public-safety foundation and the
TextChat error-boundary correction while preserving remaining incremental
consumer migration and unrelated runtime gaps.

```text
baseline head: 888d689fcf894fa7fa83eb6d0daa18b41f77726a
G-12 TextChat raw exception string event exposure: RESOLVED
G-12 TextChat exception class-name event exposure: RESOLVED
G-12 shared safe classifier for ask_result / ask_stream: RESOLVED
G-13 common recursive public-safety utility: RESOLVED
G-13 centralized secret-like key policy: RESOLVED
G-13 five core compatibility-helper implementations: DELEGATED / RESOLVED
G-13 nested mapping/list/tuple/dataclass sanitization: RESOLVED
G-13 all repository metadata consumers migrated: False / INCREMENTAL FOLLOW-UP
nested credential redaction: PASS
raw exception exposed by accepted boundaries: False
private path exposed by accepted boundaries: False
root-public names: 121 / UNCHANGED
G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
G-01 real unified turn orchestration: UNRESOLVED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

FW-RT6-2a completes the common utility, first-wave core consumer migration, and
TextChat public-error correction. It does not claim repository-wide replacement
of every legacy metadata helper or real provider/runtime execution.
<!-- FW-RT6-2a-D-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-2b-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-2b realtime event-hub gap resolution sync

This sync records the accepted event sequencing, subscriber-safety, bounded
history, overflow, operation-order, and close-boundary behavior while preserving
the terminal-registry, stale-result, real-runtime, and normal unit-test gaps.

```text
baseline head: d12e562a0c0b0111386776d50286b1a4cbdf54d2
G-03 session-local monotonic event sequencing: RESOLVED
G-03 callback registration/unregistration token: RESOLVED
G-03 callback exception isolation: RESOLVED
G-03 slow subscriber policy: RESOLVED / SYNCHRONOUS SERIALIZED RETAIN-AND-ACCOUNT
G-03 bounded canonical event history: RESOLVED / LIMIT 64
G-03 non-silent typed overflow diagnostics: RESOLVED
G-03 EVENT_OVERFLOW legacy v5 projection: NONE / INTENTIONAL
G-03 concurrent/reentrant event emission serialization: RESOLVED
G-03 concurrent operation event-group serialization: RESOLVED
G-03 close-boundary event rejection: RESOLVED
SESSION_CLOSED exactly once: RESOLVED
event hub sealed after close: RESOLVED
post-close active event: False
asynchronous per-subscriber delivery queue: NOT CLAIMED / NOT IMPLEMENTED
background callback worker: False
automatic subscriber timeout/eviction: False
root-public names: 121 / UNCHANGED
G-04 per-session terminal registry: UNRESOLVED / FW-RT6-2c
G-04 atomic first-terminal commit: UNRESOLVED / FW-RT6-2c
G-04 duplicate terminal suppression: UNRESOLVED / FW-RT6-2c
G-05 generation stale-result rejection: UNRESOLVED / FW-RT6-2d
G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
G-01 real unified turn orchestration: UNRESOLVED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

The bounded structure accepted here is canonical event history, not an
asynchronous delivery queue. Synchronous serialized delivery is the fixed
subscriber policy for this checkpoint.
<!-- FW-RT6-2b-D-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-2c-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-2c realtime terminal-registry gap resolution sync

This sync records the accepted exactly-once terminal primitive and current
`RealtimeSession` integration while preserving generation stale-result,
provider-driven orchestration, real-runtime, and normal unit-test gaps.

```text
baseline head: 8393c82a312af73f0b18db106b6e32c959f251a2
G-04 per-session terminal registry: RESOLVED
G-04 atomic first-terminal ownership: RESOLVED
G-04 duplicate terminal suppression: RESOLVED
G-04 terminal regression suppression: RESOLVED
G-04 late non-terminal admission rejection: RESOLVED
G-04 terminal reason/result retention: RESOLVED
G-04 read-only result/diagnostic observability: RESOLVED
G-04 same-turn concurrent integration race: RESOLVED
G-04 reentrant post-terminal mutation rejection: RESOLVED
current verified RealtimeSession first-terminal path: TURN_COMPLETED
all provider-driven terminal paths wired: False / NOT CLAIMED
one terminal event per current completed turn: PASS
same-turn concurrent lifecycle groups: 1
same-turn terminal events: 1
same-turn terminal records: 1
terminal callback late events: 0
root-public names: 121 / UNCHANGED
event_diagnostics keys changed: False
G-05 generation stale-result rejection: UNRESOLVED / FW-RT6-2d
STALE_RESULT_DROPPED runtime use: NOT IMPLEMENTED
old response delta suppression: UNRESOLVED
old TTS artifact suppression: UNRESOLVED
close後provider completion suppression: UNRESOLVED
G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
G-01 real unified turn orchestration: UNRESOLVED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2d
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

FW-RT6-2c closes G-04 for the accepted primitive and current mock completed-turn
integration. It does not claim generation-based late completion rejection or
provider-driven terminal orchestration.
<!-- FW-RT6-2c-D-GAP-RESOLUTION-SYNC:END -->


<!-- FW-RT6-2d-D-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-2d realtime generation-gate gap resolution sync

This sync records the accepted provider-neutral generation freshness primitive,
current `RealtimeSession` completion ingress, race behavior, and VTube Studio
semantic alignment while preserving the stage-protocol, lifecycle,
provider-composition, and normal unit-test gaps.

```text
baseline head: aee53d77840f49450d9319a1ff5208cec7471757
G-05 current generation registry: RESOLVED
G-05 generation retirement reason registry: RESOLVED
G-05 stage completion generation envelope: RESOLVED
G-05 central stale completion decision: RESOLVED
G-05 typed stale drop reason: RESOLVED
G-05 open-session STALE_RESULT_DROPPED observability: RESOLVED
G-05 stale diagnostic v5 projection: NONE / INTENTIONAL
G-05 close-requested stale event delivery: SUPPRESSED / COUNT-ONLY OBSERVABLE
G-05 post-close stale event delivery: SUPPRESSED / COUNT-ONLY OBSERVABLE
old response delta delivery through accepted ingress: False
old TTS artifact delivery through accepted ingress: False
interrupt / cancel late audio delivery through accepted ingress: False
close-requested / post-close completion delivery through accepted ingress: False
VTS lifecycle-generation semantic alignment: VERIFIED / IN-MEMORY FAKE
VTS source changed by Control D: False
terminal callback late interrupt / cancel events: 0
terminal callback state / phase / history mutation: False
normal post-turn no-active interrupt behavior: PRESERVED
public RealtimeSession reset method: NOT ADDED
all real provider-driven stage paths wired: False / NOT CLAIMED
single-active-turn lifecycle enforcement: UNRESOLVED / LATER CHECKPOINT
stage protocols and public stage context: UNRESOLVED / FW-RT6-3a
G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
G-01 real unified turn orchestration: UNRESOLVED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-3a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

G-05 is resolved for the accepted generation gate and the current central
completion-ingress boundary. This does not imply that future real STT, LLM,
TTS, or motion callbacks are already wired through that boundary.
<!-- FW-RT6-2d-D-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-3a-C-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-3a realtime stage-protocol gap resolution sync

This sync records the accepted provider-neutral stage vocabulary and injection
boundary while preserving legacy adapter migration, real orchestration,
deterministic fake-controller, and normal unit-test gaps.

```text
baseline head: 8db6a4ff1c9687b9e9d04b2f55a38611e27e0a5e
G-15 stable provider-neutral stage package: RESOLVED
G-15 VoiceInputStage protocol: RESOLVED
G-15 TextGenerationStage protocol: RESOLVED
G-15 VoiceOutputStage protocol: RESOLVED
G-15 MotionStage protocol: RESOLVED
G-15 common preflight/capability/start/cancel/close vocabulary: RESOLVED
G-15 public session/turn/generation stage context: RESOLVED
G-15 provider-specific public protocol objects: EXCLUDED / RESOLVED
G-15 RealtimeSession provider-neutral injection boundary: RESOLVED
G-15 fake stage injection: PASS
G-15 real legacy runtime adapter migration: UNRESOLVED / LATER CHECKPOINT
G-15 injected-stage run_turn execution: 0 / DEFERRED
G-15 preflight/capability runtime composition: NOT EXECUTED / DEFERRED
G-15 cancellation coordination across injected stages: UNRESOLVED
G-01 real unified turn orchestration: UNRESOLVED
G-16 deterministic fake runtime controller: UNRESOLVED / FW-RT6-3b
G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
factory parameters: 7 / KEYWORD-ONLY
root-public names: 121 / UNCHANGED
provider SDK root import: False
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-3b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

FW-RT6-3a resolves the missing public composition boundary. It does not claim
that legacy provider adapters have been migrated or that a real provider-driven
turn is orchestrated by `RealtimeSession`.
<!-- FW-RT6-3a-C-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-3b-C-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-3b deterministic fake-runtime gap resolution sync

This sync records the accepted deterministic race/fault controller and its
actual generation-gate/terminal-registry adoption while preserving event-hub
trace projection, normal unit-test architecture, real adapters, and unified
production orchestration as later work.

```text
baseline head: 5a565afbb19e81f55d35e89486c2327a47d87ab5
Control A deterministic fake runtime controller: ACCEPTED
Control B generation-gate / terminal-registry adoption: ACCEPTED
G-16 deterministic fake runtime controller: RESOLVED
G-16 fake clock / scheduler: RESOLVED
G-16 stage pause / resume: RESOLVED
G-16 artificial delay: RESOLVED
G-16 late completion injection: RESOLVED
G-16 duplicate terminal injection: RESOLVED
G-16 cancellation timeout injection: RESOLVED
G-16 queue overflow injection: RESOLVED
G-16 deterministic event trace assertion helper: RESOLVED
G-16 actual generation-gate deterministic adoption: RESOLVED
G-16 actual terminal-registry deterministic adoption: RESOLVED
G-16 race reproducible: True
G-16 event-hub trace projection: UNRESOLVED / LATER CHECKPOINT
G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
G-15 real legacy runtime adapter migration: UNRESOLVED / LATER CHECKPOINT
G-01 real unified turn orchestration: UNRESOLVED
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
event-hub trace projection: DEFERRED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-3c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

FW-RT6-3b resolves deterministic provider-free race reproduction. It does not
claim normal unit-test placement, real provider execution, or production stage
orchestration.
<!-- FW-RT6-3b-C-GAP-RESOLUTION-SYNC:END -->

<!-- FW-RT6-3c-C-GAP-RESOLUTION-SYNC:BEGIN -->
## FW-RT6-3c normal runtime unit-test gap resolution sync

This sync records the accepted normal `tests/` architecture and its provider-free
coverage while preserving production orchestration, real adapters, event-hub
trace projection, and release work as later checkpoints.

```text
baseline head: e368a3db3e1ae6160d6a3c3f01929eb6f256c57a
Control A unit-test foundation: ACCEPTED
Control B runtime primitive coverage: ACCEPTED
G-16 non-empty normal tests directory: RESOLVED
G-16 stdlib unittest runner: RESOLVED
G-16 identity/model unit tests: RESOLVED
G-16 lifecycle transition unit tests: RESOLVED
G-16 terminal registry unit tests: RESOLVED
G-16 generation/stale-completion unit tests: RESOLVED
G-16 subscriber/event-hub unit tests: RESOLVED
G-16 deterministic fake-runtime unit tests: RESOLVED
G-16 smoke/check separation as aggregate/release gates: RESOLVED
G-16 normal deterministic unit-test architecture: RESOLVED
G-16 tests directory non-empty: True
G-16 unit tests network-free: True
G-16 full unit suite: 45 / PASS
G-16 event-hub trace projection: UNRESOLVED / LATER CHECKPOINT
G-15 real legacy runtime adapter migration: UNRESOLVED / LATER CHECKPOINT
G-01 real unified turn orchestration: UNRESOLVED
production runtime source changed: False
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-4a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
```

FW-RT6-3c resolves the missing fast normal unit-test layer. It does not claim
that real provider adapters are composed or that `RealtimeSession.run_turn()`
executes the unified production stage chain.
<!-- FW-RT6-3c-C-GAP-RESOLUTION-SYNC:END -->
