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
