# config/calibration.py

# --- STT (Input) Calibration ---
SILENCE_DURATION = 1.2
ENERGY_THRESHOLD = 300
DYNAMIC_ENERGY_ADJUST = True

# --- LLM (Inference) Calibration ---
LLM_TEMPERATURE = 0.7  # Moved from engine.py
MAX_TOKENS_NORMAL = 1000

# --- TTS (Output) Calibration ---
VOICE_STABILITY = 0.35
SIMILARITY_BOOST = 0.8
VOICE_STYLE = 0.6        # Range: 0.0 to 1.0 (Higher means more expressive)
VOICE_SPEED = 1.0        # New: Speed control via ffplay
POST_SPEECH_PAUSE = 0.8  # New: Graceful pause after speech

