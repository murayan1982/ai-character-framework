"""FW-RT6-0c Control C isolated editable/wheel installation gate.

Offline-safe: all pip commands use PIP_NO_INDEX and local source/wheel inputs.
No provider, network, microphone, playback, VTS, or host-app execution occurs.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "e51a07e62045b185799cd32d64127170c30ebe56"
EXPECTED_SURFACE = {
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
EXAMPLE_PATHS = (
    "examples/public_text_chat.py",
    "examples/minimal_app_text_chat.py",
    "examples/app_error_handling.py",
    "examples/app_streaming_text_chat.py",
    "examples/app_reset_text_chat.py",
    "examples/app_voice_output_integration.py",
)
PACKAGE_COPY_PATHS = (
    "README.md",
    "pyproject.toml",
    "framework",
    "config",
    "llm",
    "registry",
    "presets",
    "characters",
)
TOOL_DISTRIBUTIONS = ("setuptools", "wheel", "packaging")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    label: str,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"{label} failed with exit code {result.returncode}:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def _git(*args: str) -> str:
    return _run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        label=f"git {' '.join(args)}",
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


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PIP_NO_INDEX"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _venv_python(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _packaging_python() -> Path:
    raw = os.environ.get("FW_RT6_PACKAGING_PYTHON", "").strip()
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw))
    candidates.extend(
        (
            PROJECT_ROOT / "venv" / "Scripts" / "python.exe",
            PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
            Path(sys.executable),
        )
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        probe = subprocess.run(
            [
                str(candidate),
                "-c",
                "import pip, setuptools, wheel, packaging",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return candidate.absolute()
    raise AssertionError(
        "No local Python with pip, setuptools, wheel, and packaging is available."
    )


def _copy_build_source(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for relative in PACKAGE_COPY_PATHS:
        source = PROJECT_ROOT / relative
        target = destination / relative
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "*.pyo", "*.egg-info"
                ),
            )
        else:
            shutil.copy2(source, target)


def _pack_tool_wheels(packaging_python: Path, wheel_dir: Path) -> list[Path]:
    wheel_dir.mkdir(parents=True, exist_ok=True)
    helper = textwrap.dedent(
        r"""
        import base64
        import csv
        import hashlib
        import io
        from importlib.metadata import distribution
        from pathlib import Path
        import sys
        import zipfile

        output = Path(sys.argv[1])
        names = sys.argv[2:]
        for name in names:
            dist = distribution(name)
            site_root = Path(dist._path).resolve().parent
            normalized = dist.metadata["Name"].replace("-", "_")
            wheel_path = output / f"{normalized}-{dist.version}-py3-none-any.whl"
            entries = []
            for item in dist.files or ():
                source = Path(dist.locate_file(item)).resolve()
                try:
                    relative = source.relative_to(site_root)
                except ValueError:
                    continue
                if not source.is_file():
                    continue
                if "__pycache__" in relative.parts or source.suffix in {".pyc", ".pyo"}:
                    continue
                if relative.name == "RECORD" and relative.parent.name.endswith(".dist-info"):
                    continue
                entries.append((source, relative.as_posix()))

            if not entries:
                dist_info = Path(dist._path).resolve()
                package_root = site_root / normalized
                roots = [dist_info, package_root]
                if normalized == "setuptools":
                    roots.extend(
                        [site_root / "_distutils_hack", site_root / "distutils-precedence.pth"]
                    )
                for root in roots:
                    if root.is_file():
                        candidates = [root]
                    elif root.is_dir():
                        candidates = list(root.rglob("*"))
                    else:
                        candidates = []
                    for source in candidates:
                        if not source.is_file():
                            continue
                        relative = source.relative_to(site_root)
                        if "__pycache__" in relative.parts or source.suffix in {".pyc", ".pyo"}:
                            continue
                        if relative.name == "RECORD" and relative.parent.name.endswith(".dist-info"):
                            continue
                        entries.append((source, relative.as_posix()))

            if not entries:
                raise RuntimeError(f"No installable files found for {name}")

            dist_info_name = Path(dist._path).name
            record_name = f"{dist_info_name}/RECORD"
            record_rows = []
            with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for source, relative in entries:
                    data = source.read_bytes()
                    archive.writestr(relative, data)
                    digest = base64.urlsafe_b64encode(
                        hashlib.sha256(data).digest()
                    ).rstrip(b"=").decode("ascii")
                    record_rows.append((relative, f"sha256={digest}", str(len(data))))
                buffer = io.StringIO(newline="")
                writer = csv.writer(buffer, lineterminator="\n")
                for row in record_rows:
                    writer.writerow(row)
                writer.writerow((record_name, "", ""))
                archive.writestr(record_name, buffer.getvalue().encode("utf-8"))
            print(wheel_path)
        """
    )
    result = _run(
        [
            str(packaging_python),
            "-c",
            helper,
            str(wheel_dir),
            *TOOL_DISTRIBUTIONS,
        ],
        env=_clean_env(),
        label="pack local build-tool wheels",
    )
    wheels = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    _assert(len(wheels) == len(TOOL_DISTRIBUTIONS), "tool wheel count mismatch")
    _assert(all(path.is_file() for path in wheels), "tool wheel missing")
    return wheels


def _create_venv(packaging_python: Path, venv_root: Path) -> Path:
    _run(
        [str(packaging_python), "-m", "venv", str(venv_root)],
        env=_clean_env(),
        label=f"create venv {venv_root.name}",
    )
    python = _venv_python(venv_root)
    _assert(python.is_file(), f"venv Python missing: {python}")
    return python


def _install_tool_wheels(venv_python: Path, wheels: list[Path]) -> None:
    _run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--disable-pip-version-check",
            *[str(path) for path in wheels],
        ],
        env=_clean_env(),
        label="install local build-tool wheels",
    )
    _run(
        [
            str(venv_python),
            "-c",
            "import pip, setuptools, wheel, packaging",
        ],
        env=_clean_env(),
        label="verify isolated build tooling",
    )


def _write_override_resources(root: Path) -> None:
    preset_dir = root / "presets"
    character_dir = root / "characters" / "override_character"
    preset_dir.mkdir(parents=True)
    character_dir.mkdir(parents=True)
    (preset_dir / "override_preset.json").write_text(
        json.dumps({"marker": "explicit-project-root"}), encoding="utf-8"
    )
    (character_dir / "profile.json").write_text(
        json.dumps({"marker": "explicit-project-root"}), encoding="utf-8"
    )
    (character_dir / "system.txt").write_text(
        "explicit-project-root", encoding="utf-8"
    )
    (character_dir / "vts_hotkeys.json").write_text("{}", encoding="utf-8")


def _write_cwd_decoys(cwd: Path) -> None:
    preset_dir = cwd / "presets"
    character_dir = cwd / "characters" / "default"
    preset_dir.mkdir(parents=True)
    character_dir.mkdir(parents=True)
    (preset_dir / "text_chat.json").write_text(
        json.dumps({"marker": "cwd-decoy"}), encoding="utf-8"
    )
    (character_dir / "profile.json").write_text(
        json.dumps({"marker": "cwd-decoy"}), encoding="utf-8"
    )
    (character_dir / "system.txt").write_text("cwd-decoy", encoding="utf-8")
    (character_dir / "vts_hotkeys.json").write_text("{}", encoding="utf-8")


def _child_script(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            r"""
            from __future__ import annotations

            import importlib.metadata
            import json
            import os
            import runpy
            import sys
            import tempfile
            from pathlib import Path

            mode = os.environ["FW_INSTALL_MODE"]
            repo_root = Path(os.environ["FW_REPO_ROOT"]).resolve()
            source_root = Path(os.environ["FW_SOURCE_ROOT"]).resolve()
            override_root = Path(os.environ["FW_OVERRIDE_ROOT"]).resolve()
            examples = json.loads(os.environ["FW_EXAMPLE_PATHS"])

            import framework
            from framework import create_voice_output_session
            from framework.audio._provider_adapter import ElevenLabsVoiceOutputAdapter
            from framework.resources import (
                read_json_resource,
                read_text_resource,
                resolve_character_directory,
                resolve_preset_resource,
            )

            assert framework.__version__ == "6.0.0.dev0"
            assert len(framework.__all__) == 95
            assert importlib.metadata.version("ai-character-framework") == "6.0.0.dev0"

            preset = read_json_resource(
                resolve_preset_resource("text_chat"), label="preset"
            )
            assert preset.get("marker") != "cwd-decoy"
            assert preset.get("input_voice_enabled") is False

            character = resolve_character_directory("default")
            profile = read_json_resource(
                character.joinpath("profile.json"), label="profile"
            )
            system_prompt = read_text_resource(
                character.joinpath("system.txt"), label="system"
            )
            assert profile.get("marker") != "cwd-decoy"
            assert system_prompt != "cwd-decoy"

            override_preset = read_json_resource(
                resolve_preset_resource(
                    "override_preset", project_root=override_root
                ),
                label="override preset",
            )
            override_character = resolve_character_directory(
                "override_character", project_root=override_root
            )
            override_profile = read_json_resource(
                override_character.joinpath("profile.json"),
                label="override profile",
            )
            assert override_preset["marker"] == "explicit-project-root"
            assert override_profile["marker"] == "explicit-project-root"

            adapter = ElevenLabsVoiceOutputAdapter(
                project_root=None, artifact_dir=None
            )
            expected_artifact_root = (
                Path(tempfile.gettempdir())
                / "ai-character-framework"
                / "voice_output"
            )
            assert adapter._resolve_artifact_dir() == expected_artifact_root
            assert adapter._resolve_artifact_dir() != (
                Path.cwd() / "temp" / "voice_output"
            )

            session = create_voice_output_session(real_tts_enabled=False)
            assert session.info().provider_configured is False
            session.close()

            forbidden = {
                "openai",
                "elevenlabs",
                "pyvts",
                "websockets",
                "google.genai",
                "xai_sdk",
                "speech_recognition",
                "pyaudio",
            }
            assert not (forbidden & set(sys.modules))
            assert "PYTHONPATH" not in os.environ
            assert repo_root not in [
                Path(item).resolve() for item in sys.path if item
            ]

            framework_file = Path(framework.__file__).resolve()
            if mode == "editable":
                assert source_root in framework_file.parents
            elif mode == "wheel":
                assert source_root not in framework_file.parents
                for example in examples:
                    runpy.run_path(example, run_name="fw_installed_example")
            else:
                raise AssertionError(mode)

            print(
                json.dumps(
                    {
                        "mode": mode,
                        "framework_file": str(framework_file),
                        "root_public_count": len(framework.__all__),
                        "repo_root_in_sys_path": False,
                        "preset_lookup": True,
                        "character_lookup": True,
                        "examples_imported": mode == "wheel",
                    }
                )
            )
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _run_child(
    python: Path,
    *,
    mode: str,
    cwd: Path,
    source_root: Path,
    override_root: Path,
    child_script: Path,
) -> dict[str, object]:
    env = _clean_env()
    env.update(
        {
            "FW_INSTALL_MODE": mode,
            "FW_REPO_ROOT": str(PROJECT_ROOT),
            "FW_SOURCE_ROOT": str(source_root),
            "FW_OVERRIDE_ROOT": str(override_root),
            "FW_EXAMPLE_PATHS": json.dumps(
                [str((PROJECT_ROOT / path).resolve()) for path in EXAMPLE_PATHS]
            ),
        }
    )
    result = _run(
        [str(python), str(child_script)],
        cwd=cwd,
        env=env,
        label=f"{mode} installed SDK child check",
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def check_repository_contract() -> None:
    _assert(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected Control C baseline",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control C surface: {sorted(_changed_paths())}",
    )
    print("[OK] Control C baseline and exact nine-file surface match")


def check_example_sources() -> None:
    for relative in EXAMPLE_PATHS:
        path = PROJECT_ROOT / relative
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        _assert(
            "PROJECT_ROOT" not in source,
            f"PROJECT_ROOT bootstrap remains: {relative}",
        )
        _assert(
            "sys.path.insert" not in source,
            f"sys.path.insert remains: {relative}",
        )
        _assert(
            "sys.path.append" not in source,
            f"sys.path.append remains: {relative}",
        )
        _assert(
            "PYTHONPATH" not in source,
            f"PYTHONPATH mutation remains: {relative}",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                _assert(
                    not node.module.startswith(
                        (
                            "config",
                            "core",
                            "llm",
                            "registry",
                            "tts",
                            "stt",
                            "live2d",
                        )
                    ),
                    f"internal import remains in {relative}: {node.module}",
                )
    print("[OK] public examples no longer mutate sys.path or import FW internals")


def check_isolated_installations() -> None:
    packaging_python = _packaging_python()
    with tempfile.TemporaryDirectory(prefix="fw_rt6_0c_c_") as temp_name:
        temp = Path(temp_name)
        tool_wheels = _pack_tool_wheels(
            packaging_python, temp / "tool-wheels"
        )
        source_editable = temp / "source-editable"
        source_wheel = temp / "source-wheel"
        _copy_build_source(source_editable)
        _copy_build_source(source_wheel)

        editable_venv = temp / "venv-editable"
        wheel_venv = temp / "venv-wheel"
        editable_python = _create_venv(packaging_python, editable_venv)
        wheel_python = _create_venv(packaging_python, wheel_venv)
        _install_tool_wheels(editable_python, tool_wheels)
        _install_tool_wheels(wheel_python, tool_wheels)

        _run(
            [
                str(editable_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                "--disable-pip-version-check",
                "-e",
                str(source_editable),
            ],
            env=_clean_env(),
            label="editable install",
        )

        wheel_dir = temp / "built-wheel"
        wheel_dir.mkdir()
        _run(
            [
                str(wheel_python),
                "-m",
                "pip",
                "wheel",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                "--disable-pip-version-check",
                "--wheel-dir",
                str(wheel_dir),
                str(source_wheel),
            ],
            env=_clean_env(),
            label="wheel build",
        )
        wheels = list(wheel_dir.glob("ai_character_framework-*.whl"))
        _assert(len(wheels) == 1, f"expected one SDK wheel, found {wheels}")
        _run(
            [
                str(wheel_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--disable-pip-version-check",
                str(wheels[0]),
            ],
            env=_clean_env(),
            label="wheel install",
        )

        editable_cwd = temp / "cwd-editable"
        wheel_cwd = temp / "cwd-wheel"
        editable_cwd.mkdir()
        wheel_cwd.mkdir()
        _write_cwd_decoys(editable_cwd)
        _write_cwd_decoys(wheel_cwd)
        override_root = temp / "override-root"
        _write_override_resources(override_root)
        child_script = temp / "check_installed_sdk.py"
        _child_script(child_script)

        editable_result = _run_child(
            editable_python,
            mode="editable",
            cwd=editable_cwd,
            source_root=source_editable,
            override_root=override_root,
            child_script=child_script,
        )
        wheel_result = _run_child(
            wheel_python,
            mode="wheel",
            cwd=wheel_cwd,
            source_root=source_wheel,
            override_root=override_root,
            child_script=child_script,
        )
        _assert(
            editable_result["root_public_count"] == 95,
            "editable root count drift",
        )
        _assert(
            wheel_result["root_public_count"] == 95,
            "wheel root count drift",
        )
        _assert(
            wheel_result["examples_imported"] is True,
            "wheel examples were not imported",
        )

    print(
        "[OK] isolated editable and wheel installs work outside checkout "
        "without network"
    )


def check_docs() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_installable_sdk_contract.md"
    ).read_text(encoding="utf-8")
    _assert(
        "FW-RT6-0c-C-INSTALLABLE-SDK-ISOLATION:BEGIN" in readme,
        "README Control C marker missing",
    )
    _assert(
        "FW-RT6-0c Control C — isolated editable and wheel installation"
        in contract,
        "Control C contract missing",
    )
    _assert(
        EXPECTED_BASELINE_HEAD in readme and EXPECTED_BASELINE_HEAD in contract,
        "Control C baseline missing from docs",
    )
    _assert(
        "next control authorized: False" in readme,
        "Control D authorization overclaimed",
    )
    print("[OK] installable SDK docs record Control C without overclaiming Control D")


def main() -> None:
    check_repository_contract()
    check_example_sources()
    check_isolated_installations()
    check_docs()
    print("v600_installable_sdk_status: implemented-awaiting-review")
    print("v600_editable_install: True")
    print("v600_wheel_build: True")
    print("v600_wheel_install: True")
    print("v600_import_outside_checkout: True")
    print("v600_wheel_repo_root_in_sys_path: False")
    print("v600_preset_lookup_outside_cwd: True")
    print("v600_character_lookup_outside_cwd: True")
    print("v600_example_sys_path_mutation: False")
    print("v600_root_public_name_count: 95")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-0c Control D")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-0c Control C installable SDK isolation gate passed")


if __name__ == "__main__":
    main()
