# v5.0.0 Voice Output Release Readiness Checklist

This checklist defines what counts as release-ready for AI Character Framework v5.0.0.

v5.0.0 is a **Public Voice Output / TTS Boundary Foundation** release. It is not a DRC real Web audio evidence release and it is not a full realtime voice runtime release.

The release can be considered ready when the public voice output boundary is stable, mock-safe checks pass without provider credentials, and the FW-side real provider execution policy is explicit. Real provider runs and DRC Web evidence remain separate follow-up workflows.

## Release scope

v5.0.0 may be released when FW provides all of the following:

- a public provider-neutral voice output API
- a lazy provider adapter boundary
- app-safe `VoiceOutputRequest` and `VoiceOutputResult` models
- a documented artifact handoff contract
- a documented real TTS opt-in boundary
- a documented real provider execution guard
- mock-safe smoke checks that pass without provider credentials
- release package checks that include the v5 voice output docs and smoke scripts

The release must preserve the v4.0.0 TextChat public facade behavior.

## Public API readiness

The public FW import boundary must expose:

```python
create_voice_output_session
VoiceOutputSession
VoiceOutputSessionInfo
VoiceOutputRequest
VoiceOutputResult
```

Application code should import only from `framework`:

```python
from framework import VoiceOutputRequest, create_voice_output_session
```

Host apps may pass only provider-neutral intent fields:

```text
text
voice_profile_id
requested_audio_format
utterance_purpose
language_code
```

FW must continue to own and hide:

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

## Mock-safe release readiness

The following checks are release-blocking for v5.0.0:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_artifact_result_contract.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
python scripts/smoke_voice_output_v500_release_readiness.py
python scripts/check_release_package.py
python examples/app_voice_output_integration.py
```

These checks must pass without provider credentials.

Expected mock-safe states are acceptable for this release:

```text
request_state: unavailable
request_state: skipped
audio_ready: False
audio_handoff_kind: none
provider_details_exposed: false
```

`unavailable` and `skipped` are readiness states, not playable audio evidence.

## Real-run readiness boundary

v5.0.0 must keep real provider execution default-off.

A real provider call may proceed only when all FW-owned execution layers are present:

```powershell
$env:FRAMEWORK_VOICE_OUTPUT_REAL_TTS = "1"
$env:FRAMEWORK_VOICE_OUTPUT_PROVIDER = "elevenlabs"
$env:FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION = "1"
```

Provider credentials, provider voice IDs, model IDs, and provider-specific options must still be read from FW-owned settings, not from the host app public request.

If the execution guard is closed, the result must remain non-playable:

```text
request_state: skipped
audio_ready: False
audio_url: None
audio_artifact_ref: None
reason: provider_execution_guard_disabled
```

If the execution guard is open but FW-owned settings are missing or invalid, the result must stop before provider SDK import:

```text
request_state: unavailable
audio_ready: False
reason: provider_settings_unavailable
```

## DRC handoff boundary

This FW release readiness checklist does not complete DRC evidence.

DRC remains blocked from accepting real TTS Web audio evidence until DRC integrates through the FW public voice output boundary and validates its own Web evidence workflow.

Keep the DRC status as:

```text
DRC real_tts_web_audio_output: NOT_ACCEPTED
DRC v2.0.0: NOT_RELEASED
```

DRC must still not:

- import `tts.voice_engine` directly
- own ElevenLabs/OpenAI provider implementation
- own provider voice IDs
- pass provider secrets through app-facing request objects
- treat local `ffplay` playback as Web evidence
- treat `unavailable` or `skipped` as real audio evidence

A later DRC workflow still needs Web UI playback evidence, screenshot/private evidence handling, marker-only evidence JSON, and acceptance validator success.

## Release blockers

Do not cut v5.0.0 if any of these are true:

- `import framework` imports `tts.voice_engine` or provider SDKs
- public smoke checks require API keys
- app-facing request/result types expose provider voice IDs, API keys, model IDs, provider payloads, or provider-specific options
- a configured provider can call a real SDK without `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1`
- guarded or unavailable output exposes playable audio handoffs
- release package checks omit v5 voice output docs or smoke scripts
- DRC evidence is marked accepted based only on FW mock-safe readiness

## Acceptance for this checkpoint

This checkpoint is complete when:

- this checklist is included in release package checks
- `scripts/smoke_voice_output_v500_release_readiness.py` passes
- the standard v5.0.0 local verification command set passes
- docs clearly distinguish mock-safe release readiness, real-run readiness, and DRC evidence readiness
- DRC remains unchanged and `real_tts_web_audio_output` remains `NOT_ACCEPTED`
