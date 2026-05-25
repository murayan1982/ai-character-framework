import json
import os
from dotenv import load_dotenv
from registry.tts import TTS_MODEL_MASTER

load_dotenv()

# =========================================
# Google (Gemini)
# =========================================

GOOGLE_MODELS = [
    "gemini-2.5-flash",  # 0
    "gemini-2.5-pro",  # 1
    "gemini-2.0-flash",  # 2
    "gemini-2.0-flash-001",  # 3
    "gemini-2.0-flash-lite-001",  # 4
    "gemini-2.0-flash-lite",  # 5
    "gemini-2.5-flash-preview-tts",  # 6
    "gemini-2.5-pro-preview-tts",  # 7
    "gemma-3-1b-it",  # 8
    "gemma-3-4b-it",  # 9
    "gemma-3-12b-it",  # 10
    "gemma-3-27b-it",  # 11
    "gemma-3n-e4b-it",  # 12
    "gemma-3n-e2b-it",  # 13
    "gemma-4-26b-a4b-it",  # 14
    "gemma-4-31b-it",  # 15
    "gemini-flash-latest",  # 16
    "gemini-flash-lite-latest",  # 17
    "gemini-pro-latest",  # 18
    "gemini-2.5-flash-lite",  # 19
    "gemini-2.5-flash-image",  # 20
    "gemini-3-pro-preview",  # 21
    "gemini-3-flash-preview",  # 22
    "gemini-3.1-pro-preview",  # 23
    "gemini-3.1-pro-preview-customtools",  # 24
    "gemini-3.1-flash-lite-preview",  # 25
    "gemini-3-pro-image-preview",  # 26
    "nano-banana-pro-preview",  # 27
    "gemini-3.1-flash-image-preview",  # 28
    "lyria-3-clip-preview",  # 29
    "lyria-3-pro-preview",  # 30
    "gemini-robotics-er-1.5-preview",  # 31
    "gemini-2.5-computer-use-preview-10-2025",  # 32
    "deep-research-pro-preview-12-2025",  # 33
]

# =========================================
# xAI (Grok)
# =========================================

XAI_MODELS = [
    "grok-3",  # 0
    "grok-3-mini",  # 1
    "grok-4-0709",  # 2
    "grok-4-1-fast-non-reasoning",  # 3
    "grok-4-1-fast-reasoning",  # 4
    "grok-4-fast-non-reasoning",  # 5
    "grok-4-fast-reasoning",  # 6
    "grok-4.20-0309-non-reasoning",  # 7
    "grok-4.20-0309-reasoning",  # 8
    "grok-4.20-multi-agent-0309",  # 9
    "grok-code-fast-1",  # 10
    "grok-imagine-image",  # 11
    "grok-imagine-image-pro",  # 12
    "grok-imagine-video",  # 13
]

# =========================================
# OpenAI
# =========================================

OPENAI_MODELS = [
    "gpt-4o",  # 0
    "gpt-4o-mini",  # 1
    "o1-preview",  # 2
]

# =========================================
# ElevenLabs
# =========================================

raw_voice_master = os.getenv("VOICE_MASTER", "[]")

try:
    VOICE_MASTER = json.loads(raw_voice_master)
except Exception as e:
    print("VOICE_MASTER parse error:", e)
    VOICE_MASTER = []

# =========================================
# Master Registry
# =========================================

MODEL_MASTER = {
    "google": GOOGLE_MODELS,
    "xai": XAI_MODELS,
    "openai": OPENAI_MODELS,
    "voices": VOICE_MASTER,
    "tts_models": TTS_MODEL_MASTER,
}