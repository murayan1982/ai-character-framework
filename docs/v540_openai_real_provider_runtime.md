# v5.4.0 REQ-4 Lazy OpenAI Real-Provider Runtime

Status:

```text
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: READY pending next small commit
```

## Purpose

REQ-4 adds the first concrete real-provider runtime boundary while preserving
provider-safe root imports and false-by-default execution.

Public symbols:

```text
OpenAIVoiceInputPrivateCredential
OpenAIVoiceInputRuntimeMode
OpenAIVoiceInputRealProviderStatus
OpenAIVoiceInputRealProviderPolicy
OpenAIVoiceInputRealClientFactory
OpenAIVoiceInputRealProviderExecutor
```

## Official SDK call shape

The runtime is built around the official synchronous Python client shape:

```text
OpenAI(
    api_key=<private explicit value>,
    timeout=<explicit seconds>,
    max_retries=<explicit count>,
)

client.audio.transcriptions.create(
    model=<explicit model>,
    file=<sanitized audio.wav file object>,
    language=<optional language>,
)
```

The Framework does not read `OPENAI_API_KEY` or any other credential environment
variable. A non-empty `OpenAIVoiceInputPrivateCredential` must be provided
explicitly, and its representation is redacted.

The optional OpenAI SDK is not added to the default import path by REQ-4. It is
resolved lazily with `module_importer("openai")` only after every gate passes.
An unavailable SDK returns a typed public-safe unavailable result.

## Independent explicit gates

All defaults are false:

```text
allow_provider_sdk_import=False
allow_provider_client_creation=False
allow_real_provider_execution=False
```

A positive `max_audio_bytes`, positive timeout, and non-negative retry count are
also required.

The runtime rejects direct clients and arbitrary client factories. Concrete
execution requires `OpenAIVoiceInputRealClientFactory`.

## Audio and result boundary

After every explicit execution gate passes, the executor:

1. reuses the accepted REQ-2 FILE_PATH/WAV/duration preflight;
2. rejects missing, non-regular, empty, and oversized files;
3. verifies the opened descriptor remains a regular file;
4. reads at most `max_audio_bytes + 1`;
5. hands a sanitized in-memory `audio.wav` object to the client;
6. normalizes transcript text and language;
7. returns only public-safe metadata.

Private paths, raw audio, credential values, provider payloads, and provider
exception strings are never copied into the public result.

## Provider error normalization

```text
APITimeoutError -> provider_timeout / retryable
RateLimitError -> provider_rate_limited / retryable
APIConnectionError -> provider_connection_error / retryable
AuthenticationError -> provider_authentication_error / not retryable
other provider exception -> provider_error / not retryable
```

No exception text is exposed.

## REQ-4 verification mode

REQ-4 smoke injects an SDK test double through the module importer. It verifies:

```text
private credential forwarding
OpenAI constructor arguments
client.audio.transcriptions.create(...) call shape
bounded audio handoff
transcript normalization
timeout and rate-limit mapping
secret/path/audio/payload non-exposure
```

It does not import the actual OpenAI SDK, create an actual provider client, use a
real credential, or execute a network request.

```text
actual OpenAI SDK imported in smoke: false
actual provider client created in smoke: false
real provider execution in smoke: false
microphone access: false
DRC repository change: false
```

REQ-4 is accepted after its full verification command set, exact
eleven-file diff review, test-double execution evidence review, and
explicit operator approval passed. REQ-5 may begin only in the next
small commit.
