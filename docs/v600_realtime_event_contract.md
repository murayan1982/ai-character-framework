# v6.0.0 Realtime Event Contract

<!-- FW-RT6-1c-A-TYPED-PAYLOADS:BEGIN -->
## FW-RT6-1c Control A — typed realtime event payload models

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Baseline:

```text
285e546d7065eee24d144a4fc39da82d3097bd1f
```

Control A adds provider-neutral immutable payload models without changing the
current `RealtimeEvent` envelope or `RealtimeSession` emission path.

### Root-public additions

```text
RealtimeEventPayloadKind
LifecycleEventPayload
TranscriptEventPayload
ResponseEventPayload
SynthesisEventPayload
AudioEventPayload
MotionEventPayload
InterruptEventPayload
DiagnosticEventPayload
RealtimeEventPayload
```

The accepted 104 root-public names remain in the same order. The ten payload
names are appended, producing 114 canonical root-public names.

### Payload discriminator

```text
lifecycle
transcript
response
synthesis
audio
motion
interrupt
diagnostic
```

### Typed payloads

```text
LifecycleEventPayload:
  outcome
  recovery_action
  reason

TranscriptEventPayload:
  text
  is_final
  confidence

ResponseEventPayload:
  text
  delta_index
  is_final

SynthesisEventPayload:
  request_state
  audio_format

AudioEventPayload:
  artifact_ref
  available
  invalidated
  host_stop_requested

MotionEventPayload:
  request_id
  outcome

InterruptEventPayload:
  scope
  outcome
  reason

DiagnosticEventPayload:
  code
  drop_reason
  dropped_sequence
  overflow_count
```

`RealtimeEventPayload` is the public type union of all eight payload dataclasses.
Each payload is frozen and exposes an immutable JSON-safe `as_dict()` mapping.

### Safety and privacy

```text
provider SDK object retained: False
raw provider response retained: False
raw provider exception retained: False
credential value retained: False
local/private artifact path accepted: False
arbitrary object accepted in scalar fields: False
```

Transcript and response text remain host-visible application content. Opaque
audio artifact references must not contain local paths or credential-like data.

### Compatibility and deferrals

```text
RealtimeEvent envelope adoption: DEFERRED TO CONTROL B
v5 event mapping adapter: DEFERRED TO CONTROL C
RealtimeSession ordered emission: DEFERRED TO CONTROL D
event sequence / generation runtime wiring: NOT IMPLEMENTED
RealtimeEvent terminal flag: NOT ADDED
terminal registry / exactly-once suppression: NOT IMPLEMENTED
stale-result rejection runtime: NOT IMPLEMENTED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next control: FW-RT6-1c Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1c-A-TYPED-PAYLOADS:END -->

<!-- FW-RT6-1c-B-REALTIME-EVENT-ENVELOPE:BEGIN -->
## FW-RT6-1c Control B — RealtimeEvent v6 envelope

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Baseline:

```text
a29b90cadcb6b7917499c30cbe753d2c72ea353b
```

`RealtimeEvent` preserves its accepted v5 constructor prefix and legacy
`as_dict()` mapping while appending an optional canonical v6 envelope. The
envelope normalizes Framework-owned sequence and generation identities, the
last observed transient phase, one typed Control A payload, terminal meaning,
and optional public timestamps.

```text
accepted root-public count: 114 / UNCHANGED
legacy RealtimeEvent field prefix: PRESERVED
legacy RealtimeEvent.as_dict keys: PRESERVED
new suffix: sequence / generation_id / phase / payload / terminal / timestamp / monotonic_timestamp
sequence continuity enforcement: False
generation lifecycle ownership: False
automatic clock reads: False
RealtimeSession canonical emission: False
v5 mapping adapter: DEFERRED / CONTROL C
terminal registry / exactly-once suppression: NOT IMPLEMENTED
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1c Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```

`EventSequence` is the authoritative ordering scalar when present. Timestamps
are optional non-negative finite public values and do not establish ordering. A
terminal flag must agree with the event type; this fixes envelope semantics but
does not suppress duplicate terminal events.
<!-- FW-RT6-1c-B-REALTIME-EVENT-ENVELOPE:END -->

<!-- FW-RT6-1c-C-V5-EVENT-ADAPTER:BEGIN -->
## FW-RT6-1c Control C — explicit v5 event adapter

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Baseline:

```text
532d7852bfe9370514180800a84bfc0a8e13fa9c
```

`RealtimeEvent.to_v5()` and `RealtimeEvent.as_v5_dict()` provide an explicit,
lossy compatibility projection without changing the canonical v6 envelope or
`RealtimeSession` emission path. Existing v5 event types return the same event
instance. Mapped v6 events preserve correlation, phase, payload, terminal, safe
error, timestamp, and public metadata fields while replacing only the event type.

```text
SESSION_STARTED -> SESSION_CREATED
LISTENING_STARTED -> VOICE_INPUT_STARTED
TRANSCRIPT_FINAL -> VOICE_INPUT_COMPLETED
RESPONSE_STARTED -> TEXT_CHAT_STARTED
RESPONSE_COMPLETED -> TEXT_CHAT_COMPLETED
SYNTHESIS_STARTED -> VOICE_OUTPUT_STARTED
SYNTHESIS_COMPLETED -> VOICE_OUTPUT_COMPLETED
TURN_CANCELLED -> TURN_INTERRUPTED
TURN_REJECTED -> TURN_FAILED
```

Events without an honest v5 equivalent return `None`. In particular, listening
completion is dropped because transcript final already projects to the single v5
voice-input completion event. Transcript partial and response delta are never
promoted to completed events.

```text
root-public names: 114 / UNCHANGED
legacy as_dict keys: 10 / UNCHANGED
RealtimeSession canonical v6 emission: DEFERRED TO CONTROL D
on_legacy_event callback: DEFERRED TO CONTROL D
sequence/generation runtime allocation: NOT IMPLEMENTED
terminal registry / exactly-once suppression: NOT IMPLEMENTED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next control: FW-RT6-1c Control D
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1c-C-V5-EVENT-ADAPTER:END -->

<!-- FW-RT6-1c-D-ORDERED-EVENT-ADOPTION:BEGIN -->
## FW-RT6-1c Control D — ordered RealtimeSession event adoption

`RealtimeSession.on_event()` now receives the canonical ordered event stream.
`RealtimeSession.on_legacy_event()` receives only events for which the explicit
`RealtimeEvent.to_v5()` projection exists. Both callback paths preserve the same
session/turn correlation, `EventSequence`, `GenerationId`, typed payload, terminal
flag, public timestamp, and monotonic timestamp.

The mock-safe completed-turn stream is fixed as follows:

```text
canonical:
TURN_STARTED
LISTENING_STARTED
LISTENING_COMPLETED
TRANSCRIPT_FINAL
RESPONSE_STARTED
RESPONSE_COMPLETED
SYNTHESIS_STARTED
SYNTHESIS_COMPLETED
TURN_COMPLETED

legacy projection:
TURN_STARTED
VOICE_INPUT_STARTED
VOICE_INPUT_COMPLETED
TEXT_CHAT_STARTED
TEXT_CHAT_COMPLETED
VOICE_OUTPUT_STARTED
VOICE_OUTPUT_COMPLETED
TURN_COMPLETED
```

`EventSequence` starts at 1 and increments for the full session lifetime; it does
not reset between turns. One new `GenerationId` is allocated after each turn is
admitted and remains stable for that turn. Session-only events and
rejected-before-admission events use `generation_id=None`. Runtime-emitted
canonical categories carry their required typed payload, while public and
monotonic timestamps are allocated automatically at emission. Ordering is
authoritative by `EventSequence`, not by timestamp.

```text
checkpoint: FW-RT6-1c Control D
baseline head: 007e1577a18c92a1dafdf9ede814b97dc2d0a05c
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 8 files
root-public names: 114 / UNCHANGED
on_event canonical stream: ADOPTED
on_legacy_event mapped v5 stream: ADOPTED
completed-turn canonical events: 9
completed-turn legacy events: 8
sequence reset between turns: False
generation per admitted turn: True
session/rejected generation: None
automatic public timestamps: True
typed runtime payloads: True
terminal registry / duplicate suppression: DEFERRED
automatic stale-result rejection: DEFERRED
bounded queue / overflow runtime: DEFERRED
provider partial transcript / response delta callbacks: DEFERRED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1c-D-ORDERED-EVENT-ADOPTION:END -->
