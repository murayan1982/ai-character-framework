# v6.0.0 Backpressure and Flow-Control Contract

This document freezes the FW-RT6-12b Control A public vocabulary. Control A is
a provider-neutral, data-only contract foundation. It does not install a
queue, change an existing runtime, execute a provider, use the network, or
access audio devices.

## Stable namespace

Applications and adapters import the explicit namespace:

```python
from framework.backpressure import (
    BackpressureAdmission,
    BackpressureAdmissionResult,
    BackpressureBoundary,
    BackpressureCapability,
    BackpressureControlResult,
    BackpressureOverflowEvent,
    BackpressureSnapshot,
)
```

`framework.backpressure` exports exactly 12 names. None is re-exported from the
Framework root, whose v6 application inventory remains frozen at 127 names.
Importability alone never proves runtime support.

## Exact boundaries

The contract defines four boundaries:

| Boundary | Work represented by an opaque item ID |
| --- | --- |
| `audio_input` | host-provided audio input work |
| `response_delta` | one response-delta subscriber delivery |
| `voice_output` | one voice-output request |
| `event_subscriber` | one general realtime-event subscriber delivery |

Contract models do not contain the corresponding raw audio, text, synthesis
payload, or event payload. The runtime that owns the real work remains
responsible for its private storage and disposal.

## Capability and fixed limits

The default `BackpressureCapability` is truthfully unsupported. A supported
capability must declare all of the following:

- a positive `maximum_pending_count`;
- a positive `maximum_in_flight_count`;
- typed retryable rejection support;
- a non-silent overflow event;
- an explicit `reject_newest` overflow policy;
- `silent_drop=False`.

A `BackpressureSnapshot` reports bounded pending and in-flight counts, state,
fixed maxima, and the accumulated overflow count. Counts above their advertised
limits are invalid public state.

## Admission and ownership

Admission is an explicit ownership decision:

1. The caller constructs an opaque `BackpressureAdmission` for one boundary.
2. The adopting runtime returns one `BackpressureAdmissionResult`.
3. `accepted=True` transfers responsibility for that work to the runtime.
4. `capacity_reached` and `paused` are typed, retryable rejections. The caller
   retains the rejected item and decides whether and when to retry it.
5. `closed` is terminal and non-retryable.

The Control A overflow policy is `reject_newest`. It does not mean that the new
item may disappear. A capacity rejection has `dropped=False` and, when adopted
by a runtime, is paired with a `BackpressureOverflowEvent`. An implementation
must never report acceptance and then silently discard the work.

## Pause and resume

`pause` changes admission from `accepting` to `paused`; `resume` changes it back
to `accepting`. Pause applies only to new admission. It does not cancel,
dequeue, flush, dispose, or drop pending or in-flight work. Both operations
report `cancelled_count=0` and `dropped=False`.

Repeated pause/resume requests and operations after closure return typed state
rejections: `already_paused`, `already_accepting`, or `closed`.

## Public-safety boundary

All models are immutable. Public projections contain only enum values, opaque
IDs, bounded counts, booleans, safe messages, and sanitized metadata. Opaque
IDs cannot be paths or URLs. Raw media, response content, provider objects,
credentials, device details, and private filesystem paths are outside this
contract.

## Control A boundary

Control A changes exactly six files and leaves `docs/v600_tasklist.md`
unchanged. All six FW-RT6-12b aggregate tasks remain open (`0 / 6 CLOSED`).

The following remain outside Control A:

- runtime queue adoption for any of the four boundaries;
- integration with the existing specialized voice-output pending queue;
- integration with realtime-event history/subscriber dispatch;
- changing `RealtimeVoiceInputCapability.backpressure_supported` from false;
- Control A acceptance sync, Control B, aggregate acceptance, commit, or push.

Those actions require a separately authorized control. The Control A baseline
is `3153efd68213575e39802f0857d05aee693df255`.
