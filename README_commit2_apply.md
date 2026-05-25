# Commit 2 apply notes

Commit message:

```text
feat: add public voice output session contract
```

## Add new files

Copy these files into the repo:

```text
framework/audio/__init__.py
framework/audio/voice_output.py
```

## Update `framework/__init__.py`

Add these imports alongside the existing public facade exports:

```python
from .audio import (
    VoiceOutputRequest,
    VoiceOutputResult,
    VoiceOutputSession,
    VoiceOutputSessionInfo,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
    create_voice_output_session,
)
```

Add these names to `__all__`:

```python
"VoiceOutputRequest",
"VoiceOutputResult",
"VoiceOutputSession",
"VoiceOutputSessionInfo",
"VoiceSynthesisRequest",
"VoiceSynthesisResult",
"create_voice_output_session",
```

## Optional: update `framework/facade.py`

If `facade.py` is the public API aggregation point, add the same re-export there:

```python
from .audio import (
    VoiceOutputRequest,
    VoiceOutputResult,
    VoiceOutputSession,
    VoiceOutputSessionInfo,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
    create_voice_output_session,
)
```

And add the same names to its `__all__` if it has one.

## Smoke check snippet

This should run without importing provider-specific TTS modules:

```powershell
python - <<'PY'
import sys
import framework

for name in [
    "create_voice_output_session",
    "VoiceOutputSession",
    "VoiceOutputSessionInfo",
    "VoiceOutputRequest",
    "VoiceOutputResult",
]:
    assert hasattr(framework, name), name

session = framework.create_voice_output_session()
info = session.info()
assert info.session_type == "voice_output"
assert info.provider_details_exposed is False

result = session.create_output(
    framework.VoiceOutputRequest(
        text="こんにちは。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
    )
)
assert result.request_state == "unavailable"
assert result.audio_ready is False

for forbidden in [
    "tts.voice_engine",
    "elevenlabs",
]:
    assert forbidden not in sys.modules, forbidden

print("voice_output_contract_smoke: OK")
PY
```

## Full checks

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/check_release_package.py
```
