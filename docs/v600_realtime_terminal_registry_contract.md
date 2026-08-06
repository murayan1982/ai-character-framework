# FW-RT6-2c Realtime Terminal Registry Contract

## Control A — primitive foundation

The terminal registry is an internal, provider-neutral synchronization
primitive for one future `RealtimeSession`. It owns first-terminal commitment
and records later duplicate, regressive, and late non-terminal attempts.

It does not emit events, allocate `EventSequence`, mutate session state, execute
providers, or expose new root-public names.

## Registry identity

```text
scope:
one session-owned registry

key:
TurnId | compatible legacy turn string

None turn ID:
rejected

reserved invalid fw_* turn ID:
rejected by accepted identity normalization

record order:
first-terminal commit order
```

## Atomic first-terminal contract

`RealtimeTerminalRegistry.commit(...)` executes under one `threading.RLock`.

```text
no existing record:
FIRST_TERMINAL / accepted

existing record with same outcome:
DUPLICATE_TERMINAL / suppressed

existing record with different outcome:
TERMINAL_REGRESSION / suppressed
```

Duplicate and regression attempts return immutable
`TerminalCommitDecision` values. They do not replace the first record and do not
raise `LifecycleTransitionError` through the registry caller.

The standalone public lifecycle validator remains unchanged and still raises its
existing typed errors when called directly.

## Retained record

The first committed immutable record retains:

```text
turn_id
outcome
recovery_action
reason
result
```

`result` is generic and internal. Control A does not expose registry records
through `framework.__all__`, session metadata, public events, or diagnostics.

The caller remains responsible for supplying a public-safe reason/result before
later public exposure. Control A performs no raw provider or exception capture.

## Late non-terminal admission

`admit_non_terminal(turn_id)` returns:

```text
before terminal commit:
True

after terminal commit:
False
```

Each rejected late attempt increments `late_non_terminal_count`. The primitive
does not emit a diagnostic event; Control B/C decide the session integration
policy.

## Diagnostics

The immutable diagnostic snapshot contains counts only:

```text
terminal_commit_count
duplicate_terminal_count
terminal_regression_count
late_non_terminal_count
registry_size
```

It contains no result object, reason text, exception, callback, provider payload,
credential, transcript, filesystem path, or host-private value.

## Concurrency

Concurrent `commit(...)` attempts for one turn have exactly one accepted winner.
The winning outcome is scheduler-dependent, but these invariants are
deterministic:

```text
accepted decisions:
1

stored records:
1

suppressed decisions:
attempt count - 1

first record replaced:
False
```

Control A validates primitive-level concurrency. RealtimeSession event/result
integration and deterministic integration-race orchestration remain Controls B
and C.

## Compatibility and deferrals

```text
root-public names:
121 / unchanged

framework.__all__ changed:
False

RealtimeEvent public model changed:
False

RealtimeTurnResult public model changed:
False

create_realtime_session signature changed:
False

RealtimeSession changed:
False

terminal registry root-public:
False

RealtimeSession adoption:
Control B

duplicate terminal event suppression:
Control B

late non-terminal event rejection:
Control B/C

multi-thread session integration race:
Control C

generation stale-result rejection:
FW-RT6-2d
```

## Control B — RealtimeSession adoption

Control B composes the accepted internal registry into `RealtimeSession`
without exporting registry types from the Framework root.

### Session-owned registry

Each session constructs exactly one:

```text
RealtimeTerminalRegistry[RealtimeTurnResult]
```

The registry survives until the session object is discarded. Session close does
not erase terminal results or diagnostics; both remain readable after close.

### Public read-only surfaces

```python
session.terminal_results
session.terminal_diagnostics
```

`terminal_results` is an immutable tuple containing first-terminal
`RealtimeTurnResult` objects in commit order.

`terminal_diagnostics` is an immutable mapping with exactly these keys:

```text
terminal_commit_count
duplicate_terminal_count
terminal_regression_count
late_non_terminal_count
registry_size
```

The existing `event_diagnostics` mapping remains unchanged.

### Terminal event/result ordering

The current mock `run_turn(...)` completion path follows this order:

```text
1. construct RealtimeTurnResult.completed
2. atomically commit result/outcome/recovery/reason to terminal registry
3. if accepted, emit one TURN_COMPLETED event
4. clear active turn/generation
5. restore session idle phase/state
6. return the committed result object
```

During step 3 callback delivery, steps 1 and 2 are already complete. A callback
therefore observes the result in `terminal_results` and
`terminal_commit_count == 1`.

Only the accepted first-terminal decision emits the terminal event. A
suppressed decision returns the first stored result and emits no second
terminal event.

### Sequential duplicate turn ID

When `run_turn(...)` receives a turn ID that already has a terminal record:

```text
non-terminal stage events:
not emitted

terminal event:
not emitted

returned object:
first committed RealtimeTurnResult

duplicate_terminal_count:
incremented
```

Changed input text or metadata on the retry does not replace the first result,
reason, recovery action, or terminal record.

### Current-path boundary

Control B adopts exactly-once ownership for the terminal path currently emitted
by the mock session:

```text
TURN_COMPLETED
```

The generic private commit helper accepts any `RealtimeTurnResult` and terminal
event type so later failure, rejection, cancellation, and interruption paths can
use the same boundary as they are wired.

Control B does not claim that provider-driven or not-yet-implemented terminal
paths already execute.

### Deferrals

A callback can reenter the session because the accepted operation lock is an
`RLock`. Guarding every non-terminal transition against a terminal committed by
a nested/reentrant operation, and deterministic multi-thread integration-race
tests, remain Control C.

```text
reentrant late non-terminal hardening:
Control C

multi-thread session integration race:
Control C

generation stale-result rejection:
FW-RT6-2d

aggregate task/gap acceptance:
Control D
```
