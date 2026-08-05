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
