# AI Character Framework v6.0.0 — cancel-aware text-generation contract

## Scope

FW-RT6-5a migrates the v6 text-generation boundary away from treating
`BaseLLM.ask_stream()`'s bare synchronous generator as the primary realtime
contract. Control A defines only provider-neutral model/token vocabulary and the
exact history/capability rules. Provider adapters, stream execution, and
`RealtimeSession` adoption remain deferred.

```text
baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

FW-RT6-4c:
COMPLETED / VERIFIED / ACCEPTED

FW-RT6-5a exact contract review:
COMPLETED

FW-RT6-5a Control A:
AUTHORIZED
```

## Stable import surface

Control A adds the explicitly importable stable package:

```python
framework.realtime_text_generation
```

It is not added to the root-public manifest.

```text
root-public names:
127 / UNCHANGED
```

The exact Control A module exports are:

```text
TextGenerationCancelReason
TextGenerationCancellationToken
TextGenerationDeltaEnvelope
TextGenerationStreamCloseOutcome
TextGenerationStreamCloseResult
```

## Cooperative cancellation token

`TextGenerationCancellationToken` is thread-safe and one-way.

```text
initial cancel_requested:
False

first request_cancel(reason):
True

first reason wins:
True

duplicate request_cancel:
False

reason replacement:
False
```

Accepted cancellation means cooperative cancellation was requested. It does not
claim provider transport hard-cancel success.

Reasons are typed by `TextGenerationCancelReason`:

```text
HOST_REQUEST
INTERRUPT
TURN_CANCELLED
SESSION_CLOSED
RESET
```

## Delta identity

`TextGenerationDeltaEnvelope` carries one `RealtimeStageContext` plus a
stream-local zero-based monotonic `delta_index`.

```text
session identity:
context.session_id

turn identity:
context.turn_id

generation identity:
context.generation_id

delta_index:
integer >= 0

text repr leakage:
False
```

Later stream implementations must emit indexes monotonically from zero for each
stream. Control A defines the envelope but does not yet implement stream
iteration.

## Typed close/dispose result vocabulary

`TextGenerationStreamCloseOutcome` is exactly:

```text
CLOSED
ALREADY_CLOSED
FAILED
```

`TextGenerationStreamCloseResult` contains only a typed outcome, public-safe
message, and recursively sanitized public metadata. It has no raw provider
exception field.

The later stream contract must satisfy:

```text
close idempotent:
True

dispose:
close compatibility alias

underlying iterator close:
at most once

after close future delta delivery:
False

close == normal completion:
False

close == provider hard cancel:
False
```

Those behavioral guarantees are implemented in Control B, not Control A.

## Conversation-history transaction rule

The completed conversation-history commit unit is one complete user + assistant
turn pair.

```text
normal stream completion:
commit user input + full assistant output exactly once

interrupt:
commit incomplete pair = False

cancel:
commit incomplete pair = False

stream close before completion:
commit incomplete pair = False

provider failure:
commit incomplete pair = False

session close:
commit incomplete pair = False

partial assistant output committed as completed history:
False
```

Partial output may remain transient turn/event output, but it is not completed
conversation history. Provider adapters that own conversation state must meet
this rule before they can be reported compatible in FW-RT6-5b.

## Hard-cancel capability source of truth

No duplicate hard-cancel boolean is introduced. The canonical field remains:

```python
TextGenerationCapability.provider_hard_cancel_supported
```

```text
cooperative token accepted => provider hard cancel:
False / NOT IMPLIED

stream close succeeded => provider hard cancel:
False / NOT IMPLIED

Control A provider_hard_cancel_supported default:
False
```

Provider adapters may report `True` only when their actual transport/runtime
supports the corresponding hard-cancel behavior.

## Deferred boundaries

```text
provider-neutral stream handle/reference implementation:
DEFERRED / Control B

future-delta suppression:
DEFERRED / Control B

iterator cleanup / close-dispose behavior:
DEFERRED / Control B

history transaction implementation:
DEFERRED / Control B

CancelableTextGenerationStage:
DEFERRED / Control C

existing TextGenerationStage breaking change:
False

OpenAI / Gemini / xAI / fallback / router adoption:
DEFERRED / FW-RT6-5b

RealtimeSession adoption:
DEFERRED
```

## Control A status

```text
checkpoint:
FW-RT6-5a Control A

status:
IMPLEMENTED / AWAITING_REVIEW

root-public names:
127

provider execution:
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


<!-- FW-RT6-5a-B-STREAM-HISTORY-CONTRACT:BEGIN -->
## Control A acceptance and Control B stream/history implementation

This additive block records Control A acceptance and the provider-neutral
Control B implementation without rewriting the historical Control A checkpoint.

```text
FW-RT6-5a Control A:
COMPLETED / VERIFIED / ACCEPTED

FW-RT6-5a Control B:
IMPLEMENTED / AWAITING_REVIEW

exact Control B delta:
7 files

combined working-tree surface:
32 files

root-public names:
127 / UNCHANGED
```

### Stream handle and reference implementation

The stable package now additionally exports:

```text
TextGenerationCompletedTurn
TextGenerationHistorySink
TextGenerationStream
ProviderNeutralTextGenerationStream
```

`TextGenerationStream` is the provider-neutral cancel-aware handle protocol.
`ProviderNeutralTextGenerationStream` is the deterministic reference
implementation used to fix cancellation, cleanup, and completed-history
semantics before real provider adapters are authorized.

The reference source iterator remains provider-neutral and yields the legacy
compatible shape:

```text
(text: str, emotion_tags: sequence[str])
```

The wrapper converts each delivered source item to
`TextGenerationDeltaEnvelope` and owns the zero-based monotonic `delta_index`.

### Cooperative cancellation and future-delta suppression

`request_cancel()` delegates only to the one-way cooperative token. It does not
claim transport hard cancellation. The stream checks cancellation both before
pulling another source delta and immediately after a source pull returns.

```text
cancel before next source pull:
future delivered deltas = 0

cancel while source pull is in flight:
returned source delta delivered = False

provider transport hard cancel implied:
False
```

A blocking provider iterator may therefore continue until its current provider
read returns when hard cancel is unavailable, but no post-cancel delta is
delivered to the Framework caller.

### Typed close / dispose and cleanup

The reference stream owns at-most-once source cleanup.

```text
close first call:
CLOSED or FAILED

close after closed/completed:
ALREADY_CLOSED

dispose:
close compatibility behavior

underlying source close calls:
at most once

after explicit close future delta delivery:
False
```

Cleanup failure returns the existing public-safe `FAILED` close result and does
not expose the raw source exception in the result. Provider exception
classification itself remains FW-RT6-5b scope.

### Completed conversation-history transaction

`TextGenerationCompletedTurn` is one complete atomic history commit unit:

```text
context:
session / turn / generation

user_input:
one complete user input

assistant_output:
concatenation of all delivered deltas
```

`TextGenerationHistorySink.commit_completed_turn()` accepts exactly that one
pair object. The reference stream invokes it exactly once only after normal
source exhaustion and successful cleanup.

```text
normal completion:
commit completed pair exactly once

cooperative cancel:
commit = False

explicit close before completion:
commit = False

source failure:
commit = False

invalid source delta:
commit = False

history sink failure:
stream closes / completed history remains uncommitted
```

Partial assistant text remains transient stream output and never becomes a
completed history pair.

### Deferred boundaries

```text
CancelableTextGenerationStage:
DEFERRED / Control C

existing TextGenerationStage breaking change:
False

OpenAI / Gemini / xAI / fallback / router adapters:
DEFERRED / FW-RT6-5b

RealtimeSession adoption:
DEFERRED

provider / network / microphone / playback / real VTS execution:
False

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5a-B-STREAM-HISTORY-CONTRACT:END -->


<!-- FW-RT6-5a-C-STAGE-ACCEPTANCE:BEGIN -->
## Control B acceptance and Control C additive stage protocol

This additive block records Control B acceptance and completes FW-RT6-5a
without rewriting the historical Control A/B checkpoints above.

```text
FW-RT6-5a Control A:
COMPLETED / VERIFIED / ACCEPTED

FW-RT6-5a Control B:
COMPLETED / VERIFIED / ACCEPTED

FW-RT6-5a Control C:
IMPLEMENTED / AWAITING_REVIEW

root-public names:
127 / UNCHANGED
```

### Additive cancel-aware stage protocol

The stable package `framework.realtime_text_generation` additionally exports:

```text
CancelableTextGenerationStage
```

The protocol is deliberately separate from the already-stable
`framework.realtime_stage.TextGenerationStage`.

```python
class CancelableTextGenerationStage(Protocol):
    @property
    def stage_kind(self) -> RealtimeStageKind: ...

    def preflight(self) -> TextGenerationCapability: ...

    def capability(self) -> TextGenerationCapability: ...

    def open_stream(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
        cancellation_token: TextGenerationCancellationToken,
    ) -> TextGenerationStream: ...

    def close(self) -> None: ...
```

The existing stage protocol remains source-compatible and unchanged:

```text
framework.realtime_stage exports:
7 / UNCHANGED

TextGenerationStage.start(context, request):
UNCHANGED

TextGenerationStage.cancel(context):
UNCHANGED

legacy TextGenerationStage implementations require open_stream:
False
```

Cancellation is owned by the supplied token / returned `TextGenerationStream`.
The companion stage therefore does not redefine a second hard-cancel result.

### Capability coupling

The canonical capability object remains the existing
`TextGenerationCapability` returned by `preflight()` / `capability()` and carried
by the returned stream.

```text
streaming_supported source:
TextGenerationCapability

cooperative_cancel_supported source:
TextGenerationCapability

provider_hard_cancel_supported source:
TextGenerationCapability.provider_hard_cancel_supported

duplicate hard-cancel field introduced:
False

cooperative cancellation accepted => provider hard cancel:
False / NOT IMPLIED
```

### Aggregate FW-RT6-5a acceptance candidate

```text
stream handle/protocol:
PASS

cooperative cancellation token:
PASS

stream close/dispose contract:
PASS

response delta session/turn/generation correlation:
PASS

completed history transaction:
PASS

provider hard-cancel capability reporting:
PASS

stop future deltas:
PASS

stream resource cleanup:
PASS

interrupted partial output committed as complete:
False

existing TextGenerationStage breaking change:
False

provider / network / microphone / playback / real VTS execution:
False

OpenAI / Gemini / xAI / fallback / router adoption:
DEFERRED / FW-RT6-5b

RealtimeSession adoption:
DEFERRED

next checkpoint:
FW-RT6-5b / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5a-C-STAGE-ACCEPTANCE:END -->



<!-- FW-RT6-5a-D-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-5a post-acceptance source-of-truth sync

This additive block records aggregate operator acceptance without rewriting the
historical Control A/B/C pre-acceptance checkpoints above.

```text
checkpoint:
FW-RT6-5a aggregate acceptance

status:
COMPLETED / VERIFIED / ACCEPTED

combined working-tree surface:
34 files

focused Control A+B+C tests:
41 / PASS

full unit suite at acceptance:
193 / PASS

FW-RT6-5a tasks:
6 / 6 ACCEPTED

provider hard-cancel overclaim:
False

next checkpoint:
FW-RT6-5b exact contract review completed / Control A authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5a-D-ACCEPTANCE-SYNC:END -->
