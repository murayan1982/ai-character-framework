# v5.3.0 Guarded Real Provider Adapter

Status:

```text
STT-1e: ACCEPTED
STT-1f: READY pending next small commit
```

## Purpose

This checkpoint adds the first guarded real-provider adapter boundary for voice
input.

The adapter represents a real STT provider boundary while still refusing to
execute provider code unless a host app explicitly opts in and credentials are
available.

## Public symbols

The public framework root now exports:

```text
GuardedRealVoiceInputProviderAdapter
```

## Guard behavior

The guarded adapter has three typed preflight outcomes:

```text
provider_execution_not_allowed
missing_credentials
real_stt_not_implemented
```

The adapter returns typed `VoiceInputResult` values and does not execute real STT
in this checkpoint.

## Safety rules

STT-1e does not:

- import provider SDKs;
- read API key values;
- create provider clients;
- read audio files;
- open microphones;
- upload audio;
- call real STT providers;
- change DRC;
- create a release package;
- create a tag.

## Current limitation

This checkpoint adds the guarded real-provider adapter boundary only.

DRC public handoff verification is reserved for STT-1f.

## STT-1e acceptance evidence

Local verification accepted STT-1e with these facts:

```text
v530_guarded_real_provider_adapter_status: accepted
v530_guarded_real_provider_adapter_public_export_present: True
v530_guarded_real_provider_adapter_provider_safe_import: True
v530_guarded_real_provider_adapter_preflight_guard_present: True
v530_guarded_real_provider_adapter_session_path_present: True
v530_guarded_real_provider_adapter_reads_audio: False
v530_guarded_real_provider_adapter_microphone_accessed: False
v530_guarded_real_provider_adapter_provider_execution_executed: False
v530_stt1f_authorization: ready-for-stt1f
```

The previous STT gates also passed:

- `smoke_v530_voice_input_session_adapter_wiring.py`
- `smoke_v530_lazy_provider_adapter_fake.py`
- `smoke_v530_host_audio_source_contract.py`
- `smoke_v530_real_stt_provider_boundary_inventory.py`

The v5.2.0 compatibility gates also passed:

- `smoke_v520_voice_input_public_contract_conformance_gate.py`
- `smoke_v520_release_readiness_gate.py`

No real provider execution, provider SDK import, API key read, microphone access,
audio read, raw audio handling, DRC change, release package, or tag creation was
performed.

`.vscode/settings.json` remained local-only and is not part of this checkpoint.
