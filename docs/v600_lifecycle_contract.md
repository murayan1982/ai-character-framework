# v6.0.0 Public Lifecycle Contract

<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:BEGIN -->
## FW-RT6-1b Control A — phase, terminal outcome, and recovery primitives

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Baseline:

```text
c89ca5f0ae186564a8f7bced2ea7ce1462459172
```

Control A defines five provider-neutral root-public lifecycle types while
leaving the existing realtime runtime and v5-compatible `RealtimeState`
behavior unchanged.

```text
RealtimePhase
TurnOutcome
RecoveryAction
LifecycleTransitionErrorCode
LifecycleTransitionError
```

The existing 99 root-public names remain in the same order. The five lifecycle
names are appended, producing 104 canonical root-public names.

## Transient phase

`RealtimePhase` contains only non-terminal progress:

```text
idle
listening
transcribing
thinking
speaking
motion
recovering
```

Completion, interruption, cancellation, rejection, failure, and closure are not
phases. Session closure is represented by the session lifecycle boundary; a
closed session has no canonical active phase.

## Terminal turn outcome

```text
completed   admitted turn completed normally
rejected    turn did not acquire active ownership
cancelled   admitted turn ended by an explicit host/session cancel request
interrupted admitted turn ended by barge-in or asynchronous interrupt
failed      admitted turn ended by a stage/runtime failure
closed      session close prevented or terminated turn processing
```

`cancelled` and `interrupted` are intentionally distinct.

## Recovery action

```text
none
reuse_session
reset_turn
reset_session
reconnect
close_session
permanent_failure
```

The value describes the next safe host/runtime action; it does not claim that a
provider hard cancel, reconnect, reset, or close has already completed.

## Phase transition matrix

Repeating the current phase is an idempotent no-op.

```text
idle         -> listening / transcribing / thinking / speaking / motion
listening    -> transcribing / thinking / recovering / idle
transcribing -> thinking / recovering / idle
thinking     -> speaking / motion / recovering / idle
speaking     -> motion / recovering / idle
motion       -> speaking / recovering / idle
recovering   -> idle
```

Invalid transitions raise `LifecycleTransitionError` with code
`invalid_phase_transition`.

## Terminal validation

The internal validation primitive accepts a first terminal outcome. Repeating
that terminal raises `duplicate_terminal`; attempting a different terminal
afterward raises `terminal_regression`. This control does not add a terminal
registry, atomic terminal commit, or duplicate-event suppression runtime.

## Public-safe transition error

`LifecycleTransitionError` derives from `ValueError` and exposes only:

```text
code
from_phase
to_phase
existing_outcome
attempted_outcome
safe_message
```

It does not retain provider payloads, raw provider exceptions, credentials,
paths, transcripts, or application data.

## Compatibility and deferrals

```text
RealtimeState removed or reordered: False
RealtimeTurnResult outcome adoption: Control B
RealtimeSession phase adoption: Control C
RealtimeEvent sequence/generation/terminal fields: FW-RT6-1c
terminal registry / exactly-once suppression: NOT IMPLEMENTED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next control: FW-RT6-1b Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:END -->

<!-- FW-RT6-1b-B-TURN-OUTCOME-ADOPTION:BEGIN -->
## FW-RT6-1b Control B — turn outcome and recovery adoption

`RealtimeTurnResult` now normalizes every terminal result to the root-public
`TurnOutcome` model and exposes one normalized `RecoveryAction`. Existing
terminal `RealtimeState` inputs and value comparisons remain compatible, while
transient states are rejected with `LifecycleTransitionError` code
`phase_outcome_mismatch`.

```text
checkpoint: FW-RT6-1b Control B
baseline head: 6443e524d8bc4e32eb4d7e7ecba75e26244c9f10
status: IMPLEMENTED / AWAITING_REVIEW
RealtimeTurnResult canonical outcome: TurnOutcome
RealtimeTurnResult recovery_action: RecoveryAction
completed default recovery: none
interrupted default recovery: reset_turn
cancelled default recovery: reset_turn
failed default recovery: reset_session
rejected default recovery: reuse_session
closed default recovery: none
cancelled and interrupted: DISTINCT
legacy terminal RealtimeState input/value comparison: PRESERVED
transient RealtimeState as terminal outcome: TYPED REJECTION
RealtimeSession phase adoption: DEFERRED TO CONTROL C
terminal registry: NOT IMPLEMENTED
RealtimeEvent sequence/generation/terminal fields: NOT ADDED
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1b Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```

`rejected` means that active-turn ownership was not acquired. `cancelled` means
an admitted turn ended through an explicit host/session cancellation request.
`interrupted` means an admitted turn ended through barge-in or another
asynchronous interruption. Recovery values describe the next safe action and do
not claim that reset, reconnect, close, or provider hard cancellation already
completed.
<!-- FW-RT6-1b-B-TURN-OUTCOME-ADOPTION:END -->
