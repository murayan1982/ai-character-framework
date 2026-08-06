# FW-RT6-2d Realtime Generation Gate Contract

This document fixes the provider-neutral generation-freshness boundary for
FW-RT6-2d. Control A introduces only internal primitives. RealtimeSession
adoption, stale diagnostic event emission, VTS alignment verification, and
aggregate acceptance remain separate authorized controls.


<!-- FW-RT6-2d-A-GENERATION-GATE-PRIMITIVES:BEGIN -->
## FW-RT6-2d Control A — provider-neutral generation gate primitives

Control A adds an internal session-agnostic freshness primitive for future
realtime stage completions. It does not wire `RealtimeSession`, emit
`STALE_RESULT_DROPPED`, change the public event envelope, or execute a provider.

`RealtimeGenerationGate.start_generation(turn_id)` creates a fresh opaque
GenerationId for one admitted turn. Starting another generation first retires
the active generation with `GenerationAdvanceReason.NEW_TURN`.

```text
GenerationAdvanceReason:
new_turn
interrupt
cancel
reset
session_closed
turn_terminal
```

`RealtimeStageCompletionEnvelope` carries one internal stage completion:

```text
turn_id
generation_id
stage
value (internal / repr=False)
```

`RealtimeGenerationGate.admit_completion(envelope)` performs one atomic
freshness decision:

```text
current generation + matching turn:
ACCEPTED

retired generation:
STALE / retired_generation / retirement reason retained

unknown generation:
STALE / unknown_generation

current generation + different turn:
STALE / turn_mismatch
```

The generation gate does not impose single-consumer semantics. Multiple
completions from one current generation may be accepted. Terminal exactly-once
ownership remains the responsibility of the accepted terminal registry.

Read-only primitive diagnostics are immutable and count-only:

```text
generation_start_count
generation_advance_count
accepted_completion_count
stale_completion_count
active_generation_count
registry_size
```

No-active `advance(...)` is an idempotent no-op and does not change diagnostics.
The internal module is not imported or exported by `framework` root.

```text
checkpoint:
FW-RT6-2d Control A

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
5 files

root-public names:
121 / unchanged

RealtimeSession adoption:
DEFERRED / Control B

STALE_RESULT_DROPPED runtime emission:
DEFERRED / Control B

VTS semantic alignment:
DEFERRED / Control C

provider/network/microphone/playback/VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2d-A-GENERATION-GATE-PRIMITIVES:END -->

<!-- FW-RT6-2d-B-REALTIME-SESSION-GENERATION-ADOPTION:BEGIN -->
## FW-RT6-2d Control B — RealtimeSession generation-gate adoption

Control B adopts the accepted Control A generation gate inside
`RealtimeSession`. The gate remains internal and is imported lazily when a
session instance is created, so `import framework` preserves provider/runtime
import safety and does not eagerly load the internal gate module.

```text
exact change surface:
6 files

root-public names:
121 / unchanged

RealtimeEvent public model changed:
False

RealtimeTurnResult public model changed:
False

create_realtime_session signature changed:
False
```

The sixth file is the accepted Control A primitive smoke. Its historical
candidate-surface assertion is advanced to the Control B candidate so the
primitive regression remains executable after session adoption.

### Session ownership and correlation

Each session owns one `RealtimeGenerationGate`. A new admitted turn starts a
fresh generation through the gate. `_active_generation_id` remains the
correlation identity for the currently executing event group, while the gate is
the freshness source of truth.

```text
new turn:
fresh generation / prior active generation retired by new_turn

terminal event:
retains the turn generation

first terminal commit:
generation retired by turn_terminal before terminal callback delivery
```

### Central completion ingress

All future stage completions must pass through one internal session ingress:

```text
_apply_stage_completion(envelope, deliver=...)
```

Freshness admission and `deliver(value)` execute under the same reentrant
session operation lock.

```text
current generation + matching turn:
accepted / delivered once

retired generation:
rejected / not delivered

unknown generation:
rejected / not delivered

current generation + different turn:
rejected / not delivered
```

A stale completion never mutates session state, phase, terminal registry, or the
original stage result surface.

### Typed stale diagnostic

When the session is open, one rejected completion emits one canonical v6-only
diagnostic:

```text
type:
STALE_RESULT_DROPPED

payload:
DiagnosticEventPayload

code:
stale_stage_completion

drop_reason:
retired_generation | unknown_generation | turn_mismatch

safe_message:
Stale realtime stage completion was dropped.

legacy projection:
None
```

The event retains the rejected envelope's turn and generation IDs. For a
retired generation, `public_metadata.retired_by` contains only the stable
retirement reason. Completion values, provider objects, raw payloads, raw
exceptions, private paths, endpoints, and credentials are not copied.

After `close()` is requested, stale completion delivery remains rejected but no
new stale diagnostic event is emitted. Count-only observability remains
available through `generation_diagnostics`.

### Advance ordering

```text
normal first terminal:
turn_terminal before terminal event callbacks

interrupt of current generation:
interrupt before INTERRUPT_REQUESTED

cancel_current_turn:
cancel before INTERRUPT_REQUESTED

first close request:
session_closed before deferred-close decision

no-active interrupt:
no advance

unrelated explicit-turn interrupt:
current generation preserved

duplicate close:
no advance
```

No public reset method is added. `reset` remains a defined internal retirement
reason for a later reset boundary.

### Additive diagnostics

`RealtimeSession.generation_diagnostics` is an immutable read-only mapping with
exact keys:

```text
generation_start_count
generation_advance_count
accepted_completion_count
stale_completion_count
active_generation_count
registry_size
```

Existing `event_diagnostics` and `terminal_diagnostics` keys remain unchanged.

```text
checkpoint:
FW-RT6-2d Control B

status:
IMPLEMENTED / AWAITING_REVIEW

Control A:
ACCEPTED / REGRESSION VERIFIED

Control C race and VTS alignment:
NOT_AUTHORIZED

provider/network/microphone/playback/VTS execution:
False

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2d-B-REALTIME-SESSION-GENERATION-ADOPTION:END -->
