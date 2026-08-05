# AI Character Framework v6.0.0 Detailed Realtime Capability Contract

<!-- FW-RT6-1d-A-DETAILED-CAPABILITY-MODELS:BEGIN -->
## FW-RT6-1d Control A — detailed capability model vocabulary

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Baseline:

```text
4709f0190f3779b83b8cb01a0cd67f6760ff8e35
```

Control A adds a provider-neutral, import-safe v6 capability vocabulary. It does
not replace the existing v5.1 `FrameworkCapabilities` builder and does not yet
attach a snapshot to `RealtimeSession`.

Root-public additions:

```text
CapabilitySnapshotScope
RuntimeCapabilityState
TextGenerationCapability
RealtimeVoiceInputCapability
RealtimeVoiceOutputCapability
RealtimeMotionCapability
RealtimeCapabilitySnapshot
```

`RuntimeCapabilityState` separates the following facts:

```text
configured
runtime_available
guarded
fake_runtime
real_runtime
unavailable_reason
```

Fake and real runtime selection are mutually exclusive. A selected fake or real
runtime must be reported as runtime-available. `usable` additionally requires a
complete configuration and an open execution guard.

Detailed stage contracts:

```text
text generation:
streaming_supported
cooperative_cancel_supported
provider_hard_cancel_supported

voice input:
audio_chunk_input_supported
partial_transcript_supported
final_transcript_supported
input_abort_supported
backpressure_supported
accepted_audio_formats
maximum_chunk_size
maximum_duration

voice output:
streaming_audio_supported
generation_cancel_supported
provider_hard_cancel_supported
pending_flush_supported
active_audio_invalidation_supported
audio_formats
maximum_text_size

motion:
request_cancel_supported
completion_event_supported
provider_neutral_intent_supported
```

`RealtimeCapabilitySnapshot` carries a scope, positive snapshot generation,
optional global or required session identity, all four detailed stage models,
and the established v5 summary booleans as compatibility fields. The new schema
identifier is `v6.realtime_capabilities`; the frozen v5.1 capability schema
identifier remains unchanged.

```text
accepted root-public prefix: 114 names / SAME ORDER
canonical root-public total: 121
FrameworkCapabilities implementation replaced: False
get_capabilities detailed aggregation: False
RealtimeSession snapshot adoption: False
process environment inspection: False
credential/private config read: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1d Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1d-A-DETAILED-CAPABILITY-MODELS:END -->

<!-- FW-RT6-1d-B-GLOBAL-CAPABILITY-AGGREGATION:BEGIN -->
## FW-RT6-1d Control B — truthful global capability aggregation

`get_capabilities()` preserves the v5.1 `FrameworkCapabilities` return type,
keyword-only signature, five summary fields, and `v5.1.capabilities` schema. The
builder no longer reports voice input, realtime, and motion as missing public
boundaries. Their deterministic mock-safe public runtimes are reported as
available fallback capabilities, while real provider or transport success is not
claimed.

The additive `FrameworkCapabilities.realtime_snapshot` field contains one
`v6.realtime_capabilities` global snapshot built from the same authoritative
facts. It separates configured, runtime availability, guard state, fake runtime,
real runtime, and unavailable reason for every stage.

```text
checkpoint: FW-RT6-1d Control B
baseline head: a27b3e17ff7d8158859a5a624e3b03225384bfc8
Control B exact change surface: 10 files
root-public names: 121 / UNCHANGED
v5 compatibility schema: v5.1.capabilities / PRESERVED
detailed schema: v6.realtime_capabilities
voice input summary reason: mock_voice_input_available
realtime summary reason: mock_realtime_available
motion summary reason: mock_motion_available
voice output real runtime default: UNAVAILABLE
provider hard cancel supported: False
TTS pending flush supported: False
RealtimeSession snapshot adoption: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1d Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1d-B-GLOBAL-CAPABILITY-AGGREGATION:END -->
