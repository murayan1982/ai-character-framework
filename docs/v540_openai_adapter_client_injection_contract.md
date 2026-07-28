# v5.4.0 REQ-2 OpenAI Adapter/Client-Injection Contract

Status:

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

## Purpose

REQ-2 adds the first concrete provider-specific adapter contract:

```text
OpenAIVoiceInputProviderAdapter
```

It defines configuration, model, injected-client, injected-client-factory,
source-metadata, and typed-preflight boundaries without executing OpenAI STT.

## Public symbols

```text
OpenAIVoiceInputClient
OpenAIVoiceInputClientFactory
OpenAIVoiceInputPreflight
OpenAIVoiceInputPreflightStatus
OpenAIVoiceInputProviderAdapter
```

The structural client boundary reserved for later execution is:

```text
client.audio.transcriptions.create(...)
```

REQ-2 defines this shape only. It does not call `create(...)`.

## Constructor contract

```text
execution_config: VoiceInputProviderExecutionConfig
model: explicit non-secret string
client: optional injected OpenAIVoiceInputClient
client_factory: optional injected OpenAIVoiceInputClientFactory
public_metadata: redacted public-only metadata
```

Exactly one of `client` or `client_factory` is required for a ready contract.
Neither is automatically resolved. A factory is never invoked by REQ-2.

API keys, tokens, credential objects, credential paths, authorization headers,
provider clients, and provider payloads are not accepted as public metadata.

## Initial source contract

Source preflight accepts metadata for:

```text
VoiceInputAudioSourceKind.FILE_PATH
VoiceInputAudioEncoding.WAV
explicit max_duration_ms
declared duration <= max_duration_ms when duration is present
```

The adapter does not open, stat, resolve, upload, or otherwise read the path.

Opaque IDs, URLs, non-WAV formats, and unbounded sources remain unsupported.

## Typed preflight states

```text
provider_execution_not_allowed
provider_not_configured
unsupported_provider
credentials_unavailable
model_not_configured
client_configuration_conflict
client_not_configured
source_required
unsupported_source
unsupported_audio_format
source_not_bounded
source_duration_exceeds_bound
ready_not_executed
```

`ready_not_executed` means declarations are complete. It does not mean that
audio was read, a client was created, a provider call was made, or STT is
available.

## Safety record

```text
OpenAI SDK imported: false
client factory invoked: false
provider client created: false
credential values read: false
audio path exposed: false
audio read: false
microphone accessed: false
provider execution executed: false
DRC repository changed: false
```

## Changed files

```text
README.md
framework/__init__.py
framework/openai_voice_input_provider_adapter.py
docs/v540_openai_adapter_client_injection_contract.md
docs/v540_provider_execution_configuration_status.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/smoke_v540_provider_execution_configuration_status.py
scripts/smoke_v540_openai_adapter_client_injection_contract.py
```

## Verification

```powershell
python -m compileall -q framework core stt scripts examples

python scripts\smoke_v540_openai_adapter_client_injection_contract.py
python scripts\smoke_v540_provider_execution_configuration_status.py
python scripts\smoke_v540_real_stt_provider_execution_requirements.py

python scripts\smoke_v530_release_package_gate.py
python scripts\smoke_v530_release_readiness_gate.py
python scripts\smoke_v530_guarded_real_provider_adapter.py
python scripts\smoke_v530_drc_public_handoff_verification.py

python scripts\smoke_v520_voice_input_public_contract_conformance_gate.py
python scripts\smoke_v520_release_readiness_gate.py
```

REQ-2 is accepted after the complete command set, exact nine-file diff
review, provider-safe lazy-export review, and explicit operator approval
passed. REQ-3 may begin only in the next small commit.
## REQ-3 dependent checkpoint

REQ-2 is accepted and unchanged. REQ-3 now consumes its
`ready_not_executed` preflight result to permit bounded execution only when a
directly injected client inherits `OpenAIVoiceInputFakeClientMarker`.

```text
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```

REQ-3 does not change the REQ-2 guarantee that the adapter itself never
reads audio or invokes a client.
## REQ-4 dependent runtime

REQ-2 remains accepted. REQ-4 now supplies the first Framework-owned concrete
client factory:

```text
OpenAIVoiceInputRealClientFactory
```

It is the only factory REQ-4 executes. The factory resolves the optional OpenAI
SDK lazily and passes an explicit private credential, timeout, and retry count.

```text
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```
\

## REQ-5 operator acceptance dependency

REQ-2 remains accepted. REQ-5 uses the public adapter and concrete REQ-4 factory
without adding provider-native objects to the public result.

```text
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```
