# Voice Output Artifact Result Contract

This document defines the public result handoff contract for the v5.0.0 voice output boundary.

The goal is to let Web apps such as Daily Rhythm Companion (DRC) request voice output through FW and then decide whether an audio playback handoff exists, without knowing provider-specific implementation details.

## Public result fields

`VoiceOutputResult` is the only public app-facing result shape for voice output.

```python
VoiceOutputResult(
    request_state="unavailable | skipped | rejected | generated | failed",
    audio_ready=False,
    audio_format=None,
    audio_url=None,
    audio_artifact_ref=None,
    message="...",
    public_metadata={...},
)
```

The result must stay provider-neutral. It must not expose provider voice IDs, API keys, provider model IDs, provider request payloads, provider response payloads, or local playback internals.

## Request state semantics

Current public states:

- `unavailable`: the FW boundary is available, but real TTS is disabled, provider settings are missing, the provider is unsupported, or the provider SDK is unavailable.
- `skipped`: the caller or FW policy intentionally did not create audio, such as when the real provider execution guard is closed.
- `rejected`: the request is invalid for the public boundary, such as empty text or an unsupported output format.
- `generated`: FW generated audio and returned exactly one public handoff.
- `failed`: explicit generation was attempted but failed inside the FW provider boundary.

Host apps must not treat `unavailable`, `skipped`, `rejected`, or `failed` as playable output.

## Audio handoff fields

The public handoff fields are:

- `audio_url`: a Web-app-consumable URL when FW can host, sign, or otherwise expose audio safely.
- `audio_artifact_ref`: an opaque FW-owned artifact reference when FW generated audio but does not expose a public URL.

Current v5.0.0 behavior primarily supports `audio_artifact_ref` for explicit configured real runs. `audio_url` remains a public contract field for future Web-friendly artifact hosting.

The result helper properties are:

- `result.audio_handoff_kind`: `none`, `audio_url`, `audio_artifact_ref`, or `multiple`.
- `result.has_audio_handoff`: `True` only when exactly one public handoff exists.
- `result.is_generated`: `True` only when `request_state == "generated"` and `audio_ready is True`.

## Invariants

Mock-safe, unavailable, and execution-guarded skipped outputs must satisfy:

```text
request_state != generated
audio_ready: False
audio_url: None
audio_artifact_ref: None
audio_handoff_kind: none
has_audio_handoff: False
```

Generated outputs must satisfy:

```text
request_state: generated
audio_ready: True
audio_format: a normalized public format such as mp3
exactly one of audio_url or audio_artifact_ref is set
audio_handoff_kind: audio_url or audio_artifact_ref
has_audio_handoff: True
```

A result with both `audio_url` and `audio_artifact_ref` set is considered invalid for current v5.0.0 app integration. FW may change this in a later version, but DRC should currently expect exactly one handoff for generated audio.

## Host app handling

Host apps should branch on `audio_ready` and the handoff fields:

```python
result = voice_session.create_output(request)

if not result.audio_ready:
    show_unavailable_or_retry_message(result.message)
elif result.audio_url:
    play_from_url(result.audio_url, result.audio_format)
elif result.audio_artifact_ref:
    hand_off_to_fw_artifact_endpoint(result.audio_artifact_ref, result.audio_format)
else:
    treat_as_contract_error()
```

Do not parse `audio_artifact_ref` as a provider payload or commit it as evidence. It is a FW-owned handoff reference and may contain private local paths during manual configured runs.

## DRC evidence boundary

This FW contract does not complete DRC real TTS Web audio evidence by itself.

DRC may use this contract later to decide when a FW voice output result can be presented to the Web UI, but DRC still needs its own evidence flow:

- actual DRC Web UI execution
- playback confirmation
- screenshot/private evidence handling
- marker-only evidence JSON
- DRC acceptance validator success

Until that DRC workflow validates, keep:

```text
DRC real_tts_web_audio_output: NOT_ACCEPTED
DRC v2.0.0: NOT_RELEASED
```

## Mock-safe verification

Run:

```powershell
python scripts/smoke_voice_output_artifact_result_contract.py
```

This smoke check verifies that public result fields and helper properties follow the artifact handoff contract without provider credentials or real TTS execution. The separate `smoke_voice_output_real_provider_execution_guard.py` check verifies that configured providers still return a non-playable skipped result unless the FW execution guard is explicitly opened.
