from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


STANDARD_EMOTIONS = {
    "neutral",
    "happy",
    "sad",
    "angry",
    "surprised",
    "confused",
}


@dataclass
class EmotionResult:
    emotion: str
    clean_text: str
    raw_text: str


def normalize_emotion(emotion: str | None) -> str:
    if not emotion:
        return "neutral"

    value = emotion.strip().lower()
    if value in STANDARD_EMOTIONS:
        return value

    return "neutral"


def parse_emotion_response(raw_text: str) -> EmotionResult:
    """
    Parse leading emotion tag from assistant response.

    Expected format:
        [emotion:happy]
        Hello

    Fallback:
        - invalid emotion -> neutral
        - no tag -> neutral
    """
    if not raw_text:
        return EmotionResult(
            emotion="neutral",
            clean_text="",
            raw_text="",
        )

    text = raw_text.strip()

    match = re.match(r"^\[emotion:(.*?)\]\s*", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return EmotionResult(
            emotion="neutral",
            clean_text=text,
            raw_text=raw_text,
        )

    emotion = normalize_emotion(match.group(1))
    clean_text = re.sub(
        r"^\[emotion:(.*?)\]\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    return EmotionResult(
        emotion=emotion,
        clean_text=clean_text,
        raw_text=raw_text,
    )


def resolve_emotion_hotkey(
    emotion: str | None,
    vts_hotkeys: dict | None,
) -> Optional[str]:
    """
    Resolve framework emotion key to character-specific VTS hotkey name.

    Rules:
        - unknown emotion -> neutral
        - missing mapping -> None
        - null mapping -> None
        - empty string mapping -> None
    """
    normalized = normalize_emotion(emotion)

    if not isinstance(vts_hotkeys, dict):
        return None

    hotkey_name = vts_hotkeys.get(normalized)

    if hotkey_name is None:
        return None

    if not isinstance(hotkey_name, str):
        return None

    hotkey_name = hotkey_name.strip()
    if not hotkey_name:
        return None

    return hotkey_name