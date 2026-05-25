import os
from .models import MODEL_MASTER
from .secrets import GOOGLE_API_KEY, XAI_API_KEY, ELEVENLABS_API_KEY
from .defaults import (
    DEBUG_MASTER,
    DEBUG,
    DEBUG_ROUTER,
    DEBUG_FALLBACK,
    DEBUG_VTS,
    DEBUG_TTS,
    DEBUG_STT,
    SELECT_VOICE_INDEX,
    SELECT_TTS_MODEL_INDEX,
)
from .legacy import (
    VTS_DEBUG,
    INPUT_VOICE_ENABLED,
    OUTPUT_VOICE_ENABLED,
    ENABLE_VTS,
    VTS_EMOTION_ALIAS,
)
from registry.tts import TTS_MODEL_MASTER

# =========================================
# Runtime Flags
# =========================================

# Runtime feature toggles
# Legacy global flags kept for backward compatibility.
# Main runtime behavior is controlled by RuntimeConfig / presets.

# Engine selection
STT_ENGINE = "text"
TTS_ENGINE = "elevenlabs"


# =========================================
# User-Selectable Configuration
# =========================================

# Language selection
LANGUAGE_CODE = "ja-JP"


# =========================================
# Definition Tables
# =========================================

STRONG_CODE_KEYWORDS = [
    "error",
    "exception",
    "traceback",
    "bug",
    "fix",
    "コード",
    "python",
]

WEAK_CODE_KEYWORDS = [
    "function",
    "class",
    "method",
    "api",
]

LANG_MAP = {
    "ja-JP": "Japanese",
    "en-US": "English",
    "zh-CN": "Chinese",
    "ko-KR": "Korean",
    "fr-FR": "French",
    "de-DE": "German",
}

SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
}

# =========================================
# Derived Runtime Values
# =========================================

VOICE_MASTER = MODEL_MASTER.get("voices", [])

STT_LANGUAGE = LANGUAGE_CODE
TARGET_LANGUAGE = LANG_MAP.get(LANGUAGE_CODE, "English")

VTS_TOKEN_PATH = os.path.join("config", "tokens", "vts_token.json")
DEFAULT_EMOTION = "remove expressions"


def _select_voice_id() -> str | None:
    """Return the selected voice id if voice settings are configured."""
    if not VOICE_MASTER:
        return None

    if SELECT_VOICE_INDEX < 0 or SELECT_VOICE_INDEX >= len(VOICE_MASTER):
        return None

    selected_voice = VOICE_MASTER[SELECT_VOICE_INDEX]
    if not isinstance(selected_voice, dict):
        return None

    voice_id = selected_voice.get("id")
    return str(voice_id).strip() if voice_id else None


def _select_tts_model_id() -> str | None:
    """Return the selected TTS model id if the registry entry exists."""
    if SELECT_TTS_MODEL_INDEX < 0 or SELECT_TTS_MODEL_INDEX >= len(TTS_MODEL_MASTER):
        return None

    model_id = TTS_MODEL_MASTER[SELECT_TTS_MODEL_INDEX]
    return str(model_id).strip() if model_id else None


VOICE_ID = _select_voice_id()
TTS_MODEL_ID = _select_tts_model_id()


def require_tts_settings() -> None:
    """Validate settings that are required only when TTS is enabled."""
    if not ELEVENLABS_API_KEY:
        raise EnvironmentError(
            "ELEVENLABS_API_KEY is required when TTS is enabled. "
            "Set it in .env or use a text-only preset such as text_chat."
        )

    if not VOICE_MASTER:
        raise EnvironmentError(
            "VOICE_MASTER must contain at least one ElevenLabs voice id when TTS is enabled. "
            "Set VOICE_MASTER in .env or use a text-only preset such as text_chat."
        )

    if not VOICE_ID:
        raise EnvironmentError(
            "SELECT_VOICE_INDEX does not point to a valid VOICE_MASTER entry. "
            "Update SELECT_VOICE_INDEX or VOICE_MASTER before using TTS."
        )

    if not TTS_MODEL_ID:
        raise EnvironmentError(
            "SELECT_TTS_MODEL_INDEX does not point to a valid TTS model. "
            "Update SELECT_TTS_MODEL_INDEX or registry/tts.py before using TTS."
        )
