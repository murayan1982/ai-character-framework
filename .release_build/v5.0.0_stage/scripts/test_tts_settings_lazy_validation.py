from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    import config.settings as settings

    assert hasattr(settings, "require_tts_settings")
    assert hasattr(settings, "VOICE_MASTER")
    assert hasattr(settings, "VOICE_ID")
    assert hasattr(settings, "TTS_MODEL_ID")

    original_api_key = settings.ELEVENLABS_API_KEY
    original_voice_master = settings.VOICE_MASTER
    original_voice_id = settings.VOICE_ID
    original_tts_model_id = settings.TTS_MODEL_ID

    try:
        settings.ELEVENLABS_API_KEY = ""
        settings.VOICE_MASTER = []
        settings.VOICE_ID = None
        settings.TTS_MODEL_ID = None

        try:
            settings.require_tts_settings()
        except EnvironmentError:
            pass
        else:
            raise AssertionError(
                "require_tts_settings() should fail when TTS settings are missing"
            )
    finally:
        settings.ELEVENLABS_API_KEY = original_api_key
        settings.VOICE_MASTER = original_voice_master
        settings.VOICE_ID = original_voice_id
        settings.TTS_MODEL_ID = original_tts_model_id

    print("[OK] TTS settings validation is delayed until TTS is required")


if __name__ == "__main__":
    main()
