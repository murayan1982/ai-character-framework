from dataclasses import dataclass
import re

VALID_EMOTIONS = {
    "neutral",
    "happy",
    "sad",
    "angry",
    "surprised",
    "confused",
}

EMOTION_TAG_PATTERN = re.compile(
    r"^\s*\[emotion:(?P<emotion>[a-zA-Z0-9_]+)\]\s*",
    re.IGNORECASE,
)


@dataclass
class EmotionResult:
    emotion: str
    clean_text: str
    raw_text: str


def normalize_emotion(emotion: str | None) -> str:
    if not emotion:
        return "neutral"

    value = emotion.strip().lower()
    if value in VALID_EMOTIONS:
        return value
    return "neutral"


def parse_emotion_response(raw_text: str) -> EmotionResult:
    text = raw_text or ""
    match = EMOTION_TAG_PATTERN.match(text)

    if not match:
        return EmotionResult(
            emotion="neutral",
            clean_text=text.strip(),
            raw_text=text,
        )

    emotion = normalize_emotion(match.group("emotion"))
    clean_text = text[match.end():].lstrip()

    return EmotionResult(
        emotion=emotion,
        clean_text=clean_text,
        raw_text=text,
    )