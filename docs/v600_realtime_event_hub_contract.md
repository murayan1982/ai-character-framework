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
