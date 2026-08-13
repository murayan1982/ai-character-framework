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
