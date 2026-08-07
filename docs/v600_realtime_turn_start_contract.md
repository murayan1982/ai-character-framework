# FW-RT6-4b Single-active-turn Lifecycle Contract

This document fixes Control A of the provider-neutral single-active-turn
lifecycle for AI Character Framework v6.0.0.

<!-- FW-RT6-4b-A-TURN-START-MODELS:BEGIN -->
## Control A — public start/result identity models

### Baseline

```text
baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

FW-RT6-4a:
COMPLETED / VERIFIED / COMMITTED / PUSHED / ACCEPTED / CLOSED

FW-RT6-4b:
EXACT_CONTRACT_REVIEW COMPLETED
```

### Additive public surface

Control A appends exactly one root-public name after the accepted 124-name
FW-RT6-4a surface:

```text
RealtimeTurnStartResult
```

The canonical root-public count is therefore 125.

`RealtimeTurnStartResult` is immutable, provider-neutral, and carries:

```text
accepted
session_id
turn_id
generation_id
phase
terminal_result
public_metadata
```

Accepted admission requires one generation and cannot contain a terminal result.
Rejected-before-admission has no generation and requires one correlated
`TurnOutcome.REJECTED` terminal result for the same session and turn.

### RealtimeTurnResult identity extension

`RealtimeTurnResult` gains additive optional identity fields:

```text
session_id
generation_id
```

Existing construction remains source compatible. A generation identity cannot be
reported without a session identity. Class factories accept the two identities
as additive keyword-only arguments.

Control A does not yet require current `RealtimeSession.run_turn()` results to
populate these identities. Runtime population belongs to Controls B/C.

### Deferred runtime boundaries

```text
RealtimeSession.start_turn():
DEFERRED / Control B

structured active-turn context:
DEFERRED / Control B

active-turn typed rejection:
DEFERRED / Control B

automatic previous-turn replacement prohibition:
DEFERRED / Control B

run_turn() start_turn adoption:
DEFERRED / Control C

normal terminal identity population:
DEFERRED / Control C

idle/reusable cleanup:
DEFERRED / Control C
```

No provider, network, microphone, playback, or real VTS execution is introduced
by Control A.

### Control A status

```text
checkpoint:
FW-RT6-4b Control A

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
11 files including FW-RT6-4a closure sync

root-public names:
125

focused tests:
10 / PASS expected

full unit suite:
90 / PASS expected

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4b-A-TURN-START-MODELS:END -->

<!-- FW-RT6-4b-B-TURN-START-ADOPTION:BEGIN -->
## Control B — explicit start and single-active admission

### Accepted Control A baseline

```text
Control A:
ACCEPTED

root-public names:
125

RealtimeTurnStartResult:
PUBLIC / IMMUTABLE

RealtimeTurnResult identity fields:
session_id / generation_id
```

### Explicit `RealtimeSession.start_turn()`

Control B adds the synchronous provider-neutral public admission method:

```text
start_turn(
    turn=None,
    *,
    input_text="",
    public_metadata=None,
) -> RealtimeTurnStartResult
```

The method admits one turn but does not execute voice input, text generation,
voice output, motion, provider, network, microphone, playback, or VTS work.
Successful admission allocates exactly one Framework `GenerationId`, binds one
internal `_ActiveTurnContext`, transitions the session from `idle` to
`listening`, and emits exactly one canonical `TURN_STARTED` event correlated by
session, turn, and generation identity.

A repeated start of the same already-active turn is idempotent: it returns the
same accepted generation without allocating another generation or emitting a
second `TURN_STARTED` event.

### Structured active-turn context

Control B adds one immutable internal context:

```text
_ActiveTurnContext:
turn
generation_id
```

The explicit-start context is session-owned. The existing `_active_turn_id` and
`_active_generation_id` fields remain compatibility mirrors during the staged
Control B implementation because existing generation/interrupt smoke contracts
still inspect them. Control C will make `run_turn()` use the same explicit-start
path and complete the internal consolidation.

### Atomic single-active admission

One session-owned `_turn_admission_lock` serializes explicit admission attempts.
Before a new generation is allocated, `start_turn()` checks the explicit context,
the generation gate's current identity, and the compatibility active identity.
An active turn therefore prevents the explicit-start path from calling
`RealtimeGenerationGate.start_generation()` for a different turn.

The underlying generation-gate primitive retains its historical replacement
behavior for internal compatibility. Control B enforces the public no-replacement
contract at session admission instead of changing that lower-level primitive.

### Active-turn rejection

A different turn submitted while one turn is active returns:

```text
accepted:
False

terminal outcome:
rejected

public error code:
rejected

reason:
active_turn_exists

generation allocated to rejected turn:
False

automatic previous-turn replacement:
False
```

The rejected turn owns one terminal-registry record and exactly one
`TURN_REJECTED` event. That event is emitted through a dedicated state-neutral
path: the active session state and phase are observed but never changed, the
active generation is not advanced, and the rejection event has no generation
identity. Submitting the same rejected turn again returns the original terminal
result without a second terminal event.

### Additional admission safety

A turn explicitly bound to another session is rejected before generation
allocation with `INVALID_REQUEST`. A closed session returns a typed
`SESSION_CLOSED` admission result without reopening the closed event hub.

An explicit real-runtime request that is not executable continues to use the
accepted FW-RT6-4a no-silent-fallback rejection path. Its terminal result now
carries the session identity required by `RealtimeTurnStartResult`; no generation
is allocated and no mock turn runs.

### Deferred Control C boundaries

Control B intentionally does not rewrite the existing synchronous `run_turn()`
mock execution path. Therefore these remain Control C:

```text
run_turn() -> start_turn() adoption
normal completed result session/generation population
normal terminal exactly-once acceptance through the explicit context
active-context cleanup on normal completion through the unified path
idle/reusable aggregate acceptance
FW-RT6-4b task checkbox completion
```

Legacy `run_turn()` remains source-compatible and its normal completed result
continues to leave the new optional session/generation identity fields unset
until Control C.

### Control B verification status

```text
checkpoint:
FW-RT6-4b Control B

baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

Control A:
ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

Control B exact delta:
5 files

combined uncommitted Control A+B surface:
14 files

root-public names:
125 / UNCHANGED FROM CONTROL A

explicit start generation allocation:
1 per accepted turn

same-turn repeated start:
idempotent / no second generation

active new-turn rejection:
typed / state-neutral

rejected-turn generation allocation:
0

active-generation retirement on rejection:
0

focused Control A+B tests:
24 / PASS expected

full unit suite:
104 / PASS expected

provider / network / microphone / playback / real VTS execution:
False

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4b-B-TURN-START-ADOPTION:END -->
<!-- FW-RT6-4b-C-TURN-LIFECYCLE-ACCEPTANCE:BEGIN -->
## Control C — unified run-turn lifecycle and aggregate acceptance

### Accepted Control B baseline

```text
Control A:
ACCEPTED

Control B:
ACCEPTED

combined Control A+B surface:
14 files
```

### Unified `run_turn()` admission

`run_turn()` now normalizes the public turn request and performs explicit
`start_turn()` admission before entering the serialized execution boundary.
This ordering is required for the single-active-turn concurrency policy: a
different turn submitted while another turn is active is rejected immediately
instead of waiting for the earlier synchronous execution to finish and then
implicitly replacing it.

An accepted `run_turn()` never allocates a second legacy generation. It executes
the generation returned by `start_turn()`. If the same turn was already
explicitly started, the idempotent start result is reused and no second
`TURN_STARTED` event is emitted.

### Normal terminal identity and exactly-once ownership

A normally completed admitted turn returns a `RealtimeTurnResult` containing:

```text
session_id == RealtimeSessionInfo.session_id
turn_id == admitted turn_id
generation_id == admitted generation_id
```

The same identity is carried by the terminal `TURN_COMPLETED` event. Normal
completion is committed through the session-owned terminal registry exactly
once. Repeating `run_turn()` with an already-completed turn returns the original
terminal result, does not start a second generation, and does not emit another
terminal event.

### Active context cleanup and reuse

After the first normal terminal commit, the admitted generation is retired with
`turn_terminal`, the matching `_ActiveTurnContext` and compatibility mirrors are
cleared, and the session returns to:

```text
state: idle
phase: idle
```

The next turn can then be admitted with a fresh turn and generation identity.
Automatic previous-turn replacement remains false.

### Rejection and closed paths

Active different-turn rejection remains state-neutral and carries no generation.
Foreign-session `run_turn()` uses the typed `INVALID_REQUEST` admission result.
Closed-session `run_turn()` returns a session-bound `SESSION_CLOSED` result with
no generation. The FW-RT6-4a explicit-real-runtime no-silent-mock-fallback
contract remains unchanged and its rejection result carries session identity
without allocating a generation.

### Aggregate acceptance

```text
checkpoint:
FW-RT6-4b Control C / aggregate acceptance

status:
IMPLEMENTED / AWAITING_REVIEW

Control C exact delta:
7 files

combined Control A+B+C surface:
16 files

root-public names:
125 / UNCHANGED

focused Control A+B+C tests:
36 / PASS expected

full unit suite:
116 / PASS expected

single active turn:
PASS

new turn while active:
typed rejection

normal turn:
exactly one terminal

session reusable:
True

provider / network / microphone / playback / real VTS execution:
False

next checkpoint:
FW-RT6-4c / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4b-C-TURN-LIFECYCLE-ACCEPTANCE:END -->

<!-- FW-RT6-4b-D-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-4b aggregate acceptance sync

```text
checkpoint:
FW-RT6-4b

status:
COMPLETED / VERIFIED / ACCEPTED

accepted combined surface:
16 files

focused Control A+B+C tests:
36 / PASS

full unit suite at acceptance:
116 / PASS

single active turn:
PASS

new turn while active:
typed / state-neutral rejection

normal terminal:
exactly one

session reusable:
True

active generation replacement:
0

root-public names at FW-RT6-4b acceptance:
125

provider / network / microphone / playback / real VTS execution:
False

next checkpoint:
FW-RT6-4c

next checkpoint status:
EXACT_CONTRACT_REVIEW COMPLETED / CONTROL A AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

This acceptance sync supersedes only the aggregate checkpoint status. Earlier
Control A/B/C status blocks remain historical records of their pre-acceptance
states.
<!-- FW-RT6-4b-D-ACCEPTANCE-SYNC:END -->
