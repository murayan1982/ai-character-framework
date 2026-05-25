"""
Legacy compatibility definitions.

This module keeps old global flags and compatibility aliases that are
still referenced by older paths. These values are not the preferred
source of truth for new runtime behavior.

Main runtime behavior should be controlled by RuntimeConfig, presets,
and character-level configuration.
"""

from .defaults import DEBUG_VTS

# Backward compatibility debug alias
VTS_DEBUG = DEBUG_VTS

# Legacy global runtime flags kept for compatibility only.
# Main runtime behavior is controlled by RuntimeConfig / presets.
INPUT_VOICE_ENABLED = False
OUTPUT_VOICE_ENABLED = False
ENABLE_VTS = True

# Legacy fallback aliases for old change_expression() path.
# v1.5+ main emotion flow uses character-level vts_hotkeys mapping.
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