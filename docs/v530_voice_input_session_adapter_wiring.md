# v5.3.0 VoiceInputSession Adapter Wiring

Status:

```text
STT-1d: ACCEPTED
STT-1e: READY pending next small commit
```

## Purpose

This checkpoint wires the provider-neutral host-audio source contract and lazy
provider adapter into the public `VoiceInputSession` boundary.

## Public session methods

`VoiceInputSession` now exposes:

```text
transcribe_audio_result(audio_source, *, request=None, adapter=None)
listen_audio_result(audio_source, *, request=None, adapter=None)
```

The default adapter path uses `FakeVoiceInputProviderAdapter`.

## Safety rules

STT-1d does not:

- read audio files;
- open microphones;
- upload audio;
- call real STT providers;
- create provider clients;
- read API keys;
- add provider dependencies;
- change DRC;
- create a release package;
- create a tag.

## Current limitation

This checkpoint wires only the public session-to-adapter path.

The first guarded real provider adapter is reserved for STT-1e.

## STT-1d acceptance evidence

Local verification accepted STT-1d with these facts:

```text
v530_voice_input_session_adapter_wiring_status: accepted
v530_voice_input_session_adapter_methods_present: True
v530_voice_input_session_fake_adapter_result_present: True
v530_voice_input_session_provider_safe_import: True
v530_voice_input_session_reads_audio: False
v530_voice_input_session_microphone_accessed: False
v530_voice_input_session_provider_execution_executed: False
v530_stt1e_authorization: ready-for-stt1e
```

The previous STT gates also passed:

- `smoke_v530_lazy_provider_adapter_fake.py`
- `smoke_v530_host_audio_source_contract.py`
- `smoke_v530_real_stt_provider_boundary_inventory.py`

The v5.2.0 compatibility gates also passed:

- `smoke_v520_voice_input_public_contract_conformance_gate.py`
- `smoke_v520_release_readiness_gate.py`

No real provider execution, microphone access, audio read, raw audio handling,
DRC change, release package, or tag creation was performed.

`.vscode/settings.json` remained local-only and is not part of this checkpoint.
