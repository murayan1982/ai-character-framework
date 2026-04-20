"""
LLM registry definitions for provider/model selection.

This module owns the static LLM catalog and route definitions.
It should not contain runtime secrets or user-specific environment values.
"""

LLM_CATALOG = {
    "gemini_fast": {
        "provider": "google",
        #"model": "gemini-3.1-flash-lite-preview",
        "model": "gemini-does-not-exist",
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