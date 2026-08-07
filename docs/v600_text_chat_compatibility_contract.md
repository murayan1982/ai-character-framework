# AI Character Framework v6.0.0 — FW-RT6-5c TextChatSession compatibility contract

## Purpose

Connect the existing v4/v5 `TextChatSession` facade to v6 identity, event, and
control primitives without breaking the observable legacy facade contract.

## Compatibility invariants

```text
TextChatSessionInfo.api_version:
4.0 / UNCHANGED

ask(text):
str / UNCHANGED

ask_stream(text):
Generator[str, None, None] / UNCHANGED

interrupt():
bool / legacy True semantics preserved

TextChatSessionEvent:
type + data / UNCHANGED

TextChatStateChange:
old_state + new_state / UNCHANGED

root-public names:
127 / UNCHANGED
```

## FW-RT6-5c Control A — identity/event scaffold

Status:

```text
COMPLETED / VERIFIED / ACCEPTED
```

Control A is additive scaffolding only. It does not adopt `ask()` or
`ask_stream()` into the canonical event path yet.

### Stable session identity

Each `TextChatSession` allocates exactly one Framework-owned `SessionId` during
construction and exposes it through the additive `session_id` property. The ID
remains stable across requests and reset. `TextChatSessionInfo` is intentionally
unchanged.

### Internal turn/generation context

The internal `_TextChatRealtimeTurnContext` carries:

```text
session_id
turn_id
generation_id
input_text (repr-hidden)
```

The internal context factory allocates a fresh `TurnId` and `GenerationId` while
reusing the session's stable `SessionId`. Control B will adopt this factory at
the `ask_stream()` execution boundary.

### Canonical realtime callback boundary

`TextChatSession.on_realtime_event(callback)` is additive and receives existing
root-public `RealtimeEvent` values. No new root-public type is introduced.

The internal canonical event primitive:

- stamps the stable `SessionId`
- adopts turn/generation identity when a turn context is supplied
- allocates session-local `EventSequence` values starting at 1
- preserves monotonic sequence allocation
- uses boundary `text_chat`
- delivers synchronously to registered canonical callbacks

### Deliberate Control A non-adoption

```text
ask/ask_stream canonical event emission:
False / DEFERRED TO CONTROL B

interrupt typed result bridge:
False / DEFERRED TO CONTROL C

legacy event projection from canonical event:
False / DEFERRED TO CONTROL B

provider execution path change:
False
```

Existing `ask_stream()`, `interrupt()`, reset, legacy events, state changes, and
exception behavior remain byte-for-byte compatible at their observable boundary
in Control A.

## Safety / execution boundary

```text
provider SDK import:
False

real provider execution:
False

network execution:
False

microphone access:
False

playback execution:
False

real VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```


<!-- FW-RT6-5c-B-CANONICAL-ADOPTION:BEGIN -->
## FW-RT6-5c Control B — canonical ask/ask_stream adoption

Status:

```text
COMPLETED / VERIFIED / ACCEPTED
```

Control B connects the existing legacy text-chat execution path to the Control A
identity/event scaffold without replacing `BaseLLM.ask_stream()` or changing the
legacy facade return/event shapes.

### Turn/generation adoption

Each `ask_stream()` execution allocates exactly one internal turn context.
`ask()` continues to join `ask_stream()` and therefore consumes exactly the same
one turn/generation identity instead of allocating a second context.

A normal turn emits the canonical order:

```text
TURN_STARTED
RESPONSE_STARTED
RESPONSE_DELTA * delivered non-empty chunks
RESPONSE_COMPLETED
TURN_COMPLETED
```

All events for the turn carry the same `SessionId`, `TurnId`, and `GenerationId`.
Session-local `EventSequence` remains monotonic across later turns.

`RESPONSE_DELTA.delta_index` is zero-based and counts only chunks actually
delivered through the legacy generator. Empty provider chunks are not surfaced
as canonical or legacy response deltas. `RESPONSE_COMPLETED` carries the
concatenated delivered assistant text as the final response payload.

### Terminal behavior

```text
normal completion:
TURN_COMPLETED / exactly once

legacy interrupt observed at provider chunk boundary:
TURN_INTERRUPTED / exactly once
RESPONSE_COMPLETED: not emitted

provider/LLM exception:
TURN_FAILED / exactly once
RESPONSE_COMPLETED: not emitted
exception re-raise: preserved
```

The active internal compatibility context is cleared after normal completion,
legacy interruption, or provider failure.

### v4/v5 event projection

Selected canonical events are explicitly projected back to the existing
`TextChatSessionEvent(type, data)` vocabulary:

```text
RESPONSE_STARTED -> response_started {text: original_input}
RESPONSE_DELTA -> response_chunk {chunk: delivered_text}
RESPONSE_COMPLETED -> response_completed {}
TURN_FAILED -> error {public_error_code, safe_message, retryable, public_metadata}
```

Canonical `TURN_STARTED`, `TURN_COMPLETED`, and `TURN_INTERRUPTED` are not
introduced as new legacy event names. Existing normal, interrupted, and error
state transitions remain unchanged.

### Safe failure projection

`TURN_FAILED` reuses the existing public-safe text-chat exception classifier.
Raw provider exception text/class/repr is not placed in canonical or legacy
events. The original exception is still re-raised from `ask_stream()` for v4/v5
compatibility.

### Accepted Control B boundary

```text
interrupt_result():
ADOPTED ADDITIVELY BY CONTROL C

INTERRUPT_REQUESTED canonical bridge from interrupt():
ADOPTED ADDITIVELY BY CONTROL C

legacy interrupt() bool True semantics:
UNCHANGED

TextChatSessionInfo:
UNCHANGED / api_version 4.0

root-public names:
127 / UNCHANGED
```

### Control B verification target

```text
Control A focused baseline:
14 / PASS

Control A+B focused:
32 / PASS

full unit suite:
276 / PASS

provider/network/microphone/playback/real VTS execution:
False

Control C:
AUTHORIZED / IMPLEMENTED IN NEXT CONTROL

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5c-B-CANONICAL-ADOPTION:END -->

<!-- FW-RT6-5c-C-INTERRUPT-AGGREGATE:BEGIN -->
## FW-RT6-5c Control C — typed interrupt bridge and aggregate acceptance

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Control C closes the v4/v5 compatibility adapter without replacing the legacy
`BaseLLM.ask_stream()` execution path.

### Typed interrupt companion

`TextChatSession.interrupt_result(request=None)` is additive and returns the
existing root-public `InterruptResult`.

Typed outcomes are fixed as:

```text
active turn:
ACCEPTED

idle:
NO_ACTIVE_TURN

closed:
ALREADY_CLOSED
```

For an active text turn the result uses the active `TurnId`, records cooperative
suppression of future delivered chunks, and remains truthful about deeper
capabilities:

```text
provider_cancel_supported:
False

queue_flush_supported:
False
```

The compatibility layer does not claim provider transport hard-cancel or output
queue flush support.

### Legacy boolean compatibility

Existing `TextChatSession.interrupt()` delegates through the typed companion but
retains the historical request-received boolean contract:

```text
active:
True

idle:
True

closed:
True
```

The legacy boolean is intentionally not derived from
`InterruptResult.accepted`. The typed result communicates runtime outcome while
the old boolean preserves v4/v5 observable behavior.

### Canonical interrupt event and legacy projection

Every typed/legacy interrupt request emits exactly one canonical
`INTERRUPT_REQUESTED` event with typed `InterruptEventPayload`.

The canonical event:

- uses the stable session identity
- carries active turn/generation identity when a turn is active
- preserves session-local monotonic sequence allocation
- carries the typed interrupt outcome
- contains only public-safe metadata

`INTERRUPT_REQUESTED` is projected to the existing legacy event unchanged:

```text
interrupt_requested {}
```

No new legacy event name is introduced.

### Existing v5 adapter reuse

Control C does not add a second v5 event vocabulary or mapping table.
`RealtimeEvent.to_v5()` / `as_v5_dict()` remain the sole existing v5 projection
boundary. `INTERRUPT_REQUESTED` is already a v5 event type and projects without
replacement. Existing v6 response mappings continue to be reused:

```text
RESPONSE_STARTED -> TEXT_CHAT_STARTED
RESPONSE_DELTA -> no v5 projection
RESPONSE_COMPLETED -> TEXT_CHAT_COMPLETED
```

### Safe-event aggregate

The previously completed safe failure contract remains regression-protected.
Raw provider exception text/class/repr is absent from canonical and legacy
events while the original exception re-raise behavior of `ask_stream()` remains
preserved.

### Aggregate acceptance target

```text
existing ask:
compatible

existing ask_stream:
compatible

existing interrupt:
compatible / bool True preserved

typed active interrupt:
ACCEPTED

typed idle interrupt:
NO_ACTIVE_TURN

typed closed interrupt:
ALREADY_CLOSED

canonical INTERRUPT_REQUESTED:
PASS

existing v5 adapter reused:
PASS

raw exception event:
False

TextChatSessionInfo:
UNCHANGED / api_version 4.0

root-public names:
127 / UNCHANGED

focused Control A+B+C:
46 / PASS

full unit suite:
290 / PASS

FW-RT6-5c tasks:
6 / 6 ACCEPTED-CANDIDATE

provider/network/microphone/playback/real VTS execution:
False

next checkpoint:
FW-RT6-6a / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5c-C-INTERRUPT-AGGREGATE:END -->
