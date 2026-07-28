# v5.4.0 REQ-3 Bounded Audio / Fake Execution Boundary

Status:

```text
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: READY pending next small commit
```

## Purpose

REQ-3 proves the provider-shaped execution path without contacting a real
provider. It adds:

```text
OpenAIVoiceInputFakeClientMarker
OpenAIVoiceInputFakeExecutionPolicy
OpenAIVoiceInputFakeExecutionStatus
OpenAIVoiceInputFakeExecutor
```

## Required guards

Fake execution requires all of the following:

```text
REQ-2 adapter preflight is ready_not_executed
directly injected client
client inherits OpenAIVoiceInputFakeClientMarker
allow_fake_client_execution=True
explicit positive max_audio_bytes
FILE_PATH / WAV / duration-bound source contract
regular file
file size and actual read remain within max_audio_bytes
```

Client factories remain disabled and are never invoked.

## Execution behavior

A successful REQ-3 call:

1. inspects the host path without publishing it;
2. rejects non-regular files;
3. enforces `max_audio_bytes` before and during the read;
4. reads bounded bytes;
5. places them in a sanitized in-memory `audio.wav` object;
6. calls the marked fake client's
   `client.audio.transcriptions.create(...)`;
7. converts only safe transcript fields into `VoiceInputResult`.

Exceptions are converted into a generic typed failure. Exception strings,
source paths, raw audio, and provider payloads are not exposed.

Public result metadata records the fake-only call boundary explicitly:

```text
fake_provider_protocol_call_executed: true only after the marked fake
client method was invoked
real_provider_execution_executed: false
```

## Explicit non-goals

```text
OpenAI SDK import: false
environment credential resolution: false
credential value read: false
client factory invocation: false
provider client creation: false
real provider execution: false
microphone access: false
DRC repository change: false
release package/tag: false
```

The smoke test creates and removes a small temporary WAV-like file. That is
the only audio read authorized by REQ-3 verification.

REQ-3 is accepted after the complete command set, exact ten-file diff
review, bounded temporary-file execution evidence review, and explicit
operator approval passed. REQ-4 may begin only in the next small commit.
