# Host App Voice Output Integration Handoff

This document defines the app-facing handoff for host applications that want to use the v5.0.0 public voice output boundary.

The goal is to make voice output integration safe for general app developers while keeping provider-specific TTS implementation details inside FW.

Daily Rhythm Companion (DRC) is the first concrete integration target, but this policy is not DRC-specific. Any host app should follow the same boundary.

## Integration summary

Host apps should request voice output through the public framework package:

```python
from framework import VoiceOutputRequest, create_voice_output_session

session = create_voice_output_session(
    default_voice_profile_id="gentle_mina_default",
)

result = session.create_output(
    VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )
)
```

Host apps should not import `tts.voice_engine`, provider adapters, provider SDKs, config internals, or local playback internals.

## What host apps may pass

A host app may pass only provider-neutral voice output intent:

- `text`
- `voice_profile_id`
- `requested_audio_format`
- `utterance_purpose`
- `language_code`

These fields describe what the app wants FW to say and how the app would prefer to consume the result. They do not select a provider directly.

## What FW owns and hides

FW owns provider-specific and runtime-specific details:

- provider selection
- provider voice IDs
- API keys and tokens
- model IDs
- provider-specific request parameters
- provider SDK imports and calls
- provider response parsing
- temporary audio file handling
- local playback implementation details
- artifact storage and cleanup strategy

Host apps must not use provider details as app-facing configuration or evidence.

## Voice profile IDs

`voice_profile_id` is a framework-level identifier, not a provider voice ID.

Good app-facing usage:

```python
VoiceOutputRequest(
    text="おはようございます。",
    voice_profile_id="gentle_mina_default",
    requested_audio_format="mp3",
)
```

Avoid app-facing usage like this:

```python
# Do not do this in host app code.
VoiceOutputRequest(
    text="おはようございます。",
    voice_profile_id="elevenlabs_internal_voice_id_or_provider_value",
)
```

Future FW versions may map `voice_profile_id` through a voice profile registry, app profile, character configuration, or provider adapter. The host app contract should not change when the provider mapping changes.

## VoiceOutputResult handling

Host apps should branch on the public result contract:

```python
if not result.audio_ready:
    show_voice_output_unavailable(result.message)
elif result.audio_url:
    play_audio_url(result.audio_url)
elif result.audio_artifact_ref:
    request_fw_artifact_playback(result.audio_artifact_ref)
else:
    report_contract_error("generated result has no audio handoff")
```

Important fields:

- `request_state`: public lifecycle state
- `audio_ready`: whether app playback may proceed
- `audio_format`: normalized app-facing format such as `mp3`
- `audio_url`: FW-provided URL when FW hosts or signs an app-consumable artifact
- `audio_artifact_ref`: opaque FW-owned artifact reference when URL hosting is not available
- `audio_handoff_kind`: helper classification for `none`, `audio_url`, `audio_artifact_ref`, or `multiple`
- `has_audio_handoff`: whether the result has exactly one public handoff
- `is_generated`: whether the result represents generated playable audio

Host apps must not inspect provider-specific internals to decide playback behavior.

## Request states

Host apps should handle these request states as public lifecycle states:

| State | App meaning | Playable audio? |
| --- | --- | --- |
| `unavailable` | FW voice output is disabled, unsupported, or not configured. | No |
| `skipped` | A provider may be configured, but explicit provider execution is guarded off. | No |
| `rejected` | The public request was invalid or unsupported. | No |
| `failed` | FW attempted provider work but generation failed. | No |
| `generated` | FW generated an app-consumable handoff. | Yes, only when `audio_ready=True` and exactly one handoff exists |

`unavailable`, `skipped`, `rejected`, and `failed` must not be counted as real audio evidence.

## Audio handoff rules

For v5.0.0, generated results should expose exactly one app-facing handoff:

- `audio_url`, or
- `audio_artifact_ref`

Host apps should treat both fields being present as a contract error for the current boundary.

`audio_artifact_ref` is opaque. It may look like a local path in an early adapter, but host apps should not parse provider names, API details, or storage internals from it. A host app should hand it back to FW or its own trusted backend boundary for playback delivery.

## Real provider execution guard

Real provider execution is intentionally more strict than real TTS enablement.

A configured provider still must not import provider SDKs, call provider APIs, or write audio artifacts unless the FW execution guard is explicitly opened:

```text
FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1
```

This guard is for deliberate configured real runs only. General app integration tests and release smoke checks should leave it unset.

A guarded configured provider should return:

```text
request_state: skipped
audio_ready: False
reason: provider_execution_guard_disabled
```

That state proves the boundary is safe. It does not prove real audio generation.

## Host app integration checklist

Before a host app integrates voice output, confirm:

- app code imports voice output only from `framework`
- app code passes only provider-neutral `VoiceOutputRequest` fields
- app code does not own provider voice IDs, API keys, model IDs, or provider-specific options
- app code handles `unavailable` and `skipped` as non-playable states
- app code plays audio only when `audio_ready=True`
- app code requires exactly one handoff: `audio_url` or `audio_artifact_ref`
- app code does not treat local playback, command output, or provider logs as Web evidence
- real provider execution remains explicitly guarded by FW

## DRC reference integration target

DRC should use this same host app handoff when it resumes real TTS Web audio evidence work.

DRC may pass:

- advice text
- DRC/FW-level `voice_profile_id`
- requested audio format such as `mp3`
- utterance purpose such as `daily_advice`
- language code such as `ja`

DRC must not:

- import `tts.voice_engine`
- call ElevenLabs, OpenAI TTS, or any provider SDK directly
- own provider voice IDs or provider model IDs
- use local `ffplay` playback as Web evidence
- commit raw audio, screenshots, provider payloads, secrets, private paths, or LAN IPs
- mark `real_tts_web_audio_output` as accepted from FW smoke checks alone

DRC `real_tts_web_audio_output` remains `NOT_ACCEPTED` until DRC validates Web UI playback evidence through the FW public boundary, screenshot/private evidence handling, marker-only evidence JSON, and the DRC acceptance validator.

## Required FW checks

Run these checks before treating the host app handoff as ready:

```powershell
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_artifact_result_contract.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
python scripts/smoke_voice_output_host_app_handoff.py
python scripts/smoke_voice_output_v500_release_readiness.py
python scripts/check_release_package.py
python examples/app_voice_output_integration.py
```

The host app handoff smoke is mock-safe. It must pass without provider credentials, provider SDK imports, provider network calls, generated audio, or committed evidence artifacts.
