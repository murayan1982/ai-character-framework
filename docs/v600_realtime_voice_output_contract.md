# FW-RT6-6a Voice Output Generation Protocol Contract

This document fixes the provider-neutral synthesis-generation vocabulary for AI
Character Framework v6.0.0. Control A defines models, protocols, and capability
semantics only. Provider adapter adoption, concrete active-generation state,
queue ownership, artifact invalidation, and host playback control remain later
authorized controls.

<!-- FW-RT6-6a-A-VOICE-SYNTHESIS-PROTOCOL:BEGIN -->
## FW-RT6-6a Control A — voice synthesis generation protocol

### Baseline

```text
baseline HEAD / origin/main:
3c40a1bc537aaa9015235b520b3431819ec0381a

FW-RT6-4b / 4c / 5a / 5b / 5c:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED

FW-RT6-6a exact contract review:
COMPLETED

Control A:
READY_FOR_IMPLEMENTATION
```

### Stable explicit package

Control A adds one explicitly stable package:

```text
framework.realtime_voice_output
```

It is not imported or re-exported by `framework` root in Control A.

```text
root-public names:
127 / UNCHANGED
```

Existing contracts remain unchanged:

```text
VoiceOutputSession
VoiceOutputRequest
VoiceOutputResult
VoiceSynthesisRequest
VoiceSynthesisResult
framework.realtime_stage.VoiceOutputStage
```

The exact package exports are:

```text
SynthesisWorkId
VoiceSynthesisResultEnvelope
VoiceSynthesisActiveGeneration
VoiceSynthesisCancelOutcome
VoiceSynthesisCancelResult
VoiceSynthesisProviderAdapter
VoiceSynthesisStage
```

### Synthesis work identity

`SynthesisWorkId` is a provider-neutral Framework-owned opaque scalar.

```text
format:
fw_synthesis_<32 lowercase hex>

provider request/model/voice/client identity embedded:
False
```

Correlation uses four independent identities:

```text
session_id
turn_id
generation_id
work_id
```

`GenerationId` remains the lifecycle/stale-result generation. One lifecycle
generation may contain multiple synthesis work IDs. A synthesis work ID never
replaces session, turn, or lifecycle-generation identity.

### Result and active-generation models

`VoiceSynthesisResultEnvelope` fields are exactly:

```text
context
work_id
result
```

The wrapped `VoiceOutputResult` is excluded from `repr`. Printing the envelope
must not expose output URLs, artifact references, private paths inherited from a
legacy result, provider payloads, or raw request text.

`VoiceSynthesisActiveGeneration` fields are exactly:

```text
context
work_id
```

The active snapshot intentionally does not expose:

```text
VoiceOutputRequest / raw text
VoiceOutputResult
provider/client/model/voice identifiers
provider payloads
artifact URL/ref/path
provider exception
```

### Typed cancel result

`VoiceSynthesisCancelOutcome` is exactly:

```text
REQUESTED
NO_ACTIVE_GENERATION
WORK_MISMATCH
ALREADY_TERMINAL
UNSUPPORTED
ALREADY_CLOSED
FAILED
```

`VoiceSynthesisCancelResult` fields are:

```text
outcome
context
work_id
cooperative_cancel_requested
provider_hard_cancel_applied
safe_message
retryable
public_metadata
```

`public_metadata` is recursively public-sanitized. Cooperative cancel and
provider hard cancel are independent facts.

```text
REQUESTED => provider hard cancel applied:
NOT IMPLIED

UNSUPPORTED => provider hard cancel applied:
False

pending queue clear => active synthesis cancel:
NOT IMPLIED
```

### Provider adapter protocol

`VoiceSynthesisProviderAdapter` is provider-neutral and exposes exactly:

```python
def capability() -> RealtimeVoiceOutputCapability: ...
def synthesize(request: VoiceOutputRequest) -> VoiceOutputResult: ...
```

The provider adapter receives no Framework session/turn/generation/work IDs.
Those identities remain owned by the synthesis stage and later queue/runtime
orchestration.

Provider-specific clients, request payloads, voice IDs, model IDs, credentials,
endpoints, local paths, and raw exceptions are not public protocol values.

### Synthesis stage protocol

`VoiceSynthesisStage` exposes:

```text
active_generation
preflight()
capability()
start(*, context, request)
cancel(*, context, work_id=None)
close()
```

Exact operation types:

```text
active_generation:
VoiceSynthesisActiveGeneration | None

preflight / capability:
RealtimeVoiceOutputCapability

start:
RealtimeStageContext + VoiceOutputRequest
-> VoiceSynthesisResultEnvelope

cancel:
RealtimeStageContext + optional SynthesisWorkId
-> VoiceSynthesisCancelResult
```

The existing `framework.realtime_stage.VoiceOutputStage` is not changed or
replaced by Control A.

### Capability source of truth

Control A introduces no duplicate capability model. The accepted source of
truth remains `RealtimeVoiceOutputCapability`.

```text
generation_cancel_supported:
truthfully reports whether the synthesis stage can request active generation cancellation

provider_hard_cancel_supported:
truthfully reports whether the selected provider/runtime can hard-cancel active synthesis

Control A existing defaults:
generation_cancel_supported = False
provider_hard_cancel_supported = False
```

A cooperative cancel request, successful stage cleanup, pending queue clear, or
host playback stop must not be used to infer provider hard-cancel support.

### Deferred boundaries

```text
concrete provider-neutral synthesis stage implementation:
DEFERRED / Control B

thread-safe active_generation state:
DEFERRED / Control B

existing voice-output provider adapter capability adoption:
DEFERRED / Control B

existing synthesize compatibility wiring:
DEFERRED / Control B

aggregate identity / observability / privacy acceptance:
DEFERRED / Control C

bounded pending queue:
DEFERRED / FW-RT6-6c

artifact store/path mismatch correction:
DEFERRED / FW-RT6-6b

generation cancellation execution / artifact invalidation:
DEFERRED / FW-RT6-6d

host playback physical stop ownership:
False / HOST RESPONSIBILITY
```

### Control A status

```text
checkpoint:
FW-RT6-6a Control A

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
5 files

stable package:
framework.realtime_voice_output

root-public names:
127 / UNCHANGED

provider/network/microphone/playback/real VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6a-A-VOICE-SYNTHESIS-PROTOCOL:END -->

<!-- FW-RT6-6a-B-PROVIDER-ACTIVE-ADOPTION:BEGIN -->
## FW-RT6-6a Control B — provider adapter and active-generation adoption

### Baseline

```text
baseline HEAD / origin/main:
5a509c9ddc18cd55dc84b264193bab973c176ee6

Control A:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED

Control B:
AUTHORIZED
```

Control B adopts the accepted `VoiceSynthesisProviderAdapter` shape in the
existing private voice-output provider adapter layer and adds a Framework-owned
reference synthesis stage with thread-safe `active_generation` observability.
It does not expand the accepted stable export list or the `framework` root API.

### Existing provider adapter adoption

The existing private adapters now expose exactly the capability facts required
by the stable provider-neutral protocol:

```text
capability() -> RealtimeVoiceOutputCapability
synthesize(VoiceOutputRequest) -> VoiceOutputResult
```

Capability inspection does not load a provider SDK, perform network I/O, read a
microphone, play audio, connect to VTube Studio, or execute real TTS. Existing
provider selection and `VoiceOutputSession.create_output()` compatibility remain
unchanged.

The current v5 voice-output providers do not expose a verified active-generation
cancel handle. Therefore Control B truthfully reports:

```text
generation_cancel_supported = False
provider_hard_cancel_supported = False
pending_flush_supported = False
active_audio_invalidation_supported = False
```

A configured provider key is not sufficient to claim provider runtime
availability. Control B does not import/probe the provider SDK during capability
inspection, so unprobed runtime availability remains false rather than being
overclaimed.

### Concrete active-generation state

`ProviderNeutralVoiceSynthesisStage` is a Framework reference implementation of
the accepted `VoiceSynthesisStage` protocol. It is intentionally **not** added to
`framework.realtime_voice_output.__all__`; the accepted seven-name stable package
surface from Control A remains unchanged.

For one synchronous synthesis call the stage owns:

```text
SynthesisWorkId
VoiceSynthesisActiveGeneration(context, work_id)
thread-safe active-generation state
exact active->terminal clearing
single-active-work rejection
```

The public-safe active snapshot continues to expose only:

```text
context
work_id
```

It never exposes request text, provider/client/model/voice identifiers, provider
payloads, audio result data, artifact paths/refs, or provider handles.

### Cancellation truth in Control B

Control B does not implement active synthesis cancellation. While a matching
synthesis work item is active, `cancel()` returns `UNSUPPORTED` and both
cancellation facts remain false:

```text
cooperative_cancel_requested = False
provider_hard_cancel_applied = False
```

A non-matching context/work ID returns `WORK_MISMATCH`; no active work returns
`NO_ACTIVE_GENERATION`; a closed stage returns `ALREADY_CLOSED`.

Actual active-generation cancellation execution, future-delivery suppression,
and artifact invalidation remain **FW-RT6-6d** work. Pending work remains
FW-RT6-6c and host playback stop remains FW-RT6-6e.

### Compatibility and exact surface

```text
existing VoiceOutputSession behavior changed:
False

existing framework.realtime_stage.VoiceOutputStage changed:
False

stable framework.realtime_voice_output exports changed:
False

root-public names:
127 / UNCHANGED

exact change surface: 6 files
provider/network/microphone/playback/real VTS execution: False
Control C: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-6a-B-PROVIDER-ACTIVE-ADOPTION:END -->


<!-- FW-RT6-6a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6a Control C — aggregate acceptance

### Baseline and scope

```text
baseline HEAD / origin/main:
dd34b24faca398a070d1c50681b5e1809c260fb2

Control A:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED

Control B:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED

Control C:
AUTHORIZED
```

Control C adds no runtime implementation. It reviews the accepted Control A+B
voice-synthesis generation boundary as one aggregate and fixes the acceptance
truth needed to close FW-RT6-6a without claiming later P0-5 work.

### Aggregate identity and observability

```text
synthesis work identity:
SynthesisWorkId / fw_synthesis_<32 lowercase hex>

correlation identities:
session / turn / generation / work

active generation observable:
True

active generation public fields:
context / work_id

active generation thread-safe:
True

provider adapter receives Framework correlation IDs:
False
```

The provider adapter continues to receive only `VoiceOutputRequest`. Framework
correlation remains stage-owned. Active-generation observation therefore does not
expose request text, provider/client/model/voice identifiers, provider payloads,
artifact paths/references, or provider handles.

### Aggregate capability truth

`RealtimeVoiceOutputCapability` remains the sole capability source. The current
accepted provider boundary has no verified active synthesis cancel handle, so the
aggregate truth remains:

```text
generation_cancel_supported = False
provider_hard_cancel_supported = False
pending_flush_supported = False
active_audio_invalidation_supported = False
```

`UNSUPPORTED` for a matching active-generation cancel is truthful Control B
behavior; it must not be reinterpreted as `REQUESTED`, completed cancellation, or
provider hard-cancel success.

### Public surface and privacy acceptance

```text
framework.realtime_voice_output stable exports:
7 / UNCHANGED

framework root-public names:
127 / UNCHANGED

provider details public:
False

existing VoiceOutputSession behavior changed:
False

existing framework.realtime_stage.VoiceOutputStage changed:
False
```

### Later P0-5 boundaries remain separate

```text
opaque artifact store / local-path correction:
FW-RT6-6b

bounded pending queue / pending clear:
FW-RT6-6c

active generation cancellation / artifact invalidation / future delivery suppression:
FW-RT6-6d

host playback coordination:
FW-RT6-6e
```

Closing FW-RT6-6a does not authorize or claim any of those behaviors.

### Control C acceptance candidate

```text
exact Control C delta:
3 files

FW-RT6-6a tasks:
6 / 6 ACCEPTED-CANDIDATE

generation identity:
True / PASS expected

active generation observable:
True / PASS expected

provider details public:
False / PASS expected

root-public names:
127 / UNCHANGED

provider/network/microphone/playback/real VTS execution:
False

next checkpoint:
FW-RT6-6b / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6a-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6b-A-ARTIFACT-STORE-PROTOCOL:BEGIN -->
## FW-RT6-6b Control A — opaque artifact store protocol

### Baseline and authorization

```text
baseline HEAD / origin/main:
5318f89aeb524f91f7c388816058bb0e8a3e2fc0

FW-RT6-6a:
COMPLETED / VERIFIED / ACCEPTED / CLOSED

FW-RT6-6b exact contract review:
COMPLETED

Control A:
AUTHORIZED
```

### Stable explicit package

Control A adds one explicitly stable package:

```text
framework.voice_artifacts
```

It is not imported or re-exported by the `framework` root in Control A.

```text
root-public names:
127 / UNCHANGED
```

The exact stable package exports are:

```text
VoiceArtifactId
VoiceArtifactState
VoiceArtifactRecord
VoiceArtifactStore
```

The concrete local file-backed reference implementation remains Framework
internal and is not part of the stable package export list.

### Opaque artifact identity

`VoiceArtifactId` is a Framework-owned provider-neutral scalar.

```text
format:
fw_voice_artifact_<32 lowercase hex>

filesystem path embedded:
False

provider/client/model/voice identity embedded:
False

URL embedded:
False
```

`VoiceArtifactRef.artifact_id` may carry the serialized opaque ID, but callers
must not parse it as a path, storage location, provider object, or provider
identifier.

### Store protocol

`VoiceArtifactStore` fixes the following provider-neutral operations:

```text
store
resolve / open / delete / expire
bind_generation
```

`store()` accepts bytes or streamed bytes and returns `VoiceArtifactRef`. The
store implementation owns any internal directory/path and does not return that
path through the stable package.

`resolve()` returns a public-safe `VoiceArtifactRecord` containing only:

```text
ref
state
generation_id
```

No filesystem path or provider handle is present in the record.

### Artifact validity

`VoiceArtifactState` is exactly:

```text
VALID
EXPIRED
DELETED
```

Only `VALID` records are playable through `open()`.

```text
expired artifact -> open:
not playable

deleted artifact -> open:
not playable

unknown artifact -> resolve:
None
```

Expiration is a store-lifecycle primitive only. Interrupt-driven artifact
invalidation and future-delivery suppression remain FW-RT6-6d.

### Lifecycle generation association

The store may bind a valid artifact to one `GenerationId` after synthesis.
Binding the same generation is idempotent; rebinding the same artifact to a
different generation is rejected.

The accepted FW-RT6-6a provider-adapter boundary remains unchanged:

```text
provider adapter receives session ID:
False

provider adapter receives turn ID:
False

provider adapter receives GenerationId:
False

provider adapter receives SynthesisWorkId:
False
```

A provider adapter stores provider-produced bytes and receives only an opaque
`VoiceArtifactRef`. Framework synthesis/runtime orchestration owns generation
binding after the provider result returns.

### Deferred Control B adoption

Control A intentionally leaves the current real-provider adapter unchanged.
Therefore the known legacy path handoff still exists until Control B:

```text
real provider audio_artifact_ref=str(artifact_path):
EXISTING / NOT ACCEPTED AS 6b FINAL

Control B responsibility:
replace direct path handoff with VoiceArtifactStore + VoiceArtifactRef
```

Control B also owns enforcing the generated-result exactly-one-handoff boundary
at the real provider/result integration point.

### Later P0-5 boundaries remain separate

```text
bounded pending queue / pending clear:
FW-RT6-6c

active generation cancellation / interrupt-driven artifact invalidation / future delivery suppression:
FW-RT6-6d

host playback coordination:
FW-RT6-6e
```

### Control A status

```text
checkpoint:
FW-RT6-6b Control A

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
5 files

stable package:
framework.voice_artifacts

opaque artifact ID:
fw_voice_artifact_<32 lowercase hex>

store lifecycle:
resolve / open / delete / expire

generation binding primitive:
True

provider adapter receives GenerationId:
False

real provider path leak corrected:
False / DEFERRED CONTROL B

root-public names:
127 / UNCHANGED

provider/network/microphone/playback/real VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6b-A-ARTIFACT-STORE-PROTOCOL:END -->

<!-- FW-RT6-6b-B-PROVIDER-ARTIFACT-ADOPTION:BEGIN -->
## FW-RT6-6b Control B — provider artifact-store adoption

### Baseline and authorization

```text
baseline HEAD / origin/main:
d9f4a562728ba1c63b82c83f4ff5826cf900f9b0

Control A:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED

Control B:
AUTHORIZED
```

Control B connects the accepted `framework.voice_artifacts` foundation to the
existing real voice-output adapter and the provider-neutral synthesis stage. It
does not add a new root-public name or change the accepted seven-name
`framework.realtime_voice_output` export list.

### Real provider handoff correction

The ElevenLabs adapter no longer creates a public result from
`str(artifact_path)`. Provider-produced bytes are streamed into a
Framework-owned `VoiceArtifactStore`, which returns a `VoiceArtifactRef`.

```text
real provider local path in VoiceOutputResult:
False

provider result artifact type:
VoiceArtifactRef

opaque artifact ID:
fw_voice_artifact_<32 lowercase hex>

provider adapter receives Framework correlation IDs:
False
```

The adapter still receives only `VoiceOutputRequest`. Session, turn, lifecycle
generation, and synthesis-work identity remain outside the provider protocol.

### Generated result invariant

`VoiceOutputResult.audio_artifact_ref` is now an opaque `VoiceArtifactRef | None`;
a raw string/path is not an accepted artifact handoff. Generated results require
exactly one public handoff:

```text
audio_url XOR audio_artifact_ref:
REQUIRED

generated + both handoffs:
REJECTED

generated + no handoff:
REJECTED

non-generated + playable handoff:
REJECTED
```

This removes the legacy state where a local path could be stored in
`audio_artifact_ref` while retaining the existing URL handoff branch.

### Stage-side generation binding

`ProviderNeutralVoiceSynthesisStage` may be composed with the same
`VoiceArtifactStore` used by a provider adapter. When synthesis returns an
artifact reference, the stage binds that opaque artifact to
`RealtimeStageContext.generation_id` after the provider call returns.

Generation identity is therefore not passed into the provider adapter. The
accepted FW-RT6-6a correlation-free provider protocol remains unchanged.

### Deferred boundaries

```text
bounded pending work / pending clear:
FW-RT6-6c

interrupt-driven artifact invalidation / future-delivery suppression:
FW-RT6-6d

active synthesis cancellation / provider hard cancel:
FW-RT6-6d

host playback coordination / physical stop:
FW-RT6-6e
```

Control B does not infer any of those capabilities from successful artifact
storage or generation binding.

### Control B status

```text
checkpoint:
FW-RT6-6b Control B

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
7 files

real provider path leak corrected:
True

raw local path in VoiceOutputResult:
False

exactly one generated audio handoff:
ENFORCED

stage-side generation binding:
True

provider adapter receives Framework IDs:
False

root-public names:
127 / UNCHANGED

provider/network/microphone/playback/real VTS execution:
False

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6b-B-PROVIDER-ARTIFACT-ADOPTION:END -->

<!-- FW-RT6-6b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6b Control C — aggregate opaque artifact-store acceptance

### Accepted combined boundary

Control C performs no runtime implementation. It reviews the accepted Control A
artifact-store foundation and Control B provider adoption as one FW-RT6-6b
contract and closes the seven aggregate task items as an acceptance candidate.

```text
baseline HEAD / origin/main:
163ad7c7a611221148dd1bc5a902685615caaf16

Control A:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED

Control B:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED

exact Control C delta:
3 files
```

### Aggregate invariants

```text
VoiceArtifactStore protocol:
True

opaque artifact ID:
fw_voice_artifact_<32 lowercase hex>

internal storage path exposed by VoiceArtifactRef:
False

resolve / open / delete / expire:
PASS

generated audio handoff:
audio_url XOR audio_artifact_ref / REQUIRED

real provider local path in VoiceOutputResult:
False

provider result artifact type:
VoiceArtifactRef

lifecycle generation association:
Framework synthesis-stage side

provider adapter receives Framework correlation IDs:
False

expired/deleted artifact playable:
False
```

`FileVoiceArtifactStore` may own a private local storage path internally, but
that path is not a public artifact identity. Public handoff is the opaque
`VoiceArtifactRef`, and real provider adapters do not publish
`str(artifact_path)`.

Lifecycle `GenerationId` remains outside the provider protocol. The Framework
synthesis stage binds a returned artifact reference to its lifecycle generation
after provider synthesis returns.

### Deferred P0-5 boundaries

```text
bounded pending work / pending clear:
FW-RT6-6c

active synthesis cancellation / provider hard cancel:
FW-RT6-6d

interrupt-driven artifact invalidation:
FW-RT6-6d

future-delivery suppression:
FW-RT6-6d

host playback coordination / physical stop:
FW-RT6-6e
```

Expired/deleted artifacts are non-playable under the FW-RT6-6b store validity
contract. Control C does not reinterpret that as active interrupt-driven
artifact invalidation support.

### Control C status

```text
checkpoint:
FW-RT6-6b Control C

status:
IMPLEMENTED / AWAITING_REVIEW

FW-RT6-6b tasks:
7 / 7 ACCEPTED-CANDIDATE

root-public names:
127 / UNCHANGED

provider/network/microphone/playback/real VTS execution:
False

next checkpoint:
FW-RT6-6c / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6b-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6c-A-BOUNDED-PENDING-QUEUE:BEGIN -->
## FW-RT6-6c Control A — bounded pending synthesis queue foundation

### Baseline and authorization

```text
baseline HEAD / origin/main:
3bdd196c34d2ffd3eaa2dfc30cc39cf22aa34409

FW-RT6-6b:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED

FW-RT6-6c exact contract review:
COMPLETED

Control A:
AUTHORIZED
```

The exact contract review keeps pending work separate from active synthesis.
The accepted `ProviderNeutralVoiceSynthesisStage` remains the active-generation
owner. Control A introduces a pending-only queue and does not execute the stage.

### Stable explicit package

Control A adds one explicitly stable package:

```text
framework.realtime_voice_output_queue
```

It is not imported or re-exported by the `framework` root.

```text
root-public names:
127 / UNCHANGED
```

The exact stable exports are:

```text
VoiceSynthesisPendingWork
VoiceSynthesisEnqueueOutcome
VoiceSynthesisEnqueueResult
VoiceSynthesisPendingClearOutcome
VoiceSynthesisPendingClearResult
VoiceSynthesisQueueEventType
VoiceSynthesisQueueEvent
VoiceSynthesisPendingQueue
```

The concrete `BoundedVoiceSynthesisPendingQueue` reference implementation is not
part of the stable `__all__` surface in Control A.

### Pending work identity and privacy

Every enqueue attempt receives one Framework-owned `SynthesisWorkId`. An
accepted pending item retains exactly:

```text
RealtimeStageContext:
session_id
turn_id
generation_id

SynthesisWorkId:
work_id
```

`VoiceSynthesisPendingWork` contains no `VoiceOutputRequest`, synthesis text,
provider/model/voice identity, provider object, artifact reference/path, or raw
result.

The concrete reference queue may retain the request privately for later
Control B handoff. That private entry is not part of the stable protocol.

### Bounded admission

`max_pending_depth` is configured at queue construction and must be an integer
greater than or equal to one. It counts pending work only; active synthesis is
not included.

```text
pending_count < max_pending_depth:
ACCEPTED

pending_count == max_pending_depth:
REJECTED_FULL

automatic oldest-item drop:
False

automatic newest-item silent drop:
False
```

A full-queue rejection leaves the existing pending FIFO unchanged.

`VoiceSynthesisEnqueueResult` is the authoritative admission result. Overflow is
therefore non-silent even when no event callback is registered or a host
diagnostic callback fails.

### Overflow event

Control A adds a provider-neutral component event:

```text
VoiceSynthesisQueueEventType.OVERFLOW
```

The event contains only the rejected work identity, pending count, configured
maximum depth, cumulative overflow count, safe message, and public-safe
metadata. It does not contain request text or provider data.

This component event is deliberately not a self-sequenced `RealtimeEvent`.
Canonical session event sequencing remains owned by `RealtimeEventHub`.
A later integration may project queue overflow into the already existing
`RealtimeEventType.EVENT_OVERFLOW` / `DiagnosticEventPayload` vocabulary without
creating a second sequence allocator.

### Pending clear

```text
clear_pending(context=None):
clear all pending work

clear_pending(context=<RealtimeStageContext>):
clear only exact matching pending context

active generation cancellation:
False / DEFERRED FW-RT6-6d

provider hard cancel:
False / DEFERRED FW-RT6-6d

artifact invalidation:
False / DEFERRED FW-RT6-6d

future-delivery suppression:
False / DEFERRED FW-RT6-6d

host playback stop:
False / DEFERRED FW-RT6-6e
```

`VoiceSynthesisPendingClearResult.active_generation_cancelled` is fixed to
`False`; constructing a pending-clear result that claims active cancellation is
rejected.

The existing provider capability remains truthful in Control A:

```text
RealtimeVoiceOutputCapability.pending_flush_supported:
UNCHANGED / provider boundary remains False

RealtimeVoiceOutputCapability.generation_cancel_supported:
UNCHANGED / False

RealtimeVoiceOutputCapability.provider_hard_cancel_supported:
UNCHANGED / False
```

Framework queue ownership is not inferred as provider-side queue flush support.

### Deferred Control B adoption

Control B owns queue-to-stage handoff. It must preserve the enqueue-time
`SynthesisWorkId` when pending work becomes active rather than allocating a
second unrelated work identity.

Control B must also prove:

```text
active generation state:
owned by synthesis stage

pending state:
owned by pending queue

same item simultaneously active and pending:
False

pending clear changes active generation:
False

active cancel overclaim:
False
```

No provider adapter receives Framework session, turn, generation, or work IDs.

### Control A status

```text
checkpoint:
FW-RT6-6c Control A

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
5 files

stable package:
framework.realtime_voice_output_queue

stable exports:
8

bounded pending queue:
True

max_pending_depth:
CONFIGURABLE / >= 1

enqueue typed result:
True

silent overflow drop:
False

pending clear:
True

active generation cancellation:
False / DEFERRED FW-RT6-6d

root-public names:
127 / UNCHANGED

provider/network/microphone/playback/real VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6c-A-BOUNDED-PENDING-QUEUE:END -->

<!-- FW-RT6-6c-B-PENDING-ACTIVE-HANDOFF:BEGIN -->
## FW-RT6-6c Control B — pending-to-active stage handoff

### Baseline and authorization

```text
baseline HEAD / origin/main:
820056ff897e7bfdcfa20c3f7d4b14df0633c3b1

Control A:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED

Control B:
AUTHORIZED
```

Control B adopts the deferred queue-to-stage composition without changing the
stable `VoiceSynthesisPendingQueue` or `VoiceSynthesisStage` protocols.

### Exact implementation surface

```text
M docs/app_integration_contract.md
M docs/public_facade.md
M docs/v600_realtime_voice_output_contract.md
M framework/realtime_voice_output.py
M framework/realtime_voice_output_queue.py
M scripts/smoke_v600_voice_output_queue_control_a.py
A scripts/smoke_v600_voice_output_queue_control_b.py
```

`framework` root remains 127 names. `framework.realtime_voice_output` remains the
accepted seven-name stable package and
`framework.realtime_voice_output_queue` remains the accepted eight-name stable
package. The concrete queue/stage composition is not added to either `__all__`.

### Pending-to-active ownership transition

The concrete bounded queue owns pending state. The concrete synthesis stage owns
active state. `handoff_next(stage=...)` performs one FIFO transition.

```text
1. inspect oldest private pending entry under queue lock
2. concrete stage claims entry.context + entry.work_id
3. only after successful claim, remove that exact entry from pending FIFO
4. release queue lock
5. execute provider through the already accepted stage adapter boundary
6. return VoiceSynthesisResultEnvelope with the SAME work_id
7. clear stage active state on completion or failure
```

The stage claim and queue removal form one observable ownership transition: a
pending observer cannot observe the claimed item after the queue lock is released,
and the stable pending protocol never owns active state.

### Claim failure and execution failure

A closed or already-active stage rejects before queue removal. The pending FIFO is
therefore unchanged and no restore race is required.

Once the stage claim succeeds and the item leaves pending state, provider
execution failure is an active-work failure. The item is not silently requeued.
The stage clears active state in its existing deterministic finally boundary.

### Identity preservation and privacy

```text
enqueue work_id:
SynthesisWorkId A

active work_id:
SynthesisWorkId A

result envelope work_id:
SynthesisWorkId A

second work ID allocation during handoff:
False
```

Provider adapters still receive only `VoiceOutputRequest`; session, turn,
generation, and synthesis-work identities are not passed to the adapter. Request
text remains private and is absent from public pending/active snapshots.

### Pending clear and deferred P0-5 behavior

Pending clear continues to operate only on queue-owned pending entries. Once a
work item is active it is absent from the pending queue, so targeted or full
pending clear cannot change the stage-owned active generation.

```text
generation cancellation:
False / DEFERRED FW-RT6-6d

provider cancel timeout:
DEFERRED FW-RT6-6d

interrupt-driven artifact invalidation:
DEFERRED FW-RT6-6d

future-delivery suppression:
DEFERRED FW-RT6-6d

host playback coordination:
DEFERRED FW-RT6-6e
```

`RealtimeVoiceOutputCapability.pending_flush_supported`,
`generation_cancel_supported`, and `provider_hard_cancel_supported` remain
unchanged and false at the accepted provider boundary.

### Control B status

```text
checkpoint:
FW-RT6-6c Control B

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
7 files

queue-to-stage handoff:
True

same enqueue/active/result work ID:
True

active state owner:
synthesis stage

pending state owner:
pending queue

same work simultaneously observable as pending and active:
False

pending clear changes active generation:
False

active cancel overclaim:
False

root-public names:
127 / UNCHANGED

FW-RT6-6c aggregate tasklist:
0 / 7 CLOSED

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6c-B-PENDING-ACTIVE-HANDOFF:END -->

<!-- FW-RT6-6c-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6c Control C — bounded voice-output queue aggregate acceptance

### Accepted combined boundary

Control C performs no runtime implementation. It reviews the accepted Control A
bounded pending-queue foundation and Control B pending-to-active stage handoff as
one FW-RT6-6c contract and closes the seven aggregate task items as an acceptance
candidate.

```text
baseline HEAD / origin/main:
647191b7b939587c9977279dd446e16e90bfb4b3

Control A:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED

Control B:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED

exact Control C delta:
3 files
```

### Aggregate invariants

```text
bounded pending queue:
True

max_pending_depth:
CONFIGURABLE / >= 1

pending item correlation:
session / turn / generation / SynthesisWorkId

enqueue result:
typed ACCEPTED / REJECTED_FULL

silent overflow drop:
False

overflow event:
typed VoiceSynthesisQueueEventType.OVERFLOW

pending clear:
typed / exact context or all pending

active generation owner:
synthesis stage

pending state owner:
pending queue

same work simultaneously pending and active:
False

enqueue work ID == active work ID == result work ID:
True

closed/busy stage claim mutates pending FIFO:
False

provider execution failure silently requeues claimed work:
False

pending clear changes active generation:
False

provider adapter receives Framework correlation IDs:
False
```

The stable queue protocol remains pending-only, and the stable synthesis-stage
protocol remains active-only. The concrete reference composition does not add
`handoff_next()` to `VoiceSynthesisPendingQueue` and does not add a handoff
`work_id` argument to `VoiceSynthesisStage.start()`.

### Deferred P0-5 boundaries

```text
active synthesis cooperative cancellation:
DEFERRED FW-RT6-6d

provider cancel timeout / hard-cancel result:
DEFERRED FW-RT6-6d

interrupt-driven artifact invalidation:
DEFERRED FW-RT6-6d

future-delivery suppression / stale late artifact guard:
DEFERRED FW-RT6-6d

host playback coordination / physical stop:
DEFERRED FW-RT6-6e
```

Clearing pending work is not active synthesis cancellation. Provider capability
flags remain truthful and unchanged; Framework queue ownership is not reported as
provider-side pending flush support.

### Control C status

```text
checkpoint:
FW-RT6-6c Control C

status:
IMPLEMENTED / AWAITING_REVIEW

FW-RT6-6c tasks:
7 / 7 ACCEPTED-CANDIDATE

stable framework.realtime_voice_output_queue exports:
8 / UNCHANGED

stable framework.realtime_voice_output exports:
7 / UNCHANGED

root-public names:
127 / UNCHANGED

provider/network/microphone/playback/real VTS execution:
False

next checkpoint:
FW-RT6-6d / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6c-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6d-A-TYPED-CANCEL-RESULT:BEGIN -->
## FW-RT6-6d Control A — typed voice-synthesis cancellation result foundation

Control A extends the accepted `framework.realtime_voice_output` cancellation
vocabulary only. It does not execute active cancellation, change the provider
adapter protocol, invalidate an artifact, suppress delivery, alter
`RealtimeSession`, or change the pending queue.

```text
baseline HEAD / origin/main:
3613056b798bd0a46ecee87a252ed5f36156a67d

exact Control A surface:
6 files

VoiceSynthesisCancelOutcome additions:
COMPLETED
TIMED_OUT

VoiceSynthesisCancelResult additions:
cooperative_cancel_completed
provider_hard_cancel_unsupported
artifact_invalidated
future_delivery_suppressed

stable framework.realtime_voice_output exports:
7 / UNCHANGED

root-public names:
127 / UNCHANGED
```

### Result invariants

```text
REQUESTED:
cooperative_cancel_requested = True
cooperative_cancel_completed = False

COMPLETED:
cooperative_cancel_requested = True
cooperative_cancel_completed = True

TIMED_OUT:
cooperative_cancel_requested = True
cooperative_cancel_completed = False

provider_hard_cancel_applied XOR provider_hard_cancel_unsupported:
enforced when either is claimed

provider hard-cancel result without cooperative request:
invalid

artifact_invalidated = True:
future_delivery_suppressed = True / REQUIRED

non-cancel outcomes:
must not claim cancellation, invalidation, or suppression effects
```

The current concrete synthesis stage remains unchanged in behavior. A matching
active cancel still returns `UNSUPPORTED`; current provider adapters still report
`generation_cancel_supported=False` and
`provider_hard_cancel_supported=False`. Control A therefore establishes result
vocabulary without claiming provider cancellation capability.

```text
active synthesis cancellation execution:
False

provider cancel timeout execution:
False

provider hard cancel execution:
False

artifact invalidation execution:
False

future delivery suppression execution:
False

RealtimeSession changed:
False

pending queue changed:
False

FW-RT6-6d tasklist:
0 / 7 CLOSED

Control B:
NOT_AUTHORIZED

provider/network/microphone/playback/real VTS execution:
False

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6d-A-TYPED-CANCEL-RESULT:END -->

<!-- FW-RT6-6d-B-CANCEL-INVALIDATION-ADOPTION:BEGIN -->
## FW-RT6-6d Control B — cooperative cancellation / invalidation runtime adoption

Control B adopts the accepted Control A result vocabulary in an internal
Framework reference composition. It does not change the stable synthesis-stage
protocol, provider-adapter protocol, pending-queue protocol, root facade, or
`RealtimeSession` real-runtime orchestration.

```text
baseline HEAD / origin/main:
5e26f29847a357225a29c724c6014aa15ff1c83d

exact Control B surface:
6 files

active cooperative cancellation:
IMPLEMENTED

provider cancel timeout:
BOUNDED / IMPLEMENTED

provider hard cancel:
UNSUPPORTED / TRUTHFUL

completed artifact invalidation:
IMPLEMENTED

future delivery suppression:
IMPLEMENTED

late artifact freshness source:
RealtimeGenerationGate

duplicate cancel / flush:
IDEMPOTENT / PASS expected

pending clear vs active cancel:
DISTINGUISHED

FW-RT6-6d tasks:
0 / 7 CLOSED

Control C:
NOT_AUTHORIZED
```

### Concrete cancellation semantics

`CancelableProviderNeutralVoiceSynthesisStage` is an internal subclass of the
accepted concrete `ProviderNeutralVoiceSynthesisStage`. The accepted stable
`VoiceSynthesisStage.cancel(context, work_id=None)` signature is unchanged.

For one matching active synthesis work item:

```text
cancel request accepted:
cooperative_cancel_requested = True

provider call quiesces before configured timeout:
outcome = COMPLETED
cooperative_cancel_completed = True

provider call still active at timeout:
outcome = TIMED_OUT
cooperative_cancel_completed = False

provider_hard_cancel_applied:
False

provider_hard_cancel_unsupported:
True

future_delivery_suppressed:
True
```

The cancellation barrier is one-way for that work item. A timed-out provider may
continue internally, but when it eventually returns its audio result is converted
to a non-audio `VoiceOutputResult` before leaving the stage. Provider transport
completion is therefore not confused with host delivery permission.

Duplicate cancel for the same work returns the already established typed cancel
result. A later work item receives a fresh cancellation state.

### Artifact invalidation

`VoiceArtifactState.INVALIDATED` is additive. The stable
`framework.voice_artifacts.__all__` list remains four names and the stable
`VoiceArtifactStore` protocol is unchanged. The concrete
`FileVoiceArtifactStore.invalidate_generation(generation_id)` invalidates every
currently `VALID` artifact bound to that lifecycle generation and returns the
invalidated records.

```text
VALID -> INVALIDATED:
allowed by concrete generation invalidation

INVALIDATED playable:
False

duplicate generation invalidation:
empty result / idempotent

raw local path exposed:
False
```

A cancelable synthesis stage reports active-audio invalidation capability only
when its supplied artifact store actually implements the concrete
`invalidate_generation` operation.

### Existing generation-gate stale guard

When supplied with the accepted internal `RealtimeGenerationGate`, the cancelable
reference stage wraps the synthesis result in the existing
`RealtimeStageCompletionEnvelope` and calls the gate's atomic
`admit_completion(...)` decision.

```text
current matching generation:
completion may retain audio handoff

retired / unknown / turn-mismatched generation:
audio handoff suppressed
bound artifact invalidated
new freshness registry created:
False
```

This control does not alter `RealtimeGenerationGate`.

### Pending clear / active cancel composition

`VoiceSynthesisOutputController.flush(...)` is internal reference composition.
Its typed aggregate retains the pending clear result separately from the active
cancel result. Clearing pending work therefore never claims active cancellation.

```text
pending clear:
VoiceSynthesisPendingClearResult

active cancel:
VoiceSynthesisCancelResult | None

duplicate flush with no pending/active/invalidation effect:
idempotent no-op

provider pending_flush_supported changed:
False
```

### Deferred boundary

```text
RealtimeSession real TTS orchestration changed:
False

provider adapter protocol changed:
False

provider capability source changed:
False

host playback coordination / physical playback stop:
DEFERRED / FW-RT6-6e

provider/network/microphone/playback/real VTS execution:
False

root-public names:
127 / UNCHANGED

framework.realtime_voice_output exports:
7 / UNCHANGED

framework.voice_artifacts exports:
4 / UNCHANGED

framework.realtime_voice_output_queue exports:
8 / UNCHANGED

FW-RT6-6d aggregate:
NOT_COMPLETED

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6d-B-CANCEL-INVALIDATION-ADOPTION:END -->

<!-- FW-RT6-6d-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6d Control C — generation cancel / artifact invalidation aggregate acceptance

Control C is aggregate acceptance only. It adds no new runtime implementation
beyond the accepted Control A typed cancellation-result vocabulary and Control B
Framework-owned cooperative cancellation/invalidation reference composition.

```text
baseline HEAD / origin/main:
663a23b4485a96a75e5a3dfb1ab70c15517e0fc2

exact Control C delta:
3 files

runtime Python modified by Control C:
False

active synthesis cooperative cancel:
PASS expected

provider cancel timeout:
BOUNDED / PASS expected

provider hard cancel applied:
False / TRUTHFUL expected

provider hard cancel unsupported:
True / PASS expected

completed artifact invalidation:
PASS expected

invalidated artifact playable:
False expected

future delivery suppression:
PASS expected

late artifact stale guard:
existing RealtimeGenerationGate / PASS expected

new freshness registry:
False expected

duplicate cancel / flush:
IDEMPOTENT / PASS expected

pending clear vs active cancel:
DISTINGUISHED / PASS expected

stable framework.realtime_voice_output exports:
7 / UNCHANGED

stable framework.voice_artifacts exports:
4 / UNCHANGED

stable framework.realtime_voice_output_queue exports:
8 / UNCHANGED

root-public names:
127 / UNCHANGED

FW-RT6-6d tasks:
7 / 7 ACCEPTED-CANDIDATE

FW-RT6-6d aggregate:
IMPLEMENTED / AWAITING_REVIEW

next checkpoint:
FW-RT6-6e / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

### Aggregate semantics

Framework-cooperative cancellation remains distinct from provider hard cancel.
The current provider adapter capability source is unchanged and must continue to
report provider hard cancel as unsupported. No transport-level hard-cancel
success is inferred from Framework cancellation completion.

A cancellation request establishes a one-way future-delivery suppression barrier.
If a synchronous provider call quiesces inside the configured wait, the typed
result may complete; if it exceeds the bounded wait, the result is timed out
without removing the suppression barrier. A late provider result must therefore
not regain an audio handoff.

Completed Framework-owned generation-bound artifacts may be invalidated and
become non-playable. Late completion freshness remains owned by the existing
`RealtimeGenerationGate`; no second freshness registry is introduced.

Pending queue clear remains pending-only and must not claim active cancellation.
The internal aggregate controller may return both pending clear and active cancel
results as distinct facts. Duplicate cancel and duplicate flush are idempotent.

### Deferred boundary

```text
provider capability source changed:
False

RealtimeSession real-runtime orchestration changed:
False

host playback coordination / physical playback stop:
DEFERRED / FW-RT6-6e

provider/network/microphone/playback/real VTS execution:
False
```

FW-RT6-6e is not authorized by this Control C candidate.
<!-- FW-RT6-6d-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6e-A-HOST-PLAYBACK-FOUNDATION:BEGIN -->
## FW-RT6-6e Control A — typed playback ownership / host-stop event foundation

### Baseline and scope

```text
baseline HEAD / origin/main:
cff06c92cbf1e25e128c02bcbefcc2cfe98d3125

FW-RT6-6d:
COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED

FW-RT6-6e exact contract review:
COMPLETED

Control A:
AUTHORIZED / IMPLEMENTED-CANDIDATE
```

Control A defines only provider-neutral playback ownership and host-stop event
vocabulary. It does not execute playback, wire `RealtimeSession` to a real
playback coordinator, or promote the legacy local player into the v6 stable API.

### Playback ownership capability

`RealtimeVoiceOutputCapability` adds three additive fields:

```text
playback_ownership:
none | framework | host

host_playback_stop_request_supported:
bool

host_playback_stop_ack_supported:
bool
```

The current app-facing voice-output artifact handoff is host-owned:

```text
playback_ownership:
host

host_playback_stop_request_supported:
True

host_playback_stop_ack_supported:
False
```

`host_playback_stop_request_supported=True` means the public v6 contract can
represent a request to the host when host-owned playback must stop. It does not
mean `RealtimeSession` already emits that request in Control A and it does not
mean physical playback stopped.

Capability invariants:

```text
host stop request supported:
requires playback_ownership = host

host stop ack supported:
requires host stop request supported = True

framework-owned playback:
host stop request/ack support = False
```

### Canonical host-stop events

The canonical v6 event vocabulary adds:

```text
PLAYBACK_STOP_REQUESTED_TO_HOST
= realtime.playback_stop.requested_to_host

PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST
= realtime.playback_stop.acknowledged_by_host
```

Both use `AudioEventPayload`. They intentionally have no v5 projection.

`AudioEventPayload` keeps the existing `host_stop_requested` field and adds:

```text
host_stop_acknowledged:
bool | None
```

`None` means no host acknowledgement fact was supplied. A non-`None`
acknowledgement requires `host_stop_requested=True`.

### Truthfulness boundary

```text
host stop requested
=> physical playback stopped:
NOT IMPLIED

host acknowledgement
=> physical playback stopped:
NOT IMPLIED

artifact invalidated
=> host physical playback stopped:
NOT IMPLIED

host-owned playback
=> FW physical stop success:
MUST NOT BE CLAIMED

framework-owned playback
=> stop success may be claimed:
ONLY FROM AN ACTUAL FW-OWNED PLAYBACK ADAPTER RESULT
```

Host acknowledgement is therefore an optional coordination fact, not a physical
stop-success result.

### Legacy compatibility boundary

The existing `tts.VoiceEngine` still owns provider-specific generation, a local
queue, temporary files, `ffplay`, and process termination. Control A does not
modify or export that path.

```text
legacy VoiceEngine / ffplay classification:
INTERNAL LEGACY COMPATIBILITY

framework root-public:
False

v6 playback capability source:
False

legacy local player deprecation implementation:
DEFERRED / Control B
```

### Deferred runtime adoption

```text
RealtimeSession host-stop emission:
DEFERRED / Control B

host acknowledgement ingestion:
DEFERRED / Control B

FW-owned playback adapter:
DEFERRED / Control B or later exact contract

legacy VoiceEngine isolation/deprecation wiring:
DEFERRED / Control B

physical playback execution in Control A:
False
```

### Control A status

```text
exact Control A surface:
9 files

root-public names:
127 / UNCHANGED

framework.realtime_capabilities exports:
7 / UNCHANGED

framework.realtime_event_payloads exports:
10 / UNCHANGED

FW-RT6-6e tasklist:
0 / 6 CLOSED

Control B:
NOT_AUTHORIZED

provider/network/microphone/playback/real VTS execution:
False

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-6e-A-HOST-PLAYBACK-FOUNDATION:END -->
