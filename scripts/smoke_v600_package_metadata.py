"""FW-RT6-0c Control A package metadata and wheel-skeleton smoke.

Offline-safe: builds a local wheel from a temporary source copy with
``--no-deps --no-build-isolation``. It does not install provider extras or
execute provider, network, microphone, playback, or VTS operations.
"""

from __future__ import annotations

import email
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 smoke compatibility
    try:
        from setuptools._vendor import tomli as tomllib
    except ImportError:
        from pip._vendor import tomli as tomllib
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "f082a027dbc49de04bd046642ae0f06dfd2e48ca"
EXPECTED_SURFACE = {
    "README.md",
    "characters/__init__.py",
    "docs/v600_installable_sdk_contract.md",
    "presets/__init__.py",
    "pyproject.toml",
    "scripts/smoke_v600_package_metadata.py",
}
EXPECTED_PACKAGES = {
    "framework*",
    "config*",
    "llm*",
    "registry*",
    "presets",
    "characters",
}
EXPECTED_EXTRAS = {
    "llm-gemini",
    "llm-openai",
    "llm-xai",
    "voice-input",
    "voice-output",
    "motion",
    "full",
}
FORBIDDEN_IMPORTS = (
    "openai",
    "elevenlabs",
    "pyvts",
    "websockets",
    "google.genai",
    "xai_sdk",
    "speech_recognition",
    "pyaudio",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control A baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control A surface: {sorted(_changed_paths())}")
    print("[OK] Control A baseline and exact six-file surface match")


def check_pyproject_contract() -> None:
    data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    _assert(data["build-system"]["build-backend"] == "setuptools.build_meta", "unexpected build backend")
    project = data["project"]
    _assert(project["name"] == "ai-character-framework", "distribution name drift")
    _assert(project["dynamic"] == ["version"], "version must remain central/dynamic")
    _assert(project["requires-python"] == ">=3.10", "Python requirement drift")
    _assert(project["dependencies"] == ["python-dotenv==1.2.2"], "core dependency drift")
    _assert(set(project["optional-dependencies"]) == EXPECTED_EXTRAS, "optional dependency groups drift")
    setuptools = data["tool"]["setuptools"]
    _assert(setuptools["dynamic"]["version"]["attr"] == "framework.version.FRAMEWORK_SOURCE_VERSION", "version source drift")
    _assert(set(setuptools["packages"]["find"]["include"]) == EXPECTED_PACKAGES, "package discovery drift")
    _assert(setuptools["package-data"]["presets"] == ["*.json"], "preset package data drift")
    _assert(set(setuptools["package-data"]["characters"]) == {"*/*.json", "*/*.txt"}, "character package data drift")
    print("[OK] pyproject metadata and optional dependency boundaries conform")


def _copy_build_source(destination: Path) -> None:
    for rel in ("README.md", "pyproject.toml"):
        shutil.copy2(PROJECT_ROOT / rel, destination / rel)
    for rel in ("framework", "config", "llm", "registry", "presets", "characters"):
        shutil.copytree(
            PROJECT_ROOT / rel,
            destination / rel,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def check_offline_wheel_skeleton() -> None:
    packaging_python_value = os.environ.get("FW_RT6_PACKAGING_PYTHON", "").strip()
    _assert(
        packaging_python_value,
        "FW_RT6_PACKAGING_PYTHON must identify an offline packaging-capable Python",
    )
    packaging_python = Path(packaging_python_value)
    _assert(
        packaging_python.is_file(),
        f"packaging Python does not exist: {packaging_python}",
    )
    tooling = subprocess.run(
        [
            str(packaging_python),
            "-c",
            (
                "import pip, setuptools, wheel; "
                "print('packaging tooling: PASS')"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(
        tooling.returncode == 0,
        (
            "selected packaging Python lacks pip/setuptools/wheel:\n"
            f"{tooling.stdout}\n{tooling.stderr}"
        ),
    )

    with tempfile.TemporaryDirectory(prefix="fw_rt6_0c_a_") as temp_name:
        temp = Path(temp_name)
        source = temp / "source"
        wheel_dir = temp / "wheel"
        source.mkdir()
        wheel_dir.mkdir()
        _copy_build_source(source)
        result = subprocess.run(
            [
                str(packaging_python),
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--disable-pip-version-check",
                "--wheel-dir",
                str(wheel_dir),
                str(source),
            ],
            cwd=temp,
            check=False,
            capture_output=True,
            text=True,
        )
        _assert(result.returncode == 0, f"offline wheel build failed:\n{result.stdout}\n{result.stderr}")
        wheels = list(wheel_dir.glob("*.whl"))
        _assert(len(wheels) == 1, f"expected one wheel, found {wheels}")
        with zipfile.ZipFile(wheels[0]) as archive:
            names = set(archive.namelist())
            required = {
                "framework/__init__.py",
                "framework/version.py",
                "config/loader.py",
                "llm/base.py",
                "registry/llm.py",
                "presets/__init__.py",
                "presets/text_chat.json",
                "characters/__init__.py",
                "characters/default/profile.json",
                "characters/default/system.txt",
                "characters/default/vts_hotkeys.json",
            }
            missing = sorted(required - names)
            _assert(not missing, f"wheel missing required SDK/resource files: {missing}")
            metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
            _assert(len(metadata_names) == 1, "wheel METADATA missing or duplicated")
            metadata = email.message_from_bytes(archive.read(metadata_names[0]))
            _assert(metadata["Name"] == "ai-character-framework", "wheel name drift")
            _assert(metadata["Version"] == "6.0.0.dev0", "wheel source version drift")
            _assert(metadata["Requires-Python"] == ">=3.10", "wheel Python requirement drift")
            _assert("python-dotenv==1.2.2" in metadata.get_all("Requires-Dist", []), "wheel core dependency missing")
    print("[OK] offline wheel skeleton includes SDK modules and bundled resources")


def check_public_import_safety() -> None:
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    _assert(framework.__version__ == "6.0.0.dev0", "source version drift")
    _assert(len(framework.__all__) == 95, "root-public count changed")
    _assert("__version__" not in framework.__all__, "metadata leaked into wildcard surface")
    hits = sorted(name for name in loaded if any(name == item or name.startswith(item + ".") for item in FORBIDDEN_IMPORTS))
    _assert(not hits, f"package metadata import loaded provider modules: {hits}")
    print("[OK] root import remains 95-name and provider safe")


def check_docs() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_installable_sdk_contract.md").read_text(encoding="utf-8")
    _assert("FW-RT6-0c-A-PACKAGE-METADATA:BEGIN" in readme, "README marker missing")
    for marker in (
        "distribution name: ai-character-framework",
        "public import package: framework",
        "resource lookup behavior changed: False",
        "preset/character resource resolver: FW-RT6-0c Control B",
    ):
        _assert(marker in contract, f"installable SDK contract missing: {marker}")
    print("[OK] package metadata docs preserve Control A scope")


def main() -> None:
    check_repository_contract()
    check_pyproject_contract()
    check_offline_wheel_skeleton()
    check_public_import_safety()
    check_docs()
    print("v600_package_metadata_status: implemented-awaiting-review")
    print("v600_distribution_name: ai-character-framework")
    print("v600_framework_source_version: 6.0.0.dev0")
    print("v600_root_public_name_count: 95")
    print("v600_offline_wheel_build: True")
    print("v600_packaging_python_selected: True")
    print("v600_bundled_presets_present: True")
    print("v600_bundled_characters_present: True")
    print("v600_resource_resolution_changed: False")
    print("v600_factory_signatures_changed: False")
    print("v600_artifact_path_changed: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-0c Control B")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-0c Control A package metadata smoke passed")


if __name__ == "__main__":
    main()
