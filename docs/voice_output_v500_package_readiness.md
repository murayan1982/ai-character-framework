# v5.0.0 Voice Output Package Readiness

This document defines the final package-readiness checkpoint for AI Character Framework v5.0.0.

v5.0.0 is a **Public Voice Output / TTS Boundary Foundation** release. It packages a mock-safe public voice output boundary for host applications. It does not package DRC real Web audio evidence, real provider execution proof, or a full realtime voice runtime.

## Release package scope

The v5.0.0 public package should include the public app-facing voice output boundary and the documentation needed for host apps to use it safely.

Required release-surface items:

```text
framework public API:
- create_voice_output_session
- VoiceOutputSession
- VoiceOutputSessionInfo
- VoiceOutputRequest
- VoiceOutputResult

docs:
- RELEASE_NOTES.md
- public_facade.md
- app_integration_contract.md
- roadmap_feature_v5.0.0.md
- voice_output_real_tts_opt_in_checklist.md
- voice_output_artifact_result_contract.md
- voice_output_real_provider_execution_guard.md
- voice_output_v500_release_readiness_checklist.md
- host_app_voice_output_integration_handoff.md
- voice_output_v500_package_readiness.md

examples:
- examples/app_voice_output_integration.py

scripts:
- scripts/smoke_public_facade.py
- scripts/smoke_app_sdk.py
- scripts/smoke_voice_output_real_tts_opt_in_boundary.py
- scripts/smoke_voice_output_artifact_result_contract.py
- scripts/smoke_voice_output_real_provider_execution_guard.py
- scripts/smoke_voice_output_host_app_handoff.py
- scripts/smoke_voice_output_v500_release_readiness.py
- scripts/smoke_voice_output_v500_package_readiness.py
- scripts/check_release_package.py
```

## What this package proves

This package proves that host apps can import the public FW voice output boundary and create mock-safe voice output sessions without provider credentials.

It also proves that the public contract keeps provider-specific details inside FW:

```text
provider selection
provider voice ID
API key
model ID
provider-specific request parameters
provider SDK calls
temporary audio file management
legacy local playback behavior
```

## What this package does not prove

Do not treat this package readiness checkpoint as any of the following:

```text
real provider audio generation evidence
DRC Web UI playback evidence
DRC screenshot evidence acceptance
ElevenLabs/OpenAI provider validation
local ffplay playback validation
full realtime voice interruption validation
always-on microphone / barge-in validation
```

Guarded, skipped, unavailable, rejected, or failed voice output results are non-playable states. They must not be counted as real audio evidence.

## Verification command set

Before cutting a v5.0.0 release package or tag, run the standard mock-safe verification set:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_artifact_result_contract.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
python scripts/smoke_voice_output_host_app_handoff.py
python scripts/smoke_voice_output_v500_release_readiness.py
python scripts/smoke_voice_output_v500_package_readiness.py
python scripts/check_release_package.py
python examples/app_voice_output_integration.py
```

These commands must pass without provider credentials and without real provider execution.

## Real provider execution remains separate

Real provider execution remains guarded by all FW-owned opt-in layers:

```powershell
$env:FRAMEWORK_VOICE_OUTPUT_REAL_TTS = "1"
$env:FRAMEWORK_VOICE_OUTPUT_PROVIDER = "elevenlabs"
$env:FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION = "1"
```

Provider API keys, provider voice IDs, model IDs, and provider-specific settings must still be read from FW-owned settings. Host apps must not pass those values through `VoiceOutputRequest`.

## DRC remains a follow-up workflow

DRC can resume integration work after the FW public voice output boundary release is available, but DRC evidence acceptance remains separate.

Keep the DRC status unchanged at this checkpoint:

```text
DRC real_tts_web_audio_output: NOT_ACCEPTED
DRC v2.0.0: NOT_RELEASED
```

DRC still needs Web UI playback evidence, screenshot/private evidence handling, marker-only evidence JSON, and acceptance validator success before real TTS Web audio output can be accepted.

## Acceptance for this checkpoint

This package-readiness checkpoint is complete when:

- `RELEASE_NOTES.md` describes v5.0.0 as a mock-safe public voice output boundary release
- `../README.md` describes v5.0.0 as Public Voice Output / TTS Boundary Foundation, not as the full realtime runtime release
- `release_package_policy.md` lists the v5.0.0 verification command set
- `voice_output_v500_release_readiness_checklist.md` includes the package-readiness smoke in the release-blocking command set
- `scripts/check_release_package.py` requires this package-readiness doc and smoke script
- `scripts/smoke_voice_output_v500_package_readiness.py` passes
- the standard mock-safe verification command set passes
