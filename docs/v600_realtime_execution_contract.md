# FW-RT6-4c Public Execution Model Contract

This document fixes the public and internal execution model selected for
AI Character Framework v6.0.0 realtime orchestration.

<!-- FW-RT6-4c-A-EXECUTION-MODELS-BRIDGE:BEGIN -->
## Control A — execution model and persistent runtime primitive

### Accepted baseline

```text
baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

FW-RT6-4b:
COMPLETED / VERIFIED / ACCEPTED

accepted uncommitted FW-RT6-4b surface:
16 files

commit / push:
NOT_AUTHORIZED
```

### Exact execution decision

```text
internal orchestration:
ASYNC-FIRST

public primary turn execution:
async

public compatibility:
explicit blocking wrapper
legacy run_turn blocking compatibility

per-call asyncio.run:
False

per-stage event loop:
False
```

The public session adoption itself is deferred to Control B. Control A fixes the
model and provides the reusable internal bridge primitive without changing
`RealtimeSession` behavior.

### Public execution errors

Control A appends exactly two root-public names after the accepted 125-name
FW-RT6-4b surface:

```text
RealtimeExecutionErrorCode
RealtimeExecutionError
```

Canonical root-public count:

```text
125 -> 127
```

Exact error codes:

```text
blocking_call_in_active_event_loop
blocking_call_from_runtime_thread
```

These errors are public-safe classifications. They do not expose provider,
credential, endpoint, transcript, audio, transport, or application-specific
details.

### Planned public session surface

Control B owns the following adoption:

```python
async def run_turn_async(
    turn: RealtimeTurn | None = None,
    *,
    input_text: str = "",
    public_metadata: Mapping[str, Any] | None = None,
) -> RealtimeTurnResult:
    ...
```

```python
def run_turn_blocking(
    turn: RealtimeTurn | None = None,
    *,
    input_text: str = "",
    public_metadata: Mapping[str, Any] | None = None,
) -> RealtimeTurnResult:
    ...
```

The existing `run_turn()` remains a blocking compatibility alias. An active
host event-loop thread must use `await run_turn_async(...)`; blocking execution
from that thread will be rejected with
`BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP`. Blocking execution from the session
runtime thread will be rejected with `BLOCKING_CALL_FROM_RUNTIME_THREAD`.

Control A defines these classifications but does not yet modify
`RealtimeSession`.

### Internal persistent execution bridge

`framework.realtime_execution_bridge._RealtimeExecutionBridge` owns:

```text
construction:
zero worker threads
zero event loops

first execution:
one daemon worker thread
one asyncio event loop

later executions:
same thread reused
same loop reused

per-call event loop creation:
False

per-stage event loop creation:
False

submission:
asyncio.run_coroutine_threadsafe

shutdown before start:
does not create runtime

shutdown:
idempotent

new execution after shutdown:
rejected
```

The bridge is internal and is not exported from `framework`.

### Existing stage protocol

The accepted provider-neutral realtime stage protocol remains sync in Control A:

```text
stage.start()
stage.cancel()
stage.close()
```

No public stage protocol is converted to `async def` in FW-RT6-4c Control A.
Async-first orchestration will adapt the existing protocol internally.

### Deferred controls

```text
RealtimeSession bridge ownership:
DEFERRED / Control B

run_turn_async():
DEFERRED / Control B

run_turn_blocking():
DEFERRED / Control B

run_turn compatibility delegation:
DEFERRED / Control B

host event-loop blocking guard:
DEFERRED / Control B

callback execution-context guarantee:
DEFERRED / Control C

callback blocking reentrancy guard:
DEFERRED / Control C

session cancel/close + bridge shutdown safety:
DEFERRED / Control C

deadlock/reentrancy aggregate tests:
DEFERRED / Control C
```

### Control A status

```text
checkpoint:
FW-RT6-4c Control A

status:
IMPLEMENTED / AWAITING_REVIEW

execution decision:
ASYNC-FIRST

root-public names:
127

new public names:
2

persistent bridge primitive:
IMPLEMENTED

RealtimeSession adoption:
False / DEFERRED

provider / network / microphone / playback / real VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-A-EXECUTION-MODELS-BRIDGE:END -->

<!-- FW-RT6-4c-B-SESSION-EXECUTION-ADOPTION:BEGIN -->
## Control B — RealtimeSession async/blocking adoption

Control A is accepted. Control B adopts the persistent execution bridge into
`RealtimeSession` without changing the accepted provider-neutral stage protocol.

### Public execution surface

```text
primary turn execution:
await session.run_turn_async(...)

explicit blocking compatibility:
session.run_turn_blocking(...)

legacy compatibility:
session.run_turn(...) -> run_turn_blocking(...)
```

`run_turn_async()` is safe to await from a host event loop. Blocking turn
execution from a thread that already owns an active asyncio loop is rejected
with `BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP`. Blocking turn execution from the
session runtime thread is rejected with `BLOCKING_CALL_FROM_RUNTIME_THREAD`.
No nested event loop is created.

### Admission and runtime ownership

Turn admission remains synchronous and occurs before work is queued to the
persistent runtime loop. This preserves FW-RT6-4b single-active-turn semantics:

```text
concurrent new turn while active:
typed rejection

rejected turn generation allocation:
0

active generation replacement/retirement:
0
```

Each `RealtimeSession` owns one lazy `_RealtimeExecutionBridge`. Session
construction and `start_turn()` alone start no worker. The first executable
async/blocking turn starts one worker thread and one asyncio loop; later turns
reuse the same runtime.

### Deferred to Control C

```text
callback execution-context guarantee:
DEFERRED

callback blocking reentrancy aggregate contract:
DEFERRED

cancel/close + bridge shutdown integration:
DEFERRED

final deadlock/reentrancy acceptance:
DEFERRED
```

### Control B status

```text
checkpoint:
FW-RT6-4c Control B

Control A:
ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control B delta:
9 files

combined working-tree surface:
24 files

focused Control A+B tests:
26 / PASS expected

full unit suite:
142 / PASS expected

run_turn_async:
IMPLEMENTED

run_turn_blocking:
IMPLEMENTED

legacy run_turn delegation:
IMPLEMENTED

host event-loop blocking guard:
IMPLEMENTED

session-owned persistent bridge:
IMPLEMENTED / LAZY

admission before runtime queue:
True

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-B-SESSION-EXECUTION-ADOPTION:END -->

<!-- FW-RT6-4c-C-CALLBACK-CLOSE-ACCEPTANCE:BEGIN -->
## Control C — callback context, reentrancy, and close safety

Control B is accepted. Control C closes the execution-model contract without
changing the provider-neutral stage protocol or FW-RT6-4b terminal semantics.

### Callback execution context

`RealtimeEventHub` delivery remains synchronous. Therefore callbacks emitted by
`run_turn_async()`, `run_turn_blocking()`, or legacy `run_turn()` execute on the
session runtime worker thread that owns the persistent asyncio loop. Direct
synchronous control operations such as `interrupt()` continue to deliver their
callbacks on the caller thread. The Framework does not automatically marshal
callbacks onto a host/UI asyncio loop.

### Blocking reentrancy

A callback already running on the session runtime thread must not block waiting
for that same runtime. Calls to `run_turn_blocking()` or legacy `run_turn()` from
such a callback fail immediately with
`BLOCKING_CALL_FROM_RUNTIME_THREAD`. No nested loop and no self-wait are used.

`cancel_current_turn()` remains a synchronous control-plane operation and may be
called reentrantly from a runtime callback under the existing reentrant session
operation lock.

### Close and bridge shutdown

```text
close inside an active callback:
mark close requested
finish the outermost serialized operation
close session/event hub
release the session operation lock
then request bridge shutdown

bridge shutdown while operation depth > 0:
False

runtime thread self-join:
False

close before bridge start:
bridge is closed without creating a worker

close after bridge start from a non-runtime thread:
stop loop + join worker

close from runtime callback:
request loop stop without self-join
worker terminates after current runtime task returns

close idempotent:
True
```

The bridge exposes only internal stop diagnostics/waiting primitives. No new
root-public name is added by Control C; the root-public count remains 127.

### Aggregate acceptance candidate

```text
active host event loop safe:
PASS

blocking host-loop call:
TYPED_REJECTION

blocking runtime-callback call:
TYPED_REJECTION

callback execution context:
DETERMINISTIC / TESTED

cancel callback reentrancy:
DEADLOCK FALSE

close callback reentrancy:
DEADLOCK FALSE

runtime self-join:
False

worker / loop leak after final close:
False

per-call asyncio.run:
False

persistent loop reused:
True

FW-RT6-4b single-active / terminal / reusable semantics:
UNCHANGED

provider / network / microphone / playback / real VTS execution:
False
```

### Control C status

```text
checkpoint:
FW-RT6-4c Control C

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control C delta:
8 files

combined working-tree surface:
26 files

focused Control A+B+C tests:
36 / PASS expected

full unit suite:
152 / PASS expected

FW-RT6-4c tasks:
6 / 6 ACCEPTED-CANDIDATE

next checkpoint:
FW-RT6-5a / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-C-CALLBACK-CLOSE-ACCEPTANCE:END -->

<!-- FW-RT6-4c-D-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-4c post-acceptance source-of-truth sync

This additive block records operator acceptance without rewriting the historical
Control A/B/C pre-acceptance checkpoints above.

```text
checkpoint:
FW-RT6-4c aggregate acceptance

status:
COMPLETED / VERIFIED / ACCEPTED

combined working-tree surface:
26 files

focused Control A+B+C tests:
36 / PASS

full unit suite at acceptance:
152 / PASS

FW-RT6-4c tasks:
6 / 6 ACCEPTED

deadlock:
False

worker / loop leak after final close:
False

next checkpoint:
FW-RT6-5a exact contract review completed / Control A authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-D-ACCEPTANCE-SYNC:END -->
