# config/settings.py
import os
from dotenv import load_dotenv
from .models import MODEL_MASTER

# read .env 
load_dotenv()

# --- Get API Key ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# --- Index Selection ---
SELECT_LLM_INDEX = 25
SELECT_VOICE_INDEX = 0
SELECT_TTS_MODEL_INDEX = 2

# ---  Mode Switches ---
STT_ENGINE = "text"        # "text", "google", "whisper"
TTS_ENGINE = "elevenlabs"  # "elevenlabs", "none"

# --- Dynamic Assignment ---
ACTIVE_LLM_MODEL = MODEL_MASTER["google"][SELECT_LLM_INDEX]
VOICE_ID = MODEL_MASTER["voices"][SELECT_VOICE_INDEX]["id"]
TTS_MODEL_ID = MODEL_MASTER["tts_models"][SELECT_TTS_MODEL_INDEX]

# --- STT Settings ---
STT_LANGUAGE = "ja-JP"
TARGET_LANGUAGE = "Japanese"

# --- Interaction Mode ---
# True: Use Voice, False: Use Text
INPUT_VOICE_ENABLED = True   # If True, STT starts
OUTPUT_VOICE_ENABLED = True  # If True, TTS speaks

# --- google safety settings ---
SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
}

# --- VTube Studio Settings ---
VTS_TOKEN_PATH = os.path.join("config", "tokens", "vts_token.json")
