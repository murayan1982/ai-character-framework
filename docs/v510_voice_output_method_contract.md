# v5.1.0 Voice Output Method Contract

Status: v5.1.0 P0 / FW-F2 alignment checkpoint.

## Purpose

FW v5.0.0 established the public voice output boundary, but the public docs and
implementation did not use the same method name consistently.

The README showed host apps calling:

```python
result = session.speak(request)
```

The v5.0.0 implementation exposed:

```python
result = session.create_output(request)
```

For v5.1.0, the stable host-app method name is:

```python
VoiceOutputSession.speak(request: VoiceOutputRequest) -> VoiceOutputResult
```

`create_output(request)` remains available as a v5.0 compatibility method so
existing integrations do not break during the transition.

## Public contract

Host apps should use:

```python
from framework import VoiceOutputRequest, create_voice_output_session

session = create_voice_output_session()
result = session.speak(
    VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )
)
```

Compatibility:

```text
- speak(request): preferred public host-app method
- create_output(request): v5.0 compatibility method
```

Both methods must return the same provider-neutral `VoiceOutputResult` shape and
must remain mock-safe when real provider execution is disabled.

## Boundary requirements

```text
- Host apps do not inspect multiple output method candidates.
- README examples use the preferred `speak(request)` method.
- Existing v5.0 integrations using `create_output(request)` continue to work.
- Real provider execution remains explicitly guarded.
- No provider SDK is imported during `import framework` or session creation.
- Mock-safe unavailable results do not expose an audio handoff.
```

## Follow-up

A later public contract conformance gate should make docs/API mismatches fail the
release readiness check. This checkpoint first resolves the known
`speak` / `create_output` mismatch identified by the v5.1.0 public contract
inventory.
