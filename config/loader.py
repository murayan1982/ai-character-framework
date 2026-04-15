from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class RuntimeConfig:
    app_preset: str = "default"
    input_language_code: str = "ja"
    output_language_code: str = "ja"
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

    input_language_code = preset_data.get("input_language_code", "ja")
    output_language_code = preset_data.get("output_language_code", "ja")
    character_name = preset_data.get("character", "default")

    profile, system_prompt = load_character_data(character_name)

    config = RuntimeConfig(
        app_preset=preset_name,
        input_language_code=input_language_code,
        output_language_code=output_language_code,
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

if __name__ == "__main__":
    config = load_runtime_config()
    print(f"[Config] Loaded preset: {config.app_preset}")
    print(f"[Config] Character: {config.character_name}")
    print(f"[Config] System prompt: {config.system_prompt}")