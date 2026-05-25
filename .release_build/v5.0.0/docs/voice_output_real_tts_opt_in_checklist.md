# Voice Output Real TTS Opt-in Checklist

This checklist defines the FW-side safety gate for enabling real TTS through the public voice output boundary.

It is intentionally separate from DRC real Web audio evidence. Passing this checklist means the FW boundary is ready for a configured real run; it does not mean DRC `real_tts_web_audio_output` is accepted.

## Scope

The public voice output boundary is:

```python
from framework import VoiceOutputRequest, create_voice_output_session
```

Host apps may pass only provider-neutral voice output intent:

- `text`
- `voice_profile_id`
- `requested_audio_format`
- `utterance_purpose`
- `language_code`

FW owns and hides:

- provider selection
- provider voice IDs
- API keys
- model IDs
- provider-specific request parameters
- provider SDK calls
- temporary audio files and artifact paths
- local playback behavior

Host apps must not import `tts.voice_engine`, `registry.tts`, provider SDKs, or local playback helpers for app-facing TTS integration.

## Opt-in layers

Real TTS requires an explicit FW-owned opt-in. No single layer is enough by itself.

1. The app calls the public FW boundary.
2. FW is run with real voice output intent enabled:

   ```powershell
   $env:FRAMEWORK_VOICE_OUTPUT_REAL_TTS = "1"
   ```

3. FW owns provider selection:

   ```powershell
   $env:FRAMEWORK_VOICE_OUTPUT_PROVIDER = "elevenlabs"
   ```

4. FW owns provider credentials and provider-specific registry settings through its private configuration or environment.
5. FW operator policy explicitly opens the real provider execution guard:

   ```powershell
   $env:FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION = "1"
   ```

6. FW writes an audio artifact only through the public session result path.

If real TTS intent or provider configuration is missing, the public result must stay safe and app-readable, usually:

```text
request_state: unavailable
audio_ready: False
```

If a supported provider is configured but the execution guard is still closed, the public result must also stay non-playable:

```text
request_state: skipped
audio_ready: False
reason: provider_execution_guard_disabled
```

## Mock-safe checks

These commands must pass without provider credentials:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
python scripts/check_release_package.py
python examples/app_voice_output_integration.py
```

The dedicated opt-in smoke confirms:

- default voice output does not enable real TTS
- `FRAMEWORK_VOICE_OUTPUT_REAL_TTS=1` without a provider remains unavailable
- unsupported provider names remain unavailable
- a configured provider remains skipped while the real provider execution guard is closed
- opening the execution guard with missing FW settings returns unavailable before provider SDK execution
- provider details are not exposed through public dataclasses, metadata, or app examples
- `tts.voice_engine`, provider SDKs, runtime, and VTS modules are not imported during mock-safe checks

## Manual configured real run

A real run may be attempted only after the mock-safe checks pass.

Use the public example or a host app wrapper, not FW internals:

```powershell
$env:FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION = "1"
python examples/app_voice_output_integration.py --real-tts --artifact-dir .\temp\voice_output
```

For a real run, configure provider secrets and voice registry values as FW-owned settings, then open the FW execution guard only for that run. Do not pass provider settings from app code.

A successful FW real run may return:

```text
request_state: generated
audio_ready: True
audio_artifact_ref: <FW-owned artifact path>
```

The artifact reference is a FW-side handoff for the host app. It is not a provider voice ID, API key, model ID, or provider payload.

## Evidence handling

Do not commit:

- API keys
- provider voice IDs
- raw provider request or response payloads
- generated audio artifacts
- local artifact paths from a private machine
- screenshots or private Web evidence
- LAN IP addresses

For DRC, real evidence still belongs to the DRC evidence workflow, not to this FW checklist. DRC evidence completion still requires Web UI execution, actual playback confirmation, screenshot/private evidence handling, marker-only evidence JSON, and acceptance validator success.

Until that DRC evidence validates, keep:

```text
DRC real_tts_web_audio_output: NOT_ACCEPTED
DRC v2.0.0: NOT_RELEASED
```

## Acceptance for this FW checkpoint

This FW checkpoint is complete when:

- public voice output APIs remain importable from `framework`
- app examples remain provider-neutral
- provider details stay FW-owned and hidden from public contracts
- mock-safe checks pass with no provider credentials
- real TTS intent is explicit opt-in only
- real provider execution requires `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1`
- unavailable results are treated as readiness checks, not real evidence
- DRC is still blocked from marking real TTS Web audio evidence accepted
