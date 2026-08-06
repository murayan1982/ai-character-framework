# FW-RT6-3a Realtime Stage Protocol Contract

This document fixes the provider-neutral public stage vocabulary for AI Character
Framework v6.0.0. Control A defines protocol and correlation models only.
`RealtimeSession` injection, fake-stage composition, orchestration, cancellation
coordination, and aggregate acceptance remain separate authorized controls.


<!-- FW-RT6-3a-A-STAGE-PROTOCOL-FOUNDATION:BEGIN -->
## FW-RT6-3a Control A — provider-neutral stage protocol foundation

### Stable public package

Control A adds the explicitly stable public package:

```text
framework.realtime_stage
```

The package is not imported by `framework` root during Control A. This preserves
the accepted 121-name root-public compatibility surface while allowing host code,
composition code, tests, and type checkers to depend on one documented public
stage package.

```text
root-public names: 121 / UNCHANGED
framework root imports stage package: False
provider SDK root import: False
```

### Common correlation models

`RealtimeStageContext` carries the authoritative correlation identity used by a
future stage operation:

```text
session_id
turn_id
generation_id
public_metadata
```

Framework-reserved session and turn identities are validated while legacy host
strings remain compatible. `generation_id` is always one validated
Framework-owned `GenerationId`. Public metadata is recursively sanitized by the
accepted FW-RT6-2a utility.

`RealtimeStageResultEnvelope[T]` carries:

```text
stage_kind
context
result
public_metadata
```

The wrapped public stage result is excluded from `repr` so transcripts, generated
text, or artifact details are not accidentally logged through envelope repr.
The envelope does not accept `None` as a result and rejects a result whose
public model does not match the declared stage kind.

### Stage kinds

```text
voice_input
text_generation
voice_output
motion
```

### Four stage protocols

```text
VoiceInputStage
TextGenerationStage
VoiceOutputStage
MotionStage
```

Every protocol has the same lifecycle method names and keyword-only operation
context:

```text
stage_kind
preflight()
capability()
start(*, context, request)
cancel(*, context)
close()
```

The stage-specific request, result, and capability types are existing
provider-neutral Framework public models:

```text
VoiceInputStage:
VoiceInputRequest -> RealtimeStageResultEnvelope[VoiceInputResult]
RealtimeVoiceInputCapability

TextGenerationStage:
RealtimeTurn -> RealtimeStageResultEnvelope[TextChatResult]
TextGenerationCapability

VoiceOutputStage:
VoiceOutputRequest -> RealtimeStageResultEnvelope[VoiceOutputResult]
RealtimeVoiceOutputCapability

MotionStage:
MotionRequest -> RealtimeStageResultEnvelope[MotionResult]
RealtimeMotionCapability
```

No provider client, provider-specific cancel handle, raw provider payload, raw
exception, credential, private path, or transport object appears in these public
protocol signatures.

### Minimal cancellation boundary

Control A intentionally keeps `cancel(...) -> bool` narrow:

```text
True:
cooperative cancellation request accepted by the stage implementation

False:
no cooperative cancellation request accepted
```

This boolean does not claim provider hard-cancel completion, queue flush,
artifact invalidation, host playback stop, or detailed subsystem reach. Those
remain governed by later interrupt/output-control contracts.

`close() -> None` is required to be safe for repeated calls by implementations,
but Control A does not invoke or compose any real implementation.

### Deferred boundaries

```text
RealtimeSession injection: DEFERRED / Control B
factory signature change: DEFERRED / Control B
fake stage injection acceptance: DEFERRED / Control B
aggregate tasklist completion: DEFERRED / later Control
provider adapter migration: DEFERRED
real STT / LLM / TTS / motion orchestration: DEFERRED
interrupt coordinator detailed reach: DEFERRED
FW-RT6-3b deterministic fake runtime controller: NOT IMPLEMENTED
FW-RT6-3c normal unit-test layer: NOT IMPLEMENTED
```

### Control A status

```text
checkpoint: FW-RT6-3a Control A
baseline head: 6fe95075e1c9ae9e62150eb9844edfe9f004a8e2
baseline subject: docs/test: accept realtime generation gate
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 5 files
stable public package: framework.realtime_stage
stage protocol count: 4
common lifecycle methods: preflight / capability / start / cancel / close
stage context: session / turn / generation
provider-specific public objects: False
root-public names: 121 / UNCHANGED
RealtimeSession injection: DEFERRED / Control B
real unified orchestration: False
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3a-A-STAGE-PROTOCOL-FOUNDATION:END -->


<!-- FW-RT6-3a-B-STAGE-INJECTION:BEGIN -->
## FW-RT6-3a Control B — provider-neutral RealtimeSession stage injection

Control B adds four optional keyword-only stage bindings to both
`RealtimeSession(...)` and `create_realtime_session(...)`:

```text
voice_input_stage
text_generation_stage
voice_output_stage
motion_stage
```

Each supplied object must structurally satisfy its Control A protocol and expose
the matching provider-neutral `RealtimeStageKind`. Validation does not call
`preflight()`, `capability()`, `start()`, `cancel()`, or provider code. The stable
stage package remains lazily imported: ordinary `import framework` and no-stage
session construction do not load `framework.realtime_stage`.

The session exposes only public-safe binding state:

```text
injected_stage_kinds
stage_diagnostics:
  injected_stage_count
  stage_close_count
  stage_close_error_count
```

Raw injected objects, provider clients, provider-specific handles, close
exceptions, credentials, private paths, and raw payloads are not returned by
these diagnostics. `RealtimeSession.close()` attempts each injected stage
`close()` once. Close failures are suppressed from the public boundary and
recorded only as a count so session close and event-hub sealing remain intact.

Control B intentionally does not execute injected stages from `run_turn()`. The
accepted mock lifecycle remains the active turn path, and capability aggregation
still uses the existing session snapshot. Real/fake stage orchestration,
`preflight()` composition, stage `start()` ordering, cancellation coordination,
and generation-completion delivery remain separate controls.

```text
checkpoint: FW-RT6-3a Control B
baseline head: af474e2ceec9988bec1b7e7fadfe2d4037774597
baseline subject: feat/test: add realtime stage protocols
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 5 files
factory change: ADDITIVE / KEYWORD-ONLY
injection slots: voice_input / text_generation / voice_output / motion
provider-neutral structural validation: True
stage kind validation: True
constructor lifecycle calls: 0
run_turn injected stage starts: 0 / ORCHESTRATION DEFERRED
session close stage close: ONCE PER INJECTED STAGE
close exception exposure: False / COUNT-ONLY
root-public names: 121 / UNCHANGED
ordinary root import loads framework.realtime_stage: False
provider SDK root import: False
fake stage injection: PASS
real unified orchestration: False
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
Control C: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3a-B-STAGE-INJECTION:END -->
