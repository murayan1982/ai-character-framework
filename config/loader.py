from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

SUPPORTED_LANGUAGE_CODES = {"ja", "en"}

@dataclass
class RuntimeConfig:
    app_preset: str = "default"
    input_language_code: str = "ja"
    output_language_code: str = "en"

    input_voice_enabled: bool = False
    output_voice_enabled: bool = False
    vts_enabled: bool = False
    tts_provider: str = "none"

    emotion_enabled: bool = False
    vts_emotion_enabled: bool = False

    character_name: str = "default"
    character_profile: dict = field(default_factory=dict)
    system_prompt: str = ""


def load_preset_file(preset_name: str) -> dict:
    preset_path = Path("presets") / f"{preset_name}.json"

    if not preset_path.exists():
        raise FileNotFoundError(f"Preset file not found: {preset_path}")

    with preset_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_runtime_config() -> RuntimeConfig:
    load_dotenv()

    preset_name = os.getenv("APP_PRESET", "default")
    preset_data = load_preset_file(preset_name)

    input_language_code = normalize_language_code(
        preset_data.get("input_language_code", "ja"),
        default="ja",
    )
    output_language_code = normalize_language_code(
        preset_data.get("output_language_code", "ja"),
        default="en",
    )
    character_name = preset_data.get(
        "character_name",
        preset_data.get("character", "default"),
    )
    input_voice_enabled = preset_data.get("input_voice_enabled", False)
    output_voice_enabled = preset_data.get("output_voice_enabled", False)
    vts_enabled = preset_data.get("vts_enabled", False)
    tts_provider = preset_data.get("tts_provider", "none")
    emotion_enabled = bool(preset_data.get("emotion_enabled", False))
    vts_emotion_enabled = bool(preset_data.get("vts_emotion_enabled", False))

    profile, system_prompt = load_character_data(character_name)

    config = RuntimeConfig(
        app_preset=preset_name,
        input_language_code=input_language_code,
        output_language_code=output_language_code,

        input_voice_enabled=input_voice_enabled,
        output_voice_enabled=output_voice_enabled,
        vts_enabled=vts_enabled,
        tts_provider=tts_provider,

        emotion_enabled=emotion_enabled,
        vts_emotion_enabled=vts_emotion_enabled,

        character_name=character_name,
        character_profile=profile,
        system_prompt=system_prompt,
    )

    return config

def load_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_character_data(character_name: str) -> tuple[dict, str]:
    character_dir = Path("characters") / character_name
    profile_path = character_dir / "profile.json"
    system_path = character_dir / "system.txt"

    profile = {}
    system_prompt = ""

    if profile_path.exists():
        profile = load_json_file(profile_path)

    if system_path.exists():
        system_prompt = load_text_file(system_path)

    return profile, system_prompt

def normalize_language_code(code: str, default: str = "en") -> str:
    normalized = str(code).strip().lower()

    if normalized not in SUPPORTED_LANGUAGE_CODES:
        print(
            f"[Lang Warning] Unsupported language code: {code} -> fallback to {default}"
        )
        return default

    return normalized

if __name__ == "__main__":
    config = load_runtime_config()
    print(f"[Config] Loaded preset: {config.app_preset}")
    print(f"[Config] Character: {config.character_name}")
    print(f"[Config] System prompt: {config.system_prompt}")