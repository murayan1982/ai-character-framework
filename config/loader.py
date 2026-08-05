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


def load_preset_file(
    preset_name: str,
    *,
    project_root: str | Path | None = None,
) -> dict:
    """Load preset JSON from an explicit project root or package resources."""

    from framework.resources import read_json_resource, resolve_preset_resource

    resource = resolve_preset_resource(preset_name, project_root=project_root)
    data = read_json_resource(resource, label="preset")
    if not isinstance(data, dict):
        raise ValueError("Preset resource must contain a JSON object.")
    return data


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


def load_character_data(
    character_name: str,
    *,
    project_root: str | Path | None = None,
) -> CharacterData:
    """Load character data from an explicit project root or package resources.

    A missing character directory is an error. Missing files inside an existing
    character directory retain the legacy empty-value fallback.
    """

    from framework.resources import (
        read_json_resource,
        read_text_resource,
        resolve_character_directory,
    )

    character_dir = resolve_character_directory(
        character_name,
        project_root=project_root,
    )
    profile_resource = character_dir.joinpath(CHARACTER_PROFILE_FILE)
    system_resource = character_dir.joinpath(CHARACTER_SYSTEM_FILE)
    vts_resource = character_dir.joinpath(CHARACTER_VTS_HOTKEYS_FILE)

    profile: dict = {}
    system_prompt = ""
    vts_hotkeys: dict = {}

    if profile_resource.is_file():
        value = read_json_resource(profile_resource, label="character profile")
        if isinstance(value, dict):
            profile = value
        else:
            print("[Config] Character profile must contain a JSON object.")
    else:
        print("[Config] Character profile resource not found.")

    if system_resource.is_file():
        system_prompt = read_text_resource(system_resource, label="character system prompt")
    else:
        print("[Config] Character system prompt resource not found.")

    if vts_resource.is_file():
        try:
            value = read_json_resource(vts_resource, label="character VTS hotkeys")
            if isinstance(value, dict):
                vts_hotkeys = value
            else:
                print("[Config] Character VTS hotkeys must contain a JSON object.")
        except ValueError:
            print("[Config] Failed to load character VTS hotkeys resource.")
    else:
        print("[Config] Character VTS hotkeys resource not found.")

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


def load_runtime_config(
    *,
    project_root: str | Path | None = None,
) -> RuntimeConfig:
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
    preset_data = load_preset_file(preset_name, project_root=project_root)

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
    character_data = load_character_data(
        character_name,
        project_root=project_root,
    )

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