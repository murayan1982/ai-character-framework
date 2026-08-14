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

<!-- FW-RT6-12b-B-RUNTIME-ADOPTION:BEGIN -->
## Control B runtime adoption

Control B implements bounded ownership in the internal explicit-only
`framework.backpressure_runtime` module. The controller keeps only opaque item
IDs and counters. Audio bytes, response text, subscriber events, synthesis
requests, provider objects, and private paths stay in their existing private
owners and never enter the public backpressure projection.

The four exact adoptions are:

- `audio_input`: `VoiceInputStreamRuntime` admits at most one in-flight chunk;
  `VoiceInputSession` exposes capability, snapshot, last typed rejection, and
  pause/resume operations.
- `response_delta`: `RealtimeEventHub` applies bounded delivery admission to
  `realtime.response.delta` events before sequence/history commitment.
- `event_subscriber`: the same event hub bounds every canonical delivery and
  exposes the observation/control surface through `RealtimeSession`.
- `voice_output`: `BoundedVoiceSynthesisPendingQueue` uses its configured
  pending depth and one in-flight synthesis handoff while retaining its
  established enqueue result vocabulary.

Admission uses `reject_newest`. `capacity_reached` and `paused` are retryable;
`closed` is terminal. Rejected work is not consumed and `dropped=False`.
Capacity rejection produces a `BackpressureOverflowEvent`; adopting components
may also preserve their existing typed diagnostic. A callback failure cannot
convert a rejection to acceptance or hide the caller-visible typed result.

Pause/resume never changes already accepted pending or in-flight ownership.
Closure rejects new work while allowing accepted work to complete or be
explicitly cleared by its existing owner. No automatic eviction, implicit
flush, silent discard, provider hard cancel, device stop, or playback action is
introduced.

```text
baseline head: fa12002e898a88bc9d9025004b0e4b26772d8187
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: IMPLEMENTED / AWAITING_REVIEW
exact Control B surface: 11 files
runtime namespace exports: 1 / EXACT / EXPLICIT_ONLY
boundaries adopted: 4 / 4
maximum pending/in-flight: FIXED PER OWNER
overflow policy: reject_newest
silent drop: False / PROHIBITED
root-public names: 127 / UNCHANGED
provider/network/device/playback execution: False
docs/v600_tasklist.md changed: False
FW-RT6-12b tasks: 0 / 6 CLOSED
Control B acceptance sync: NOT_AUTHORIZED
aggregate acceptance / commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-12b-B-RUNTIME-ADOPTION:END -->
