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
