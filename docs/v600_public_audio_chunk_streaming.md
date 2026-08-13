# Public audio chunk streaming contract

FW-RT6-12a Control A defines the provider-neutral public vocabulary for host
audio chunk input. The stable explicit namespace is
`framework.voice_input_streaming`; the frozen 127-name Framework root is not
expanded.

This control is a data-contract foundation only. It does not add a streaming
method to `VoiceInputSession` or `RealtimeSession`, create an input queue, emit
partial transcripts, read audio, open a microphone, import a provider SDK, or
execute a provider or network call.

<!-- FW-RT6-12a-A-PUBLIC-AUDIO-CHUNK:BEGIN -->
## Stable explicit namespace

```python
from framework.voice_input_streaming import (
    VoiceInputAudioChunk,
    VoiceInputStreamAbort,
    VoiceInputStreamConfig,
    VoiceInputStreamEnd,
    VoiceInputStreamOperationResult,
    VoiceInputStreamRejectionCode,
    VoiceInputStreamingCapability,
)
```

`VOICE_INPUT_STREAMING_API_VERSION` is `6.0`. The module exposes exactly nine
names through `__all__`. None is exported from the `framework` root.

## Stream format and capability

`VoiceInputStreamConfig` binds one opaque `stream_id` to the existing
provider-neutral `VoiceInputAudioFormat`. Streaming requires an explicit
encoding; `UNKNOWN` is rejected. The host continues to own capture and raw
audio lifetime.

`VoiceInputStreamingCapability` truthfully reports:

- whether audio chunk input is supported;
- accepted `VoiceInputAudioEncoding` values;
- maximum chunk size in bytes;
- maximum stream duration in milliseconds;
- end-of-input, abort, partial-transcript, and final-transcript support.

The default capability is entirely unsupported. A supported snapshot must
declare at least one format, both finite limits, end-of-input support, and
final-transcript support. This model does not change the current runtime
capability snapshot, which still reports audio chunk input as unsupported.

## Ordering

`VoiceInputAudioChunk.sequence_number` is zero-based. A future stream owner
must accept only the next expected number; it must not reorder, infer, or
silently drop chunks. `VoiceInputStreamEnd.sequence_number` is the next
expected number after the last chunk and is therefore part of the ordered
input sequence.

`VoiceInputStreamAbort` is an out-of-band host request. It does not consume a
sequence number and does not claim provider hard cancellation. Its optional
`last_sequence_number` is correlation context, not an acknowledgement that the
provider consumed that chunk.

## Typed operation result

`VoiceInputStreamOperationResult` is the future acknowledgement/rejection
shape. `VoiceInputStreamRejectionCode` includes stable provider-neutral codes
for unsupported input, invalid identifiers or formats, empty or oversized
chunks, duration overflow, out-of-order input, ended/aborted streams, and
closed sessions.

Control A defines these result types but does not attach them to a session.
Malformed/out-of-order runtime rejection, partial transcript event delivery,
queue/backpressure behavior, and final transcript orchestration remain later
controls. Constructors still reject structurally invalid values immediately.

## Privacy and execution boundary

`VoiceInputAudioChunk.data` is explicit host input. It is excluded from
`repr(...)` and from `as_dict()`; the safe projection contains only byte count,
sequence, duration, and public-safe metadata. No error or result model retains
raw audio, provider objects, exceptions, credentials, or private paths.

```text
checkpoint: FW-RT6-12a Control A
baseline head: d5e707fa4bca34322b9a2319696273b129b6f395
exact implementation surface: 6 files
stable namespace: framework.voice_input_streaming
namespace exports: 9 / EXACT
root-public names: 127 / UNCHANGED
session/runtime streaming method added: False
current runtime audio_chunk_input_supported: False / UNCHANGED
audio queue/backpressure added: False
partial transcript event delivery added: False
provider/network/audio-read/microphone/playback/real VTS execution: False
FW-RT6-12a tasks: 0 / 7 CLOSED
Control B: NOT_AUTHORIZED
aggregate acceptance: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-12a-A-PUBLIC-AUDIO-CHUNK:END -->

<!-- FW-RT6-12a-B-VOICE-INPUT-STREAMING:BEGIN -->
## Control B VoiceInputSession adoption

Control B attaches the accepted vocabulary to `VoiceInputSession` without
changing the root-public inventory or `create_voice_input_session(...)`
signature. Applications explicitly configure an adapter, begin one stream,
send ordered chunks, then end or abort it:

```python
from framework import create_voice_input_session
from framework.voice_input_audio import VoiceInputAudioEncoding, VoiceInputAudioFormat
from framework.voice_input_streaming import (
    VoiceInputAudioChunk,
    VoiceInputStreamConfig,
    VoiceInputStreamEnd,
)
from framework.voice_input_streaming_adapter import (
    DeterministicFakeVoiceInputStreamingAdapter,
)

session = create_voice_input_session()
session.configure_audio_streaming(
    DeterministicFakeVoiceInputStreamingAdapter(
        partial_transcripts={0: "途中"},
        final_transcript="最終 transcript",
    )
)
session.begin_audio_stream(
    VoiceInputStreamConfig(
        stream_id="host_stream_1",
        audio_format=VoiceInputAudioFormat(
            encoding=VoiceInputAudioEncoding.PCM16,
            sample_rate_hz=16_000,
            channel_count=1,
        ),
    )
)
session.send_audio_chunk(
    VoiceInputAudioChunk(
        stream_id="host_stream_1",
        sequence_number=0,
        data=b"...",
        duration_ms=20,
    )
)
session.end_audio_input(
    VoiceInputStreamEnd(stream_id="host_stream_1", sequence_number=1)
)
```

`framework.voice_input_streaming_adapter` is an explicit-only, provider-safe
namespace with exactly two exports: the structural
`VoiceInputStreamingAdapter` protocol and the offline deterministic fake.
The default `VoiceInputSession.streaming_capability` remains fully unsupported.
Support becomes true only after an explicit adapter whose truthful capability
passes validation is installed.

Framework, not the adapter, owns stream identity, strict next-sequence
admission, maximum chunk bytes, cumulative duration, terminal state, and typed
rejection. Every admitted chunk must supply positive `duration_ms`; missing or
over-limit duration is rejected without consuming the expected sequence.
There is no queue, silent drop, pause/resume, or retry budget in Control B.

Partial observations use the already accepted canonical
`RealtimeEventType.TRANSCRIPT_PARTIAL` plus `TranscriptEventPayload` with
`is_final=False`. They carry the same session/turn/generation as the stream and
are intentionally absent from the v5 mapping callback. Accepted end-of-input
emits one `TRANSCRIPT_FINAL`, stores the correlated `last_stream_result`, and
retires the generation. Late partial callbacks after end/abort are ignored.

Abort is cooperative Framework/adapter invalidation only. It does not prove a
provider hard cancel or that application-owned capture physically stopped.
Closing the session aborts the private stream state and post-close chunk/end/
abort calls return typed `session_closed` results.

`RealtimeSession` and the global/session realtime capability snapshot remain
unchanged in this control. Unified turn orchestration is not inferred from the
standalone voice-input boundary. The Framework root remains exactly 127 names.

```text
checkpoint: FW-RT6-12a Control B
baseline head: f07105742ea6068a6d1655d737c160a5f3487dd5
exact Control B surface: 10 files
VoiceInputSession streaming adoption: IMPLEMENTED / AWAITING_REVIEW
explicit adapter namespace exports: 2 / EXACT
default streaming support: False / TRUTHFUL
configured fake streaming support: True / PROVIDER-FREE
strict chunk sequence: PASS expected
format/chunk/duration validation: PASS expected
partial transcript canonical event: PASS expected
partial transcript v5 mapping: NONE
final transcript event/result: PASS expected
input abort hard-cancel claim: False
RealtimeSession streaming methods: False / UNCHANGED
root-public names: 127 / UNCHANGED
backpressure: DEFERRED_TO_FW-RT6-12b
provider/network/audio-file/microphone/playback/real VTS execution: False
FW-RT6-12a tasks: 0 / 7 CLOSED
Control B acceptance sync: NOT_AUTHORIZED
aggregate acceptance: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-12a-B-VOICE-INPUT-STREAMING:END -->
