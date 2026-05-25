from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


SUPPORTED_LANGUAGE_CODES = {"ja", "en"}

CHARACTER_PROFILE_FILE = "profile.json"
CHARACTER_SYSTEM_FILE = "system.txt"
CHARACTER_VTS_HOTKEYS_FILE = "vts_hotkeys.json"


@dataclass
class CharacterData:
    """
    Character-specific data loaded from characters/<character_name>/.

    Character data describes who the AI character is:
    - profile metadata
    - system prompt / behavior instruction
    - optional VTS hotkey mapping

    Runtime mode selection such as voice, text, VTS enablement, and language
    belongs to presets and RuntimeConfig, not character files.
    """

    profile: dict = field(default_factory=dict)
    system_prompt: str = ""
    vts_hotkeys: dict = field(default_factory=dict)


@dataclass
class RuntimeConfig:
    """
    Runtime source of truth for application behavior.

    Values are assembled at startup from:
    - preset data for runtime mode selection
    - character data for character-specific differences

    After initialization, runtime behavior should read from RuntimeConfig
    rather than older global config paths.
    """

    app_preset: str = "default"
    input_language_code: str = "ja"
    output_language_code: str = "en"

    input_voice_enabled: bool = False
    output_voice_enabled: bool = False
    vts_enabled: bool = False
    tts_provider: str = "none"
    allow_text_fallback_during_stt: bool = False

    emotion_enabled: bool = False
    vts_emotion_enabled: bool = False

    character_name: str = "default"
    character_profile: dict = field(default_factory=dict)
    system_prompt: str = ""
    vts_hotkeys: dict = field(default_factory=dict)


def load_preset_file(preset_name: str) -> dict:
    """
    Load preset JSON for runtime mode selection.
    """

    preset_path = Path("presets") / f"{preset_name}.json"

    if not preset_path.exists():
        raise FileNotFoundError(f"Preset file not found: {preset_path}")

    with preset_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json_file(path: Path) -> dict:
    """
    Load a JSON file as a dictionary.
    """

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print(f"[Config] JSON file must contain an object: {path}")
        return {}

    return data


def load_text_file(path: Path) -> str:
    """
    Load a UTF-8 text file and trim surrounding whitespace.
    """

    with path.open("r", encoding="utf-8") as f:
        return f.read().strip()


def load_character_data(character_name: str) -> CharacterData:
    """
    Load character-specific differences.

    Character data is responsible for:
    - profile
    - system prompt
    - VTS hotkey mapping

    Character data is not responsible for general runtime mode selection.
    Missing files fall back to empty values so minimal characters can be used
    during development.
    """

    character_dir = Path("characters") / character_name
    profile_path = character_dir / CHARACTER_PROFILE_FILE
    system_path = character_dir / CHARACTER_SYSTEM_FILE
    vts_hotkeys_path = character_dir / CHARACTER_VTS_HOTKEYS_FILE

    profile = {}
    system_prompt = ""
    vts_hotkeys = {}

    if profile_path.exists():
        profile = load_json_file(profile_path)
    else:
        print(f"[Config] Character profile not found: {profile_path}")

    if system_path.exists():
        system_prompt = load_text_file(system_path)
    else:
        print(f"[Config] Character system prompt not found: {system_path}")

    if vts_hotkeys_path.exists():
        try:
            vts_hotkeys = load_json_file(vts_hotkeys_path)
        except Exception as e:
            print(f"[Config] Failed to load VTS hotkeys: {e}")
            vts_hotkeys = {}
    else:
        print(f"[Config] Character VTS hotkeys not found: {vts_hotkeys_path}")

    return CharacterData(
        profile=profile,
        system_prompt=system_prompt,
        vts_hotkeys=vts_hotkeys,
    )


def normalize_language_code(code: str, default: str = "en") -> str:
    """
    Normalize language code to the runtime-supported short form.
    """

    normalized = str(code).strip().lower()

    if normalized not in SUPPORTED_LANGUAGE_CODES:
        print(
            f"[Lang Warning] Unsupported language code: {code} -> fallback to {default}"
        )
        return default

    return normalized


def load_runtime_config() -> RuntimeConfig:
    """
    Assemble RuntimeConfig from preset data and character data.

    Loading order:
    1. Read APP_PRESET from environment
    2. Load preset JSON
    3. Normalize preset-facing runtime values
    4. Load character-specific data
    5. Assemble RuntimeConfig as the runtime source of truth
    """

    # APP_PRESET is selected through environment setup.
    load_dotenv()

    # 1) Select startup preset.
    preset_name = os.getenv("APP_PRESET", "default")
    preset_data = load_preset_file(preset_name)

    # 2) Read runtime-facing values from preset data.
    input_language_code = normalize_language_code(
        preset_data.get("input_language_code", "ja"),
        default="ja",
    )
    output_language_code = normalize_language_code(
        preset_data.get("output_language_code", "ja"),
        default="en",
    )

    # New presets should use "character_name".
    # "character" is kept only as a legacy fallback for older preset files.
    character_name = preset_data.get(
        "character_name",
        preset_data.get("character", "default"),
    )

    input_voice_enabled = preset_data.get("input_voice_enabled", False)
    output_voice_enabled = preset_data.get("output_voice_enabled", False)
    vts_enabled = preset_data.get("vts_enabled", False)
    tts_provider = preset_data.get("tts_provider", "none")
    allow_text_fallback_during_stt = bool(
        preset_data.get("allow_text_fallback_during_stt", False)
    )
    emotion_enabled = bool(preset_data.get("emotion_enabled", False))
    vts_emotion_enabled = bool(preset_data.get("vts_emotion_enabled", False))

    # 3) Load character-specific data.
    character_data = load_character_data(character_name)

    # 4) Assemble RuntimeConfig as the runtime source of truth.
    return RuntimeConfig(
        app_preset=preset_name,
        input_language_code=input_language_code,
        output_language_code=output_language_code,
        input_voice_enabled=input_voice_enabled,
        output_voice_enabled=output_voice_enabled,
        vts_enabled=vts_enabled,
        tts_provider=tts_provider,
        allow_text_fallback_during_stt=allow_text_fallback_during_stt,
        emotion_enabled=emotion_enabled,
        vts_emotion_enabled=vts_emotion_enabled,
        character_name=character_name,
        character_profile=character_data.profile,
        system_prompt=character_data.system_prompt,
        vts_hotkeys=character_data.vts_hotkeys,
    )


if __name__ == "__main__":
    config = load_runtime_config()
    print(f"[Config] Loaded preset: {config.app_preset}")
    print(f"[Config] Character: {config.character_name}")
    print(f"[Config] System prompt: {config.system_prompt}")
    print(f"VTS Hotkeys: {config.vts_hotkeys}")