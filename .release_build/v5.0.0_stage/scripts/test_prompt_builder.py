from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.prompt_builder import (
    build_final_system_instruction,
    should_apply_voice_output_policy,
)


@dataclass
class DummyConfig:
    output_language_code: str = "ja"
    output_voice_enabled: bool = False
    tts_provider: str = "none"
    emotion_enabled: bool = False
    system_prompt: str = "You are a helpful AI assistant."


def main() -> None:
    text_config = DummyConfig()
    text_prompt = build_final_system_instruction(text_config)

    assert should_apply_voice_output_policy(text_config) is False
    assert "You MUST write your entire response in Japanese." in text_prompt
    assert "Voice output is enabled." not in text_prompt
    assert "At the beginning of every assistant response" not in text_prompt
    assert "You are a helpful AI assistant." in text_prompt

    voice_config = DummyConfig(
        output_voice_enabled=True,
        tts_provider="local",
    )
    voice_prompt = build_final_system_instruction(voice_config)

    assert should_apply_voice_output_policy(voice_config) is True
    assert "You MUST write your entire response in Japanese." in voice_prompt
    assert "Voice output is enabled." in voice_prompt
    assert "You are a helpful AI assistant." in voice_prompt

    assert voice_prompt.index("You MUST write your entire response") < voice_prompt.index(
        "Voice output is enabled."
    )
    assert voice_prompt.index("Voice output is enabled.") < voice_prompt.index(
        "You are a helpful AI assistant."
    )

    emotion_config = DummyConfig(emotion_enabled=True)
    emotion_prompt = build_final_system_instruction(emotion_config)

    assert "Voice output is enabled." not in emotion_prompt
    assert "At the beginning of every assistant response" in emotion_prompt
    assert emotion_prompt.index("You MUST write your entire response") < emotion_prompt.index(
        "At the beginning of every assistant response"
    )
    assert emotion_prompt.index("At the beginning of every assistant response") < emotion_prompt.index(
        "You are a helpful AI assistant."
    )

    print("[OK] prompt builder applies voice output policy only for voice-enabled configs")


if __name__ == "__main__":
    main()
