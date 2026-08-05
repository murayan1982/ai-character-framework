"""FW-RT6-0c Control B package-resource and artifact-root smoke.

Offline-safe: no provider SDK, network, microphone, playback, or VTS execution.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "f83d3fc72907885a370dc80cbe121c03a657c852"
EXPECTED_SURFACE = {
    "config/loader.py",
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v510_public_factory_signature_contract.md",
    "docs/v600_installable_sdk_contract.md",
    "framework/audio/_provider_adapter.py",
    "framework/facade.py",
    "framework/resources.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v510_public_contract_conformance_gate.py",
    "scripts/smoke_v600_resource_resolution.py",
}
FORBIDDEN_IMPORTS = ("openai", "elevenlabs", "pyvts", "websockets", "google.genai", "xai_sdk")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (("-c","core.safecrlf=false","diff","--name-only"), ("-c","core.safecrlf=false","diff","--cached","--name-only"), ("ls-files","--others","--exclude-standard")):
        paths.update(line.replace("\\", "/") for line in _git(*args).splitlines() if line.strip())
    return paths


@contextmanager
def _cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control B baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control B surface: {sorted(_changed_paths())}")
    print("[OK] Control B baseline and exact eleven-file surface match")


def check_package_resources_ignore_cwd() -> None:
    from config.loader import load_character_data, load_preset_file

    with tempfile.TemporaryDirectory(prefix="fw_rt6_0c_b_cwd_") as temp_name:
        temp = Path(temp_name)
        (temp / "presets").mkdir()
        (temp / "characters/default").mkdir(parents=True)
        (temp / "presets/text_chat.json").write_text(json.dumps({"app_preset": "cwd-decoy"}), encoding="utf-8")
        (temp / "characters/default/profile.json").write_text(json.dumps({"name": "cwd-decoy"}), encoding="utf-8")
        (temp / "characters/default/system.txt").write_text("cwd decoy", encoding="utf-8")
        with _cwd(temp):
            preset = load_preset_file("text_chat")
            character = load_character_data("default")
        _assert(preset.get("app_preset") == "text_chat", "CWD decoy preset was used")
        _assert(character.profile.get("name") == "default", "CWD decoy character was used")
        _assert(character.system_prompt != "cwd decoy", "CWD decoy system prompt was used")
    print("[OK] bundled preset and character resources ignore arbitrary CWD decoys")


def check_explicit_project_root_precedence() -> None:
    from config.loader import load_character_data, load_preset_file
    from framework.facade import _load_facade_config

    with tempfile.TemporaryDirectory(prefix="fw_rt6_0c_b_root_") as temp_name:
        root = Path(temp_name)
        (root / "presets").mkdir()
        (root / "characters/custom").mkdir(parents=True)
        preset = {
            "app_preset": "text_chat",
            "input_language_code": "ja",
            "output_language_code": "ja",
            "input_voice_enabled": False,
            "output_voice_enabled": False,
            "vts_enabled": False,
            "tts_provider": "none",
            "character_name": "custom",
        }
        (root / "presets/custom_text.json").write_text(json.dumps(preset), encoding="utf-8")
        (root / "characters/custom/profile.json").write_text(json.dumps({"name":"override"}), encoding="utf-8")
        (root / "characters/custom/system.txt").write_text("override prompt", encoding="utf-8")
        (root / "characters/custom/vts_hotkeys.json").write_text("{}", encoding="utf-8")

        loaded = load_preset_file("custom_text", project_root=root)
        character = load_character_data("custom", project_root=root)
        config = _load_facade_config("custom_text", None, project_root=root)
        _assert(loaded["character_name"] == "custom", "project-root preset override failed")
        _assert(character.profile.get("name") == "override", "project-root character override failed")
        _assert(config.system_prompt == "override prompt", "facade project-root propagation failed")
    print("[OK] explicit project_root takes precedence for preset and character resources")


def check_resource_name_safety() -> None:
    from framework.resources import resolve_character_directory, resolve_preset_resource
    for value in ("", ".", "..", "../private", "..\\private", "C:\\private", "characters/default", "bad\x00name"):
        for resolver in (resolve_preset_resource, resolve_character_directory):
            try:
                resolver(value)
            except ValueError as exc:
                message = str(exc)
                _assert("private" not in message.lower(), "resource error exposed the rejected path")
            else:
                raise AssertionError(f"unsafe resource name accepted: {value!r}")
    print("[OK] resource names reject traversal and errors stay path-safe")


def check_factory_signature() -> None:
    from framework import create_text_chat_session
    signature = inspect.signature(create_text_chat_session)
    _assert(list(signature.parameters) == ["preset","character_name","provider","model","project_root"], "text factory parameter drift")
    for name in ("preset","character_name","provider","model"):
        _assert(signature.parameters[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD, f"{name} compatibility changed")
    _assert(signature.parameters["project_root"].kind is inspect.Parameter.KEYWORD_ONLY, "project_root must be keyword-only")
    print("[OK] public text factory preserves four positional parameters and adds keyword-only project_root")


def check_voice_artifact_default() -> None:
    from framework.audio._provider_adapter import ElevenLabsVoiceOutputAdapter
    with tempfile.TemporaryDirectory(prefix="fw_rt6_0c_b_artifact_") as cwd_name:
        with _cwd(Path(cwd_name)):
            resolved = ElevenLabsVoiceOutputAdapter(project_root=None)._resolve_artifact_dir()
    expected = Path(tempfile.gettempdir()) / "ai-character-framework" / "voice_output"
    _assert(resolved == expected, f"unexpected system-temp artifact root: {resolved}")
    _assert(resolved != Path(cwd_name) / "temp" / "voice_output", "artifact root still depends on CWD")
    _assert(not resolved.exists() or resolved.is_dir(), "artifact root should not be created by resolution")
    print("[OK] public voice artifact default uses system temp instead of CWD")


def check_import_and_docs() -> None:
    import framework
    _assert(len(framework.__all__) == 95, "root-public count changed")
    _assert("framework.resources" not in framework.__all__, "internal resources module leaked root-public")
    imported = [name for name in FORBIDDEN_IMPORTS if name in sys.modules]
    _assert(not imported, f"provider modules imported: {imported}")
    for rel, marker in (
        ("docs/public_facade.md", "FW-RT6-0c-B-RESOURCE-RESOLUTION:BEGIN"),
        ("docs/app_integration_contract.md", "FW-RT6-0c-B-RESOURCE-RESOLUTION:BEGIN"),
        ("docs/v510_public_factory_signature_contract.md", "FW-RT6-0c-B-FACTORY-RESOURCE-ROOT:BEGIN"),
        ("docs/v600_installable_sdk_contract.md", "FW-RT6-0c-B-RESOURCE-RESOLUTION:BEGIN"),
    ):
        _assert(marker in (PROJECT_ROOT / rel).read_text(encoding="utf-8"), f"missing docs marker: {rel}")
    print("[OK] root-public compatibility and resource-resolution docs conform")


def main() -> None:
    check_repository_contract()
    check_package_resources_ignore_cwd()
    check_explicit_project_root_precedence()
    check_resource_name_safety()
    check_factory_signature()
    check_voice_artifact_default()
    check_import_and_docs()
    print("v600_resource_resolution_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 11")
    print("v600_cwd_preset_dependency: False")
    print("v600_cwd_character_dependency: False")
    print("v600_cwd_voice_artifact_dependency: False")
    print("v600_project_root_override_preserved: True")
    print("v600_root_public_name_count: 95")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-0c Control C")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-0c Control B resource-resolution smoke passed")


if __name__ == "__main__":
    main()
