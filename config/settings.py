# config/settings.py
import os
from dotenv import load_dotenv
from .models import MODEL_MASTER

# read .env 
load_dotenv()

# --- Get API Key ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# --- LLM Provider Selection ---
# "google" or "xai"
LLM_PROVIDER = "xai"

# Define current index for each provider (Set based on models.py tables)
# google table size: 34, xai table size: 6
CURRENT_SELECTIONS = {
    "google": 25,  # gemini-3.1-flash-lite-preview
    "xai": 5      # grok-4-1-fast-non-reasoning
}
# --- Dynamic Assignment (LLM Model) ---
try:
    target_index = CURRENT_SELECTIONS[LLM_PROVIDER]
    ACTIVE_LLM_MODEL = MODEL_MASTER[LLM_PROVIDER][target_index]
except (KeyError, IndexError) as e:
    # Failsafe: Default to Gemini
    print(f"[Config Error]: Invalid provider or index ({e}). Falling back to Gemini.")
    ACTIVE_LLM_MODEL = MODEL_MASTER["google"][0]

# --- TTS & Voice Selection ---
SELECT_VOICE_INDEX = 0
SELECT_TTS_MODEL_INDEX = 2

VOICE_ID = MODEL_MASTER["voices"][SELECT_VOICE_INDEX]["id"]
TTS_MODEL_ID = MODEL_MASTER["tts_models"][SELECT_TTS_MODEL_INDEX]

# --- Engine Switches ---
STT_ENGINE = "text"        # "text", "google", "whisper"
TTS_ENGINE = "elevenlabs"  # "elevenlabs", "none"

# --- STT Settings ---
LANGUAGE_CODE = "ja-JP"
LANG_MAP = {
    "ja-JP": "Japanese",
    "en-US": "English",
    "zh-CN": "Chinese",
    "ko-KR": "Korean",
    "fr-FR": "French",
    "de-DE": "German"
}
STT_LANGUAGE = LANGUAGE_CODE
TARGET_LANGUAGE = LANG_MAP.get(LANGUAGE_CODE, "English")

# --- Interaction Mode ---
# True: Use Voice, False: Use Text
INPUT_VOICE_ENABLED = False   # If True, STT starts
OUTPUT_VOICE_ENABLED = False  # If True, TTS speaks

# --- google safety settings ---
SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
}

# --- VTube Studio Settings ---
VTS_TOKEN_PATH = os.path.join("config", "tokens", "vts_token.json")
