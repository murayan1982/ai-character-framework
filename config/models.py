# config/models.py

# --- Google (Gemini) ---
GOOGLE_MODELS = [
    'gemini-2.5-flash',  # 0
    'gemini-2.5-pro',  # 1
    'gemini-2.0-flash',  # 2
    'gemini-2.0-flash-001',  # 3
    'gemini-2.0-flash-lite-001',  # 4
    'gemini-2.0-flash-lite',  # 5
    'gemini-2.5-flash-preview-tts',  # 6
    'gemini-2.5-pro-preview-tts',  # 7
    'gemma-3-1b-it',  # 8
    'gemma-3-4b-it',  # 9
    'gemma-3-12b-it',  # 10
    'gemma-3-27b-it',  # 11
    'gemma-3n-e4b-it',  # 12
    'gemma-3n-e2b-it',  # 13
    'gemma-4-26b-a4b-it',  # 14
    'gemma-4-31b-it',  # 15
    'gemini-flash-latest',  # 16
    'gemini-flash-lite-latest',  # 17
    'gemini-pro-latest',  # 18
    'gemini-2.5-flash-lite',  # 19
    'gemini-2.5-flash-image',  # 20
    'gemini-3-pro-preview',  # 21
    'gemini-3-flash-preview',  # 22
    'gemini-3.1-pro-preview',  # 23
    'gemini-3.1-pro-preview-customtools',  # 24
    'gemini-3.1-flash-lite-preview',  # 25
    'gemini-3-pro-image-preview',  # 26
    'nano-banana-pro-preview',  # 27
    'gemini-3.1-flash-image-preview',  # 28
    'lyria-3-clip-preview',  # 29
    'lyria-3-pro-preview',  # 30
    'gemini-robotics-er-1.5-preview',  # 31
    'gemini-2.5-computer-use-preview-10-2025',  # 32
    'deep-research-pro-preview-12-2025'  # 33
]

# --- TTS Voices (ElevenLabs) ---
VOICE_MASTER = [
    {"name": "Nicole - Bright, Friendly and Clear", "id": "aUNOP2y8xEvi4nZebjIw"},
]

# --- TTS Engines (ElevenLabs) ---
TTS_MODEL_MASTER = [
    'eleven_v3',  # 0
    'eleven_multilingual_v2',  # 1
    'eleven_flash_v2_5',  # 2
    'eleven_turbo_v2_5',  # 3
    'eleven_turbo_v2',  # 4
    'eleven_flash_v2',  # 5
    'eleven_english_sts_v2',  # 6
    'eleven_monolingual_v1',  # 7
    'eleven_multilingual_sts_v2',  # 8
    'eleven_multilingual_v1'  # 9
]
# --- OpenAI  ---
OPENAI_MODELS = [
    "gpt-4o",                # 0
    "gpt-4o-mini",           # 1
    "o1-preview"             # 2
]

# --- xAI ---
XAI_MODELS = [
    "grok-beta",             # 0
    "grok-2"                 # 1
]

# Master Dictionarys
MODEL_MASTER = {
    "google": GOOGLE_MODELS,
    "voices": VOICE_MASTER,
    "tts_models": TTS_MODEL_MASTER,
    "xai": XAI_MODELS
}
