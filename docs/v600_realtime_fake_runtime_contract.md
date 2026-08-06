# FW-RT6-3b Deterministic Fake Runtime Contract

This document fixes the Control A contract for reproducing realtime ordering and
fault scenarios without a real provider. The controller is deterministic test
infrastructure, not a provider adapter and not a production turn orchestrator.


<!-- FW-RT6-3b-A-DETERMINISTIC-FAKE-RUNTIME:BEGIN -->
## FW-RT6-3b Control A — deterministic fake runtime controller foundation

### Explicit package

Control A adds the explicit test-support package:

```text
framework.realtime_fake_runtime
```

The package is intentionally not imported by `framework` root. The accepted
root-public surface therefore remains 121 names. Importing the package may load
the already accepted provider-neutral stage vocabulary, but it does not import
or execute a provider SDK.

```text
root-public names: 121 / UNCHANGED
framework root imports fake runtime: False
provider SDK root import: False
```

### Fake clock and scheduler

`DeterministicFakeClock` is an integer-tick monotonic clock. It never reads wall
time, sleeps, creates a thread, or enters an event loop.

`DeterministicFakeScheduler` orders actions by:

```text
1. due_tick
2. insertion sequence
```

An action scheduled for a later tick advances only fake time. Actions scheduled
for the same tick execute in insertion order. Callback execution is synchronous
on the caller's thread, making trace order reproducible.

### Stage pause and resume

The scheduler accepts the four provider-neutral `RealtimeStageKind` values.
Pausing a stage prevents its queued actions from executing but does not discard
them. Other unpaused stages continue in deterministic order. When the stage is
resumed, due work executes at the current fake tick.

```text
pause duplicates: no-op / False
resume duplicates: no-op / False
paused due action retained: True
other stage progress while paused: True
```

### Artificial delay

Every scheduled action accepts a non-negative integer `delay_ticks`. Delay is
computed from the current fake tick and never uses a wall-clock timeout.

### Fault and race injections

`DeterministicFakeRuntimeController` exposes explicit injections:

```text
inject_late_completion(...)
inject_duplicate_terminal(...)
inject_cancellation_timeout(...)
inject_queue_overflow(...)
```

Late-completion injection delivers a caller-defined completion at a chosen fake
tick. The target callback or later Control decides whether the generation is
stale; Control A does not inspect a live `RealtimeGenerationGate`.

Duplicate-terminal injection delivers two or more same-correlation terminal
actions in deterministic sequence. Control A intentionally does not suppress
the duplicate because the target terminal registry must observe and classify
the attempted duplicate.

Cancellation-timeout injection emits one deterministic timeout action after the
requested tick count. It does not claim provider hard-cancel, playback stop, TTS
queue flush, or microphone shutdown.

Queue-overflow injection raises the typed
`FakeRuntimeQueueOverflow`. Capacity-triggered overflow preserves already queued
actions and emits a public-safe trace event. An explicit overflow injection is
also available for focused fault tests.

### Deterministic trace

Every scheduler mutation and dispatch emits an immutable
`FakeRuntimeTraceEvent`. Trace metadata is sanitized through the accepted
Framework public-safety boundary. Callback objects and raw exceptions are not
stored in trace events.

`deterministic_trace_signature(...)` returns an exact metadata-free signature
containing only:

```text
trace index
fake tick
trace kind
fake action id
fake action kind
provider-neutral stage kind
public correlation key
```

`assert_deterministic_trace(...)` compares the complete signature and reports
only the first mismatch index and event counts. It does not include metadata or
callback values in assertion messages.

### Reproducibility boundary

The dedicated Control A smoke runs the same mixed scenario twice:

```text
new generation stage action
duplicate terminal delivery
retired-generation late completion
cancellation timeout
```

Both runs must produce the same callback order and exact trace signature.

```text
race reproducible: True
wall-clock sleep: False
background thread: False
network: False
provider SDK: False
microphone: False
playback: False
real VTS: False
```

### Public-safety boundary

Fake action and trace metadata use recursive public sanitization. Secret-like
keys, private paths, binary values, exceptions, cycles, and unknown objects are
not exposed as raw trace values. The controller does not read credentials,
provider payloads, audio, transcripts, screenshots, private paths, LAN
addresses, or operator evidence.

### Deferred boundaries

Control A provides standalone deterministic infrastructure only.

```text
RealtimeSession orchestration changed: False
RealtimeSession stage execution changed: False
generation-gate adoption: DEFERRED / Control B
terminal-registry adoption: DEFERRED / Control B
event-hub trace projection: DEFERRED
normal tests/ directory: DEFERRED / FW-RT6-3c
real provider adapters: NOT EXECUTED
real unified turn orchestration: UNRESOLVED
tasklist checkboxes changed: False
aggregate FW-RT6-3b acceptance: DEFERRED
```

### Control A status

```text
checkpoint: FW-RT6-3b Control A
baseline head: dc02a13b98cb6fd7a8ff300366dac77b9b6f5873
baseline subject: docs/test: accept realtime stage protocols
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 5 files
explicit package: framework.realtime_fake_runtime
fake clock / scheduler: True
stage pause / resume: True
artificial delay: True
late completion injection: True
duplicate terminal injection: True
cancellation timeout injection: True
queue overflow injection: True
deterministic event trace assertion helper: True
race reproducible: True
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3b-A-DETERMINISTIC-FAKE-RUNTIME:END -->
