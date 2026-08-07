# AI Character Framework v6.0.0 — Realtime text-generation provider adapter contract

## FW-RT6-5b Control A

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Baseline:

```text
HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

FW-RT6-5a:
COMPLETED / VERIFIED / ACCEPTED

root-public names:
127 / UNCHANGED
```

### Adapter boundary

FW-RT6-5b does not mutate the legacy `BaseLLM.ask_stream()` compatibility
path.  The v6 provider path implements the accepted
`CancelableTextGenerationStage` / `TextGenerationStream` boundary with
explicitly injected clients. Importing Framework or this adapter module does
not import provider SDKs, inspect credentials, construct clients, or execute
network requests.

Control A introduces:

```text
OpenAITextGenerationAdapter
XAITextGenerationAdapter
TextGenerationProviderError
```

The adapter classes live in the explicit module
`framework.realtime_text_generation_provider_adapters`.
`TextGenerationProviderError` is additive to the stable
`framework.realtime_text_generation` package but remains outside the Framework
root-public manifest.

### Injected OpenAI-compatible client

OpenAI and xAI Control A adapters use an injected client with the
OpenAI-compatible `client.chat.completions.create(...)` streaming shape.  The
adapter itself never imports `openai`, reads an API key, or constructs that
client. Tests use deterministic fake clients only.

```text
provider SDK import during framework import:
False

credential lookup during framework import:
False

real client creation during Control A tests:
False

network execution:
False
```

### Transactional committed history

The adapter owns Framework-side committed history. Opening a stream builds the
provider request from:

```text
committed history snapshot
+ current user input
```

It does not mutate committed history at stream start. The existing
`ProviderNeutralTextGenerationStream` commits one
`TextGenerationCompletedTurn` only after normal source exhaustion and cleanup.
The history sink atomically appends the user + full delivered clean assistant
pair exactly once for one session/turn/generation context.

```text
normal completion:
user + assistant pair committed exactly once

cancel:
history mutation = 0

source failure:
history mutation = 0

early close:
history mutation = 0
```

Emotion tags are delivery metadata only. Completed assistant history uses the
clean text actually delivered by the provider-neutral stream.

### Cooperative cancellation and hard-cancel truthfulness

The same `TextGenerationCancellationToken` supplied to `open_stream()` is
owned by the returned stream. The accepted FW-RT6-5a future-delta suppression
remains authoritative. Provider resource close is not claimed as verified
transport hard cancellation.

```text
OpenAI provider_hard_cancel_supported:
False

xAI provider_hard_cancel_supported:
False

canonical hard-cancel source:
TextGenerationCapability.provider_hard_cancel_supported
```

### Safe provider exception mapping

`TextGenerationProviderError` contains only:

```text
public_error_code
safe_message
retryable
public_metadata
```

It reuses `classify_public_exception()` and never retains raw provider exception
text, repr, response body, request payload, credential material, or a public
exception cause.

```text
TimeoutError:
timeout / retryable

PermissionError:
authentication_required / not retryable

ConnectionError:
provider_unavailable / retryable

other provider failure:
provider_request_failed / retryable

raw provider exception public:
False
```

### Control A boundaries

```text
OpenAI fake stream:
PASS expected

xAI fake stream:
PASS expected

OpenAI normal history:
exactly once expected

OpenAI cancelled history:
0 expected

xAI normal history:
exactly once expected

provider hard-cancel overclaim:
False

Gemini adapter:
DEFERRED / Control B

fallback adapter:
DEFERRED / Control B

router adapter:
DEFERRED / Control B

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

<!-- FW-RT6-5b-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-5b Control A acceptance sync

```text
checkpoint:
FW-RT6-5b Control A

status:
COMPLETED / VERIFIED / ACCEPTED

exact Control A delta:
9 files

combined working-tree surface:
38 files

focused provider-adapter tests:
20 / PASS

full unit suite at acceptance:
213 / PASS

OpenAI / xAI:
cancel-aware adapters / ACCEPTED

next checkpoint:
FW-RT6-5b Control B authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5b-A-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-5b Control B

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

### Gemini stateless transactional adapter

Control B adds `GeminiTextGenerationAdapter` using only an explicitly injected
client. The adapter does not import the Google SDK, inspect credentials, or use
`client.chats.create()` / provider-owned mutable chat state.

Each stream request is reconstructed from Framework-owned committed history:

```text
committed user/model pairs
+ current user input
```

The injected client boundary is:

```text
client.models.generate_content_stream(
    model=...,
    contents=...,
    config=...,
)
```

Normal exhaustion atomically commits the current user + full clean assistant
pair once. Cancel, source failure, or early close commits no incomplete turn.

```text
provider-owned chat rollback dependency:
False

partial/cancelled provider state reused:
False

Gemini provider_hard_cancel_supported:
False / truthful
```

### Pre-delta-only fallback

Control B adds `FallbackTextGenerationAdapter`. The primary and fallback stages
receive the exact same `RealtimeStageContext` and the exact same
`TextGenerationCancellationToken`.

```text
primary failure before first delivered delta:
fallback MAY start

primary failure after first delivered delta:
fallback MUST NOT start

cancellation requested:
fallback MUST NOT start

automatic mixed primary + fallback answer:
False
```

The fallback stage capability is the conservative minimum of all candidate
stages. Provider resource cleanup remains separate from verified transport hard
cancellation.

### Single-selection router

Control B adds `RouterTextGenerationAdapter`. Route selection runs exactly once
before the selected child stream opens. The selected child receives the same
context and cancellation token.

```text
route selection per stream:
1

route replacement during stream:
False

router cancel:
selected child / same token

router capability:
conservative minimum across candidates
```

### Control B safety boundary

The provider-adapter module still imports no provider SDK, reads no credentials,
constructs no real client, and executes no network request during Control B
tests. Gemini/OpenAI/xAI hard-cancel remains `False` unless later verified by a
real provider-specific capability contract.

```text
root-public names:
127 / UNCHANGED

provider SDK import:
False

real provider execution:
False

network execution:
False

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```



<!-- FW-RT6-5b-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-5b Control B acceptance sync

```text
checkpoint:
FW-RT6-5b Control B

status:
COMPLETED / VERIFIED / ACCEPTED

exact Control B delta:
6 files

combined working-tree surface:
40 files

focused provider-adapter tests:
41 / PASS

full unit suite at acceptance:
234 / PASS

Gemini / fallback / router:
cancel-aware adapters / ACCEPTED

next checkpoint:
FW-RT6-5b Control C authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5b-B-ACCEPTANCE-SYNC:END -->

---

<!-- FW-RT6-5b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-5b Control C aggregate acceptance candidate

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Control C introduces no new provider runtime implementation. It closes the
accepted Control A/B adapter work with deterministic fake-provider aggregate
acceptance, truthful capability checks, public-safety checks, and tasklist sync.

```text
OpenAI fake stream:
PASS

Gemini fake stream:
PASS

xAI fake stream:
PASS

direct-provider cancellation future delta delivery:
0

fallback pre-delta failure:
fallback starts

fallback post-delta failure:
fallback does not start

fallback cancellation:
fallback does not start

router selection:
once per stream

router cancellation:
same selected child token

session / turn / generation correlation:
PASS

raw provider exception public:
False

provider hard-cancel source:
TextGenerationCapability.provider_hard_cancel_supported

provider hard-cancel overclaim:
False

root-public names:
127 / UNCHANGED
```

The acceptance suite uses only deterministic injected fake clients/stages. No
provider SDK import, credential lookup, real client creation, provider request,
network execution, microphone access, playback execution, or real VTS
execution is performed.

```text
next checkpoint:
FW-RT6-5c / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5b-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-5b-C-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-5b aggregate acceptance sync

```text
checkpoint:
FW-RT6-5b Control C

status:
COMPLETED / VERIFIED / ACCEPTED

exact Control C delta:
6 files

combined accepted working-tree surface:
42 files

focused provider aggregate tests at acceptance:
51 / PASS

full unit suite at acceptance:
244 / PASS

all seven FW-RT6-5b tasks:
ACCEPTED

root-public names:
127 / UNCHANGED

next checkpoint:
FW-RT6-5c Control A authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5b-C-ACCEPTANCE-SYNC:END -->
