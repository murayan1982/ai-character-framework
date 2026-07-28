# v5.4.0 Candidate Real STT Provider Execution Small Commit Checklist

Status:

```text
requirements definition: ACCEPTED
```

## Guardrails

- Preserve provider-safe `import framework`.
- Preserve v5.3.0 public Voice Input contracts.
- Preserve fake adapter behavior.
- Preserve guarded adapter non-execution behavior until real execution gates are explicitly implemented.
- Do not read audio before execution gates pass.
- Do not create provider clients before execution gates pass.
- Do not read credentials before execution gates pass.
- Do not expose private file paths, raw audio, credentials, or provider payloads.
- Do not modify DRC in Framework commits.
- Keep private operator evidence outside the repository.
- Do not create a release package or tag during requirements definition.

## REQ-0 - Requirements definition

Status:

```text
ACCEPTED
```

Changed files:

```text
README.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/smoke_v540_real_stt_provider_execution_requirements.py
```

Acceptance requirements:

- [ ] `python -m compileall -q framework core stt scripts examples`
- [ ] `python scripts/smoke_v540_real_stt_provider_execution_requirements.py`
- [ ] `python scripts/smoke_v530_release_package_gate.py`
- [ ] `python scripts/smoke_v530_release_readiness_gate.py`
- [ ] `python scripts/smoke_v530_drc_public_handoff_verification.py`
- [ ] `python scripts/smoke_v530_guarded_real_provider_adapter.py`
- [ ] `python scripts/smoke_v530_voice_input_session_adapter_wiring.py`
- [ ] `python scripts/smoke_v530_lazy_provider_adapter_fake.py`
- [ ] `python scripts/smoke_v530_host_audio_source_contract.py`
- [ ] `python scripts/smoke_v530_real_stt_provider_boundary_inventory.py`
- [ ] `python scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- [ ] `python scripts/smoke_v520_release_readiness_gate.py`
- [ ] `git diff --check` for REQ-0 files
- [ ] no real provider execution
- [ ] no microphone access
- [ ] no audio file read
- [ ] no API key read
- [ ] no DRC repo change
- [ ] no release package creation
- [ ] no tag creation

## REQ-1 - Provider execution configuration and status

Status:

```text
READY_FOR_IMPLEMENTATION
```

Expected focus: explicit enable flag, provider selection, model/config surface, credential availability without secret exposure, and capability/status mapping.

## REQ-2 - Safe FILE_PATH validation

Status:

```text
BLOCKED pending REQ-1 acceptance
```

Expected focus: file existence, normal file check, empty/invalid file rejection, size/duration limits, no private path exposure, and no audio read before gates pass.

## REQ-3 - Injectable real-provider client boundary

Status:

```text
BLOCKED pending REQ-2 acceptance
```

Expected focus: fake injected client, provider call shape, model/config propagation, transcript normalization, provider error mapping, and no network in source acceptance.

## REQ-4 - First concrete real-provider adapter

Status:

```text
BLOCKED pending REQ-3 acceptance
```

Expected focus: lazy provider runtime, explicit opt-in, private credential use, provider-safe import preserved, and no default execution.

## REQ-5 - Private real-provider operator acceptance

Status:

```text
BLOCKED pending REQ-4 acceptance
```

Expected focus: private WAV, private credentials, real transcript, public result redaction, and private evidence outside repository.

## REQ-6 - DRC released-FW adoption gate

Status:

```text
BLOCKED pending FW release
```

Expected focus: DRC public-only import, DRC private WAV handoff, real transcript handoff, fake path preserved, and RT-3d unblock criteria.
