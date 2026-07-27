# v5.3.0 Lazy Provider Adapter Protocol and Fake Adapter

Status:

```text
STT-1c: ACCEPTED
STT-1d: READY pending next small commit
```

## Purpose

This checkpoint adds a lazy provider adapter protocol and a mock-safe fake
adapter for voice input.

The target flow remains:

```text
host app capture -> VoiceInputAudioSource -> lazy provider adapter -> typed VoiceInputResult
```

## Public symbols

The public framework root now exports:

```text
VoiceInputProviderAdapter
VoiceInputProviderAdapterInfo
FakeVoiceInputProviderAdapter
```

## Rules

The adapter boundary is lazy and provider-neutral:

- `import framework` must not import provider SDKs;
- fake adapter does not read audio;
- fake adapter does not open microphones;
- fake adapter does not call real STT providers;
- fake adapter returns typed `VoiceInputResult`;
- DRC still does not import provider-specific code.

## Current limitation

This checkpoint adds the adapter protocol and fake adapter only.

`VoiceInputSession` is not wired to the adapter path yet. That is reserved for
STT-1d.

## STT-1c acceptance evidence

Local verification accepted STT-1c with these facts:

```text
v530_lazy_provider_adapter_status: accepted
v530_lazy_provider_adapter_public_exports_present: True
v530_fake_adapter_transcript_result_present: True
v530_lazy_provider_adapter_provider_safe_import: True
v530_fake_adapter_reads_audio: False
v530_fake_adapter_microphone_accessed: False
v530_fake_adapter_provider_execution_executed: False
v530_stt1d_authorization: ready-for-stt1d
```

The previous STT gates also passed:

- `smoke_v530_host_audio_source_contract.py`
- `smoke_v530_real_stt_provider_boundary_inventory.py`

The v5.2.0 compatibility gates also passed:

- `smoke_v520_voice_input_public_contract_conformance_gate.py`
- `smoke_v520_release_readiness_gate.py`

No real provider execution, microphone access, audio read, raw audio handling,
DRC change, release package, or tag creation was performed.

`.vscode/settings.json` remained local-only and is not part of this checkpoint.
