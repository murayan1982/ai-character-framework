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
