import os
from dotenv import load_dotenv
from .models import MODEL_MASTER

load_dotenv()

# =========================================
# Environment / API Keys
# =========================================

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")


# =========================================
# Runtime Flags
# =========================================

# Master debug switch
DEBUG_MASTER = True

# Component debug flags
DEBUG = DEBUG_MASTER
DEBUG_ROUTER = DEBUG_MASTER
DEBUG_FALLBACK = DEBUG_MASTER
DEBUG_VTS = DEBUG_MASTER
DEBUG_TTS = DEBUG_MASTER
DEBUG_STT = DEBUG_MASTER

# Backward compatibility
VTS_DEBUG = DEBUG_VTS

# Runtime feature toggles
# Legacy global flags kept for backward compatibility.
# Main runtime behavior is controlled by RuntimeConfig / presets.
INPUT_VOICE_ENABLED = False
OUTPUT_VOICE_ENABLED = False
ENABLE_VTS = True

# Engine selection
STT_ENGINE = "text"
TTS_ENGINE = "elevenlabs"


# =========================================
# User-Selectable Configuration
# =========================================

# Voice / TTS selection
SELECT_VOICE_INDEX = 0
SELECT_TTS_MODEL_INDEX = 2

# Language selection
LANGUAGE_CODE = "ja-JP"


# =========================================
# Definition Tables
# =========================================

LLM_CATALOG = {
    "gemini_fast": {
        "provider": "google",
        #"model": "gemini-2.5-flash",
        "model": "gemini-3.1-flash-lite-preview",
    },
    "grok_fast": {
        "provider": "xai",
        "model": "grok-4-fast-non-reasoning",
    },
    "grok_reasoning": {
        "provider": "xai",
        "model": "grok-4-fast-reasoning",
    },
}

LLM_ROUTES = {
    "chat": {
        "primary": "gemini_fast",
        "fallback": "grok_fast",
    },
    "code": {
        "primary": "grok_fast",
        "fallback": "gemini_fast",
    },
}

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

# Legacy fallback aliases for old change_expression() path.
# v1.5 main emotion flow uses character-level vts_hotkeys mapping.
VTS_EMOTION_ALIAS = {
    "smile": "heart eyes",
    "happy": "heart eyes",
    "grin": "heart eyes",
    "laugh": "heart eyes",
    "joy": "heart eyes",
    "love": "heart eyes",
    "sad": "eyes cry",
    "cry": "eyes cry",
    "angry": "angry sign",
    "mad": "angry sign",
    "surprised": "shock sign",
    "surprise": "shock sign",
    "shock": "shock sign",
    "neutral": "remove expressions",
}


# =========================================
# Derived Runtime Values
# =========================================

VOICE_MASTER = MODEL_MASTER.get("voices", [])
TTS_MODEL_MASTER = MODEL_MASTER.get("tts_models", [])

STT_LANGUAGE = LANGUAGE_CODE
TARGET_LANGUAGE = LANG_MAP.get(LANGUAGE_CODE, "English")

VTS_TOKEN_PATH = os.path.join("config", "tokens", "vts_token.json")
DEFAULT_EMOTION = "remove expressions"

if not VOICE_MASTER:
    raise EnvironmentError(
        "VOICE_MASTER is not set. Please add your ElevenLabs Voice ID to .env."
    )
if SELECT_VOICE_INDEX >= len(VOICE_MASTER):
    raise IndexError("SELECT_VOICE_INDEX is out of range.")

VOICE_ID = VOICE_MASTER[SELECT_VOICE_INDEX]["id"]

if SELECT_TTS_MODEL_INDEX >= len(TTS_MODEL_MASTER):
    raise IndexError("SELECT_TTS_MODEL_INDEX is out of range.")

TTS_MODEL_ID = TTS_MODEL_MASTER[SELECT_TTS_MODEL_INDEX]