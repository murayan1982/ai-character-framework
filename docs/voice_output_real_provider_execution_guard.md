# Voice Output Real Provider Execution Guard

This document defines the final FW-side guard before the public voice output boundary is allowed to call a real provider SDK.

The guard is intentionally separate from the public app contract and from DRC real Web audio evidence. It lets FW advertise that a provider is configured while still preventing accidental SDK imports, provider network calls, or local artifact writes during mock-safe checks.

## Why this guard exists

DRC and other host apps should call only the public FW voice output boundary:

```python
from framework import VoiceOutputRequest, create_voice_output_session
```

They should not call `tts.voice_engine`, should not own provider voice IDs, should not pass API keys, and should not know provider-specific request parameters.

Even inside FW, real provider execution needs one more explicit operator decision beyond "real TTS intent" and "provider selected". This prevents a CI run, release-package check, or app smoke test from accidentally creating audio or contacting a provider when environment variables are partially configured.

## Execution layers

A real provider call may happen only when all layers are present:

1. The app calls the public voice output boundary.
2. FW real voice output intent is enabled:

   ```powershell
   $env:FRAMEWORK_VOICE_OUTPUT_REAL_TTS = "1"
   ```

3. FW owns provider selection:

   ```powershell
   $env:FRAMEWORK_VOICE_OUTPUT_PROVIDER = "elevenlabs"
   ```

4. FW owns provider settings, such as API key, voice registry, and model selection.
5. FW operator policy explicitly opens the real provider execution guard:

   ```powershell
   $env:FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION = "1"
   ```

If layer 5 is missing or false, the public output result must be non-playable:

```text
request_state: skipped
audio_ready: False
audio_url: None
audio_artifact_ref: None
reason: provider_execution_guard_disabled
```

## Mock-safe behavior

With `FRAMEWORK_VOICE_OUTPUT_REAL_TTS=1` and `FRAMEWORK_VOICE_OUTPUT_PROVIDER=elevenlabs`, but without `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1`, FW may report that a supported provider is configured. However, `create_output()` must still stop before:

- importing provider SDKs
- calling provider APIs
- writing audio artifacts
- exposing provider voice IDs, API keys, model IDs, or provider payloads
- using legacy local playback internals

The public result is intentionally `skipped`, not `generated`, so host apps do not mistake readiness for playable audio.

## Allowed execution with missing settings

When `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1` is present but FW-owned provider settings are missing or invalid, FW should return a safe unavailable result before provider SDK import:

```text
request_state: unavailable
audio_ready: False
reason: provider_settings_unavailable
```

This means the guard was opened, but the real run still did not proceed because FW configuration was incomplete.

## Verification

Run the mock-safe execution guard smoke:

```powershell
python scripts/smoke_voice_output_real_provider_execution_guard.py
```

The smoke verifies:

- configured providers are guarded by default
- false guard values such as `0`, `false`, `off`, and `disabled` remain guarded
- opening the guard with missing settings stops before provider SDK import
- no audio artifacts are created during mock-safe checks
- provider details stay hidden from public metadata

Include it in the local v5.0.0 check set:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_artifact_result_contract.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
python scripts/check_release_package.py
python examples/app_voice_output_integration.py
```

## Evidence boundary

This FW guard does not complete DRC evidence.

Even if a later private configured run opens the guard and generates audio through FW, DRC still needs its own Web UI playback evidence workflow, screenshot/private evidence handling, marker-only evidence JSON, and acceptance validator success.

Until that DRC workflow validates, keep:

```text
DRC real_tts_web_audio_output: NOT_ACCEPTED
DRC v2.0.0: NOT_RELEASED
```

## Acceptance for this checkpoint

This checkpoint is complete when:

- the execution guard defaults closed
- `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1` is required before real provider execution can proceed
- configured-but-guarded output returns `request_state: skipped`
- missing FW-owned settings still return safe `unavailable`
- provider SDKs and legacy playback internals are not imported in mock-safe checks
- release-package checks include this document and smoke script
