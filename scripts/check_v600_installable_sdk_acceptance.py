"""Aggregate FW-RT6-0c Control D installable SDK acceptance checker.

Offline-safe: isolated installation reuses the accepted Control C helpers with
PIP_NO_INDEX and local inputs. No provider, network, microphone, playback, VTS,
or host-application operation is performed.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    try:
        from setuptools._vendor import tomli as tomllib
    except ImportError:
        from pip._vendor import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTROL_C_COMMIT = "cf9949579d971de68b2b763928f1c8052cf49921"
EXPECTED_CONTROL_B_COMMIT = "e51a07e62045b185799cd32d64127170c30ebe56"
EXPECTED_CONTROL_A_COMMIT = "f83d3fc72907885a370dc80cbe121c03a657c852"
EXPECTED_CONTROL_A_PARENT = "f082a027dbc49de04bd046642ae0f06dfd2e48ca"

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_installable_sdk_acceptance.py",
}
CONTROL_A_SUBJECT = "build/test: add installable SDK package metadata"
CONTROL_A_SURFACE = {
    "README.md",
    "characters/__init__.py",
    "docs/v600_installable_sdk_contract.md",
    "presets/__init__.py",
    "pyproject.toml",
    "scripts/smoke_v600_package_metadata.py",
}
CONTROL_B_SUBJECT = "refactor/test: add package resource resolution"
CONTROL_B_SURFACE = {
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
CONTROL_C_SUBJECT = "build/test: verify isolated SDK installation"
CONTROL_C_SURFACE = {
    "README.md",
    "docs/v600_installable_sdk_contract.md",
    "examples/public_text_chat.py",
    "examples/minimal_app_text_chat.py",
    "examples/app_error_handling.py",
    "examples/app_streaming_text_chat.py",
    "examples/app_reset_text_chat.py",
    "examples/app_voice_output_integration.py",
    "scripts/check_v600_installable_sdk.py",
}
EXAMPLE_PATHS = tuple(sorted(CONTROL_C_SURFACE - {
    "README.md",
    "docs/v600_installable_sdk_contract.md",
    "scripts/check_v600_installable_sdk.py",
}))
FORBIDDEN_IMPORTS = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websockets",
    "google.genai",
    "xai_sdk",
    "speech_recognition",
    "pyaudio",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _commit_subject(commit: str) -> str:
    return _git("show", "-s", "--format=%s", commit)


def _commit_parent(commit: str) -> str:
    return _git("rev-parse", f"{commit}^")


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
        if line.strip()
    }


def check_repository_contract() -> None:
    _assert(
        _git("rev-parse", "HEAD") == EXPECTED_CONTROL_C_COMMIT,
        "unexpected Control D baseline",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control D surface: {sorted(_changed_paths())}",
    )
    _assert(
        _commit_subject(EXPECTED_CONTROL_C_COMMIT) == CONTROL_C_SUBJECT,
        "Control C subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_CONTROL_C_COMMIT) == CONTROL_C_SURFACE,
        "Control C exact surface drift",
    )
    _assert(
        _commit_parent(EXPECTED_CONTROL_C_COMMIT) == EXPECTED_CONTROL_B_COMMIT,
        "Control C parent drift",
    )
    _assert(
        _commit_subject(EXPECTED_CONTROL_B_COMMIT) == CONTROL_B_SUBJECT,
        "Control B subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_CONTROL_B_COMMIT) == CONTROL_B_SURFACE,
        "Control B exact surface drift",
    )
    _assert(
        _commit_parent(EXPECTED_CONTROL_B_COMMIT) == EXPECTED_CONTROL_A_COMMIT,
        "Control B parent drift",
    )
    _assert(
        _commit_subject(EXPECTED_CONTROL_A_COMMIT) == CONTROL_A_SUBJECT,
        "Control A subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_CONTROL_A_COMMIT) == CONTROL_A_SURFACE,
        "Control A exact surface drift",
    )
    _assert(
        _commit_parent(EXPECTED_CONTROL_A_COMMIT) == EXPECTED_CONTROL_A_PARENT,
        "Control A parent drift",
    )
    print("[OK] Control A/B/C history and exact Control D surface conform")


def check_package_contract() -> None:
    data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    setuptools = data["tool"]["setuptools"]
    _assert(project["name"] == "ai-character-framework", "distribution name drift")
    _assert(project["dynamic"] == ["version"], "dynamic version contract drift")
    _assert(project["requires-python"] == ">=3.10", "Python requirement drift")
    _assert(project["dependencies"] == ["python-dotenv==1.2.2"], "core dependency drift")
    _assert(
        set(project["optional-dependencies"])
        == {
            "llm-gemini",
            "llm-openai",
            "llm-xai",
            "voice-input",
            "voice-output",
            "motion",
            "full",
        },
        "optional dependency groups drift",
    )
    _assert(
        setuptools["dynamic"]["version"]["attr"]
        == "framework.version.FRAMEWORK_SOURCE_VERSION",
        "central version source drift",
    )
    _assert(
        set(setuptools["packages"]["find"]["include"])
        == {"framework*", "config*", "llm*", "registry*", "presets", "characters"},
        "package discovery drift",
    )
    print("[OK] package metadata and optional dependency boundary remain accepted")


def check_runtime_contract() -> None:
    import framework
    from config.loader import load_character_data, load_preset_file
    from framework.audio._provider_adapter import ElevenLabsVoiceOutputAdapter
    from framework.facade import create_text_chat_session
    from framework.public_api import PUBLIC_API_NAMES

    _assert(framework.__version__ == "6.0.0.dev0", "source version drift")
    _assert(len(PUBLIC_API_NAMES) == 95, "canonical root-public count drift")
    _assert(list(framework.__all__) == list(PUBLIC_API_NAMES), "framework.__all__ drift")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider SDK imported at root")

    signature = inspect.signature(create_text_chat_session)
    parameters = list(signature.parameters.values())
    _assert(
        [parameter.name for parameter in parameters]
        == ["preset", "character_name", "provider", "model", "project_root"],
        "text factory parameter order drift",
    )
    _assert(
        all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in parameters[:4]
        ),
        "accepted four-parameter positional prefix drift",
    )
    _assert(
        parameters[4].kind is inspect.Parameter.KEYWORD_ONLY,
        "project_root must remain keyword-only",
    )

    preset = load_preset_file("text_chat")
    character = load_character_data("default")
    _assert(preset.get("character_name") == "default", "bundled preset drift")
    _assert(character.system_prompt.strip(), "bundled character prompt missing")

    adapter = ElevenLabsVoiceOutputAdapter(project_root=None, artifact_dir=None)
    expected_artifact_root = (
        Path(tempfile.gettempdir())
        / "ai-character-framework"
        / "voice_output"
    )
    _assert(
        adapter._resolve_artifact_dir() == expected_artifact_root,
        "public voice artifact default drift",
    )
    _assert(
        adapter._resolve_artifact_dir() != Path.cwd() / "temp" / "voice_output",
        "CWD voice artifact fallback returned",
    )
    print("[OK] resource, factory, artifact, and root-public contracts remain accepted")


def check_example_sources() -> None:
    for relative in EXAMPLE_PATHS:
        path = PROJECT_ROOT / relative
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for forbidden in ("PROJECT_ROOT", "sys.path.insert", "sys.path.append", "PYTHONPATH"):
            _assert(forbidden not in source, f"example bootstrap returned: {relative}: {forbidden}")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                _assert(
                    not node.module.startswith(("config", "core", "llm", "registry", "tts", "stt", "live2d")),
                    f"public example imports internal module: {relative}: {node.module}",
                )
    print("[OK] public examples remain normal installed-package consumers")


def _load_control_c_checker():
    path = PROJECT_ROOT / "scripts/check_v600_installable_sdk.py"
    spec = importlib.util.spec_from_file_location("fw_rt6_control_c_checker", path)
    _assert(spec is not None and spec.loader is not None, "Control C checker import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_isolated_install_acceptance() -> None:
    module = _load_control_c_checker()
    module.check_example_sources()
    module.check_isolated_installations()
    module.check_docs()
    print("[OK] editable/wheel isolation acceptance remains reproducible offline")


def check_docs_sync() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    gap = (PROJECT_ROOT / "docs/v600_current_source_gap_inventory.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    _assert("FW-RT6-0c-D-INSTALLABLE-SDK-ACCEPTANCE:BEGIN" in readme, "README Control D marker missing")
    _assert("FW-RT6-0c-D-GAP-RESOLUTION-SYNC:BEGIN" in gap, "gap Control D marker missing")
    _assert("FW-RT6-0c-D-ACCEPTANCE-SYNC:BEGIN" in tasklist, "tasklist Control D marker missing")
    _assert(EXPECTED_CONTROL_C_COMMIT in readme, "README Control C baseline missing")
    _assert(EXPECTED_CONTROL_C_COMMIT in gap, "gap Control C baseline missing")
    _assert(EXPECTED_CONTROL_C_COMMIT in tasklist, "tasklist Control C baseline missing")
    for relative, text in (
        ("README.md", readme),
        ("docs/v600_current_source_gap_inventory.md", gap),
        ("docs/v600_tasklist.md", tasklist),
    ):
        _assert("__CONTROL_" not in text, f"unresolved commit placeholder remains: {relative}")

    section = tasklist.split("## FW-RT6-0c —", 1)[1].split("## FW-RT6-1a —", 1)[0]
    _assert(section.count("- [x]") == 9, "FW-RT6-0c completed task count drift")
    _assert("- [ ]" not in section, "FW-RT6-0c incomplete task remains")
    _assert("next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED" in section, "next authorization boundary missing")

    for required in (
        "G-14 installable SDK/package metadata: RESOLVED",
        "legacy main.py/runtime CWD-relative paths: UNRESOLVED / OUT OF FW-RT6-0c SCOPE",
        "G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c",
        "capability truthfulness across modules: UNRESOLVED / FW-RT6-1d",
        "unified realtime orchestration: UNRESOLVED",
    ):
        _assert(required in gap, f"gap truthfulness marker missing: {required}")
    _assert("v6.0.0 released: False" in readme, "release status overclaimed")
    print("[OK] README, gap inventory, and tasklist aggregate acceptance are synchronized")


def main() -> None:
    check_repository_contract()
    check_package_contract()
    check_runtime_contract()
    check_example_sources()
    check_isolated_install_acceptance()
    check_docs_sync()
    print("v600_installable_sdk_acceptance_status: implemented-awaiting-review")
    print("v600_control_a_accepted: True")
    print("v600_control_b_accepted: True")
    print("v600_control_c_accepted: True")
    print("v600_exact_change_surface_count: 4")
    print("v600_editable_install: True")
    print("v600_wheel_build: True")
    print("v600_wheel_install: True")
    print("v600_import_outside_checkout: True")
    print("v600_public_resource_cwd_dependency: False")
    print("v600_public_artifact_cwd_dependency: False")
    print("v600_example_sys_path_mutation: False")
    print("v600_root_public_name_count: 95")
    print("v600_framework_source_version: 6.0.0.dev0")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_microphone_used: False")
    print("v600_audio_playback: False")
    print("v600_vts_execution: False")
    print("v600_drc_repository_accessed: False")
    print("v600_next_checkpoint: FW-RT6-1a")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-0c Control D installable SDK acceptance checker passed")


if __name__ == "__main__":
    main()
