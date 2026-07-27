# v5.3.0 Real STT Small Commit Checklist

## STT-1a - Real STT provider boundary inventory

Status:

```text
ACCEPTED
```

Changed files:

```text
README.md
docs/roadmap_feature_v5.3.0.md
docs/v530_real_stt_provider_boundary_inventory.md
docs/v530_real_stt_small_commit_checklist.md
scripts/smoke_v530_real_stt_provider_boundary_inventory.py
```

Acceptance requirements:

- [x] `python -m compileall -q framework core stt scripts`
- [x] `python scripts/smoke_v530_real_stt_provider_boundary_inventory.py`
- [x] `python scripts/smoke_v520_voice_input_inventory.py`
- [x] `python scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- [x] `python scripts/smoke_v520_release_readiness_gate.py`
- [x] `git diff --check` for the five STT-1a files
- [x] working tree contains no STT-1a runtime code changes
- [x] global capability voice-input status is recorded as existing v5.2.0 behavior
- [x] `.vscode/settings.json` remains local-only and is not included
- [x] STT-1b remains blocked until STT-1a acceptance

## STT-1b - Provider-neutral host-audio source contract

Status:

```text
ACCEPTED
```

### STT-1b implementation files

```text
README.md
framework/__init__.py
framework/voice_input_audio.py
docs/v530_host_audio_source_contract.md
docs/v530_real_stt_small_commit_checklist.md
scripts/smoke_v530_host_audio_source_contract.py
```

### STT-1b acceptance requirements

- [x] `python -m compileall -q framework core stt scripts`
- [x] `python scripts/smoke_v530_host_audio_source_contract.py`
- [x] `python scripts/smoke_v530_real_stt_provider_boundary_inventory.py`
- [x] `python scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- [x] `python scripts/smoke_v520_release_readiness_gate.py`
- [x] `git diff --check` for STT-1b files
- [x] no provider execution
- [x] no microphone access
- [x] no audio file read
- [x] `.vscode/settings.json` remains local-only and is not included

## STT-1c - Lazy provider adapter protocol and fake adapter

Status:

```text
ACCEPTED
```

Changed files:

```text
README.md
framework/__init__.py
framework/voice_input_provider_adapter.py
docs/v530_lazy_provider_adapter_fake.md
docs/v530_real_stt_provider_boundary_inventory.md
docs/v530_real_stt_small_commit_checklist.md
scripts/smoke_v530_lazy_provider_adapter_fake.py
scripts/smoke_v530_real_stt_provider_boundary_inventory.py
```

Acceptance requirements:

- [x] `python -m compileall -q framework core stt scripts`
- [x] `python scripts/smoke_v530_lazy_provider_adapter_fake.py`
- [x] `python scripts/smoke_v530_host_audio_source_contract.py`
- [x] `python scripts/smoke_v530_real_stt_provider_boundary_inventory.py`
- [x] `python scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- [x] `python scripts/smoke_v520_release_readiness_gate.py`
- [x] `git diff --check` for STT-1c files
- [x] no real provider execution
- [x] no microphone access
- [x] no audio file read
- [x] `.vscode/settings.json` remains local-only and is not included

## STT-1d - Public VoiceInputSession adapter wiring

Status:

```text
READY pending next small commit
```
