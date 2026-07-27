# v5.3.0 Provider-neutral Host Audio Source Contract

Status:

```text
STT-1b: ACCEPTED
STT-1c: READY pending next small commit
```

## Purpose

This checkpoint adds a public data-only contract for host-captured audio handoff.

The target DRC RT-3 path is:

```text
host app capture -> opaque/private audio source -> FW public voice-input API -> guarded STT provider adapter -> typed VoiceInputResult
```

## Public symbols

The public framework root now exports:

```text
VoiceInputAudioSourceKind
VoiceInputAudioEncoding
VoiceInputAudioFormat
VoiceInputAudioRef
VoiceInputAudioSource
```

## Safety rules

STT-1b does not:

- read audio files;
- open microphones;
- upload audio;
- call STT providers;
- create provider clients;
- read API keys;
- add provider dependencies;
- change DRC;
- create a release package;
- create a tag.

## Current limitation

This checkpoint only adds the host-audio source contract.

`VoiceInputSession` does not yet execute adapter-backed STT with this source.
That is reserved for later small commits.

## STT-1b acceptance evidence

Local verification accepted STT-1b with these facts:

```text
v530_host_audio_source_contract_status: accepted
v530_host_audio_source_public_exports_present: True
v530_host_audio_source_provider_safe_import: True
v530_host_audio_source_reads_audio: False
v530_host_audio_source_microphone_accessed: False
v530_host_audio_source_provider_execution_executed: False
v530_stt1c_authorization: ready-for-stt1c
```

The inventory gate also confirmed:

```text
v530_host_audio_source_contract_present: True
v530_lazy_provider_adapter_present: False
v530_runtime_code_changed: False
v530_provider_execution_executed: False
v530_microphone_accessed: False
v530_audio_handled: False
v530_stt1b_status: accepted
```

The v5.2.0 compatibility gates also passed:

- `smoke_v520_voice_input_public_contract_conformance_gate.py`
- `smoke_v520_release_readiness_gate.py`

No provider execution, microphone access, audio read, raw audio handling, DRC
change, release package, or tag creation was performed.

`.vscode/settings.json` remained local-only and is not part of this checkpoint.
