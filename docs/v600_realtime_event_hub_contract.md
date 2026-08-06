# AI Character Framework v6.0.0 Realtime Event Hub Contract

## FW-RT6-2b Control A

```text
status:
IMPLEMENTED / AWAITING_REVIEW

baseline:
89c0ba7ccf150658c5bace612e68bce876db4223

scope:
internal provider-neutral event-hub primitives

root-public names:
121 / UNCHANGED

RealtimeSession adoption:
DEFERRED / Control B
```

## Ordering

One hub owns one session-local `EventSequence` allocator. Event factories must
retain the sequence allocated by the hub.

```text
first sequence:
1

sequence reset:
False

concurrent allocation:
serialized

reentrant allocation:
queued / serialized

authoritative ordering:
EventSequence
```

## Subscription lifecycle

Canonical and legacy callback registrations return distinct opaque
`EventSubscriptionToken` values. Unregistration is token-based and idempotent.

Callback snapshots are fixed when an event is accepted. Unregistration prevents
future accepted events; it does not mutate a delivery already accepted into the
serialized queue.

## Delivery and subscriber safety

```text
delivery policy:
synchronous serialized delivery

callback exception escapes emitter: False

callback exception:
counted / callback remains registered

slow subscriber threshold:
configurable finite non-negative seconds

slow subscriber automatic timeout:
False

slow subscriber automatic eviction: False

slow subscriber:
retained and counted

background callback worker:
False
```

This policy favors deterministic ordering and lifecycle control in the initial
P0 foundation. Async subscriber workers and per-subscriber delivery queues are
not claimed.

## Bounded history and overflow

History has a fixed minimum capacity of two and returns an immutable tuple
snapshot.

When full, the oldest history records are dropped deterministically. The
cumulative overflow counter always changes. If an overflow factory is supplied,
the hub accepts a second sequenced diagnostic event.

```text
history bounded:
True

history overflow silent: False

overflow count:
cumulative dropped history records

overflow diagnostic ordering:
after the event that caused overflow
```

The typed `RealtimeEventType.EVENT_OVERFLOW` integration is deferred to
Control B.

## Close

```text
close idempotent:
True

callbacks retained after close:
False

post-close registration accepted:
False

post-close emission accepted: False

already accepted pending delivery:
allowed to drain
```

`RealtimeSession` close-path adoption and post-close operation behavior are
deferred to Controls B and C.

## Scope exclusions

```text
framework root-public additions:
None

RealtimeSession runtime changed:
False

terminal registry:
DEFERRED / FW-RT6-2c

stale-result rejection:
DEFERRED / later checkpoint

provider/network/microphone/playback/VTS execution:
False
```

## FW-RT6-2b Control B — RealtimeSession adoption

Control B adopts the accepted hub in the existing mock-safe
`RealtimeSession`. It does not add root-public names or change the
`RealtimeEvent`, `RealtimeSessionInfo`, or factory parameter contracts.

### Callback registration

```text
on_event return:
opaque str token

on_legacy_event return:
opaque str token

unregistration:
off_event(token)

duplicate / unknown unregistration:
False

callback exception breaks turn:
False
```

Existing applications that ignore the previous `None` return remain compatible.

### Public history and diagnostics

```text
event_history:
immutable tuple

history limit:
64

event_diagnostics:
immutable Mapping[str, int]

diagnostic keys:
emitted_event_count
callback_error_count
slow_callback_count
history_overflow_count
rejected_after_close_count
subscriber_count
history_limit
```

No callback object, exception, provider payload, credential, transcript body, or
private filesystem path is included in event diagnostics.

### Typed overflow adoption

When history is already full, the hub drops the two oldest records to reserve
space for the triggering event and its overflow diagnostic.

```text
trigger event:
accepted first

overflow event:
accepted second

overflow event type:
RealtimeEventType.EVENT_OVERFLOW

overflow payload:
DiagnosticEventPayload

payload code:
event_history_overflow

drop reason:
bounded_history_capacity

dropped_sequence:
first sequence dropped for this overflow

overflow_count:
cumulative history records dropped

legacy projection:
None
```

The overflow event preserves the trigger event's session, turn, generation,
phase, and state context without creating a second lifecycle transition.

### Compatibility and deferrals

```text
root-public names:
121 / UNCHANGED

RealtimeEvent fields:
UNCHANGED

create_realtime_session parameters:
UNCHANGED

canonical completed-turn event order:
UNCHANGED

legacy completed-turn projection:
UNCHANGED

session close seals hub:
False / DEFERRED TO CONTROL C

post-close active event rejection:
DEFERRED TO CONTROL C

concurrent lifecycle-state mutation lock:
DEFERRED TO CONTROL C

terminal registry:
DEFERRED TO FW-RT6-2c
```

## FW-RT6-2b Control C — close and concurrent-operation boundary

Control C establishes an operation boundary around the existing mock-safe
session methods. It does not add a worker thread, async event queue, provider
operation, or terminal registry.

### Operation serialization

```text
lock:
threading.RLock

operation event groups:
serialized

concurrent run_turn calls:
executed one complete operation at a time

concurrent close:
waits for the active operation boundary

callback reentrant close:
deferred until the outer operation exits

event callback delivery:
synchronous / unchanged
```

The reentrant lock avoids callback deadlock. The deferred-close flag prevents a
same-thread callback from sealing the hub in the middle of its outer turn,
interrupt, flush, or barge-in event group.

### Close sequence

```text
1:
mark session closed

2:
clear active turn / generation and canonical phase

3:
emit exactly one SESSION_CLOSED event

4:
seal RealtimeEventHub

5:
clear callback registrations
```

During `SESSION_CLOSED` callback delivery the session already reports closed.
Reentrant event-producing operations therefore return a closed/rejected result
or raise the existing typed lifecycle error without emitting another event.

### Post-close contract

```text
new callback registration:
rejected

event history:
readable / immutable

event diagnostics:
readable / immutable

old callback token removal:
False after callback clearing

run_turn result:
closed

interrupt result:
already_closed

flush result:
closed

barge-in decision:
rejected

post-close active event:
False
```

No raw exception, callback object, provider payload, credential, transcript
body, or private path is added to the public diagnostics.

### Deferrals

```text
terminal exactly-once registry:
FW-RT6-2c

generation stale-result guard:
FW-RT6-2d

real provider orchestration:
later runtime checkpoint
```
