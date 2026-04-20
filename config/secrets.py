"""
Environment-backed secrets.

This module owns API keys and other secret values loaded from .env.
It should not contain runtime defaults or registry definitions.
"""
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")