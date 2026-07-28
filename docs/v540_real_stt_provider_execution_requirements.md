# v5.4.0 Candidate Real STT Provider Execution Requirements

Status:

```text
requirements definition: ACCEPTED
implementation: NOT_STARTED
private real-provider acceptance: NOT_STARTED
release readiness: BLOCKED pending implementation acceptance
```

## Purpose

This document defines the next Framework development requirements for explicit real STT provider execution through the public Voice Input API.

The immediate driver is DRC v3.0.0 RT-3d, which is blocked until Framework can execute a real STT provider through public APIs and return a provider-neutral typed transcript.

This document is a requirements definition checkpoint only. It does not select a final provider, model, SDK, release date, or private acceptance environment.

## Baseline

The current accepted Framework baseline is v5.3.0.

v5.3.0 already provides:

- public `VoiceInputRequest` / `VoiceInputResult`;
- public `VoiceInputSession`;
- public `VoiceInputAudioSource` and related host-audio source types;
- public `VoiceInputProviderAdapter` and `VoiceInputProviderAdapterInfo`;
- `FakeVoiceInputProviderAdapter`;
- `GuardedRealVoiceInputProviderAdapter`;
- provider-safe `import framework`;
- fake and guarded paths that do not read audio, access microphones, or execute real providers.

These contracts must remain backward compatible.

## DRC-driven target path

The target public path is:

```text
DRC private staged WAV
-> FW public VoiceInputAudioSource
-> FW public VoiceInputSession
-> public real-provider adapter
-> concrete real STT provider
-> provider-neutral VoiceInputResult
-> DRC text handoff
```

DRC must not import Framework internal modules, provider-specific clients, or private adapter implementations directly.

## Requirements

### FW-REQ-1: Public API real STT execution

Framework must allow host-owned audio represented by `VoiceInputAudioSource` to be passed through public `VoiceInputSession` and a public provider adapter into a real STT provider. The result must be a provider-neutral `VoiceInputResult`.

### FW-REQ-2: Explicit execution permission

Real STT execution must require all relevant gates before opening audio, creating clients, or calling a provider:

- real STT enabled;
- provider execution explicitly allowed;
- provider configured;
- credentials available;
- supported audio source;
- input size and duration within limits;
- session is not closed.

If a gate fails, Framework must return a typed provider-neutral result without reading audio, creating a client, or calling a provider.

### FW-REQ-3: Lazy provider runtime

Provider SDKs, provider clients, and credential resolution must not run during:

- `import framework`;
- fake adapter usage;
- capability probe;
- preflight failure;
- execution not allowed;
- credential missing;
- unsupported provider;
- unsupported source.

Provider runtime may only be resolved after all explicit execution gates pass.

### FW-REQ-4: Injectable client or client factory

Framework must provide a testable boundary for injecting a fake real-provider client or client factory.

The injected client path must verify without network access:

- provider call shape;
- model/config arguments;
- audio file handoff;
- transcript normalization;
- provider error normalization;
- timeout/rate-limit mapping;
- execution metadata;
- secret/path/payload non-exposure.

### FW-REQ-5: Safe FILE_PATH audio resolution

The first DRC integration path requires backend-owned temporary WAV files.

Framework must safely validate `VoiceInputAudioSourceKind.FILE_PATH` before real provider execution:

- source kind is explicitly supported;
- file exists;
- path resolves to a normal file;
- file is not empty;
- format is supported;
- file size is within the maximum;
- duration is within the maximum when duration metadata is available;
- file is not opened before execution gates pass;
- private file path is not exposed in public result metadata.

### FW-REQ-6: Success normalization

A successful provider response must be normalized into public `VoiceInputResult` data. Provider-native request/response payloads must not be returned directly.

The public result should include:

- outcome;
- text;
- language;
- duration, when known;
- confidence, when available;
- safe public metadata;
- whether provider execution ran;
- whether STT execution ran.

The public result must not include credentials, authorization headers, raw audio, base64 audio, private file paths, provider clients, full provider request payloads, or full provider response payloads.

### FW-REQ-7: Error normalization

Framework must map real-provider failures to provider-neutral public results.

At minimum, it must distinguish real STT disabled, execution not allowed, provider not configured, credentials missing, unsupported provider, unsupported source, file not found, empty or invalid audio, file size exceeded, duration exceeded, authentication error, rate limit, timeout, temporary provider failure, permanent provider failure, transcript missing, interrupted, cancelled, and session closed.

Provider exception text and HTTP payloads must not be exposed as public safe messages.

### FW-REQ-8: Capability and status honesty

Capability/status APIs must honestly report whether real STT is disabled, blocked by missing execution permission, blocked by missing credentials, blocked by unsupported provider, blocked by unsupported source, blocked by missing dependency, provider unavailable, not implemented, or configured and available.

Once real execution is implemented, a configured available provider path must no longer always return `REAL_STT_NOT_IMPLEMENTED`.

### FW-REQ-9: Lifecycle events

The public real STT path must expose enough state for host apps such as DRC to show safe UI status.

Required states or equivalent public events:

- started;
- validating;
- provider execution started;
- completed;
- unavailable;
- failed;
- interrupted;
- cancelled;
- closed.

Event payloads must not include secrets, raw audio, private file paths, provider clients, or provider payloads.

### FW-REQ-10: Interrupt / cancel boundary

Framework must define the public interrupt/cancel behavior for real STT execution.

If the first implementation cannot guarantee hard provider cancellation, the guarantee and limitation must be documented and tested.

### FW-REQ-11: Public DRC handoff acceptance

Framework must verify this path using only public APIs:

```text
DRC host capture
-> DRC private temporary WAV
-> VoiceInputAudioSource
-> public VoiceInputSession
-> public real-provider adapter
-> real STT provider
-> typed VoiceInputResult
-> DRC text handoff
```

Framework internal imports, DRC-specific private APIs, and DRC direct provider client usage are not allowed.

## Non-goals for the initial real-provider execution scope

The initial scope does not automatically include Framework-owned microphone recording, always-on microphone, wake word, continuous streaming STT, partial transcript UI, diarization, translation, noise suppression, audio editing, cloud storage, multiple provider implementations, URL audio download, opaque ID resolution inside Framework, or DRC-specific private APIs.

## DRC responsibilities that stay outside Framework

DRC remains responsible for microphone permission, recording lifecycle, recording duration limit, private WAV creation, private artifact management, mobile-to-backend transfer, backend private staging, cleanup, UI state, retry/cancel UI, private operator evidence management, and passing transcript into DRC conversation logic.

## Acceptance plan

### Source / mock acceptance

Source and mock acceptance must pass before any private real-provider execution is claimed:

- provider-safe `import framework`;
- fake adapter compatibility;
- injected fake client verifies provider call shape;
- no audio read before gates pass;
- no client creation before gates pass;
- no provider call before gates pass;
- FILE_PATH validation;
- transcript normalization;
- provider error normalization;
- secret/path/payload non-exposure;
- capability/status honesty;
- close/interrupt behavior;
- v5.2.0 and v5.3.0 accepted gates remain passing.

### Private real-provider acceptance

Private real-provider acceptance must be operator-only and must not commit private evidence.

It must verify private credentials are not committed, a private WAV is used, explicit execution opt-in is used, real provider call succeeds, a real transcript is obtained, result is provider-neutral, public logs omit secrets/private paths/raw audio/provider payloads, private audio and evidence stay outside the repository, and cleanup is verified.

### DRC integration acceptance

DRC adoption may proceed only after a released Framework artifact is available.

It must verify DRC imports Framework public APIs only, DRC private WAV can be handed to Framework, real transcript can be received, timeout/cancel/error can be reflected safely in UI, fake path remains available, backend and Flutter tests pass, and RT-3d can be unblocked without DRC-owned provider-specific clients.

## DRC restart gate

DRC RT-3d must remain blocked until all of the following are accepted or completed:

```text
FW requirements definition: ACCEPTED
FW implementation: ACCEPTED
FW private real-provider acceptance: ACCEPTED
FW release readiness: ACCEPTED
FW fixed release package: ACCEPTED
FW tag and GitHub Release: COMPLETED
DRC released-FW adoption gate: ACCEPTED
```

DRC must not unblock RT-3d using unreleased Framework code, Framework internals, or DRC-owned provider-specific STT clients.
## REQ-1 implementation checkpoint

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: READY pending next small commit
```

REQ-1 implements the provider execution configuration and status foundation
defined by REQ-0.

The new v5.4 boundary is explicit-only and separate from the existing v5.2
`VoiceInputProviderConfig` resolver. It accepts a provider name, an explicit
execution opt-in, and credential availability as a boolean assertion. It does
not inspect credential values or process environment.

Capability reasons are fixed as:

```text
provider_execution_not_allowed
provider_not_configured
credentials_unavailable
provider_execution_not_implemented
```

Implementation details and the acceptance command set are in
[`v540_provider_execution_configuration_status.md`](v540_provider_execution_configuration_status.md).

REQ-1 acceptance authorizes REQ-2 to begin in the next small commit. It does
not itself authorize provider SDK import, client creation, provider execution,
credential-value read, audio read, microphone access, private provider
acceptance, DRC change, package build, or tag creation.
## REQ-2 implementation checkpoint

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: READY pending next small commit
```

REQ-2 implements the provider-specific adapter/config/client-injection
contract authorized by REQ-1.

The selected adapter is `OpenAIVoiceInputProviderAdapter`. It exposes an
explicit model, direct client injection, client-factory injection, typed
preflight states, and FILE_PATH/WAV/bounded source-metadata validation.

The structural provider boundary is
`client.audio.transcriptions.create(...)`, but no client or factory is
resolved and no provider call is executed in REQ-2.

Details and verification commands are in
[`v540_openai_adapter_client_injection_contract.md`](v540_openai_adapter_client_injection_contract.md).

REQ-2 does not authorize an OpenAI SDK dependency, environment credential
resolution, credential-value access, audio-file opening, provider execution,
microphone access, private evidence, DRC changes, package creation, or tags.
## REQ-3 implementation checkpoint

```text
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: READY pending next small commit
```

REQ-3 implements bounded FILE_PATH reading and execution against a directly
injected client that inherits `OpenAIVoiceInputFakeClientMarker`.

It requires explicit fake-execution opt-in and an explicit `max_audio_bytes`
bound. It rejects client factories, unmarked clients, unsupported sources,
non-regular files, and oversized reads.

REQ-3 authorizes only fake provider-protocol execution in its isolated smoke.
It does not authorize an OpenAI SDK dependency, credential-value access,
provider-client creation, real provider execution, microphone access, DRC
changes, private provider evidence, release packages, or tags.
