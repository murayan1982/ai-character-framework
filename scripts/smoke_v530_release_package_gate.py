"""v5.3.0 release package gate smoke."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


DEPENDENCIES = (
    "scripts/smoke_v530_release_readiness_gate.py",
    "scripts/smoke_v530_drc_public_handoff_verification.py",
    "scripts/smoke_v530_guarded_real_provider_adapter.py",
    "scripts/smoke_v530_voice_input_session_adapter_wiring.py",
    "scripts/smoke_v530_lazy_provider_adapter_fake.py",
    "scripts/smoke_v530_host_audio_source_contract.py",
    "scripts/smoke_v530_real_stt_provider_boundary_inventory.py",
    "scripts/smoke_v520_voice_input_public_contract_conformance_gate.py",
    "scripts/smoke_v520_release_readiness_gate.py",
)

REQUIRED_ZIP_ENTRIES = {
    "README.md",
    "framework/__init__.py",
    "framework/voice_input_audio.py",
    "framework/voice_input_provider_adapter.py",
    "framework/voice_input_session.py",
    "docs/v530_release_readiness_gate.md",
    "docs/v530_drc_public_handoff_verification.md",
    "docs/v530_guarded_real_provider_adapter.md",
    "examples/voice_input_drc_public_handoff.py",
    "scripts/smoke_v530_release_readiness_gate.py",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _run_dependency(root: Path, script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        raise AssertionError(f"release package dependency failed: {script}")
    print(f"[OK] release package dependency passed: {script}")


def _load_builder(root: Path):
    builder_path = root / "scripts" / "build_v530_release_package.py"
    spec = importlib.util.spec_from_file_location("build_v530_release_package", builder_path)
    _require(spec is not None and spec.loader is not None, "could not load release package builder spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    root = _repo_root()

    doc = _read(root / "docs" / "v530_release_package_gate.md")
    checklist = _read(root / "docs" / "v530_real_stt_small_commit_checklist.md")
    readme = _read(root / "README.md")

    _require(
        "v5.3.0 release package gate: ACCEPTED" in doc,
        "release package doc should mark accepted",
    )
    _require(
        "v5.3.0 tag/push: READY" in doc,
        "release package doc should mark tag/push ready",
    )
    _require("v5.3.0 release package gate" in checklist, "checklist missing release package gate")
    _require("v5.3.0 release package gate" in readme, "README missing release package gate")
    _ok("v5.3.0 release package gate doc is documented")

    builder = _load_builder(root)
    package_files = builder.package_files(root)
    for required in builder.REQUIRED_PACKAGE_FILES:
        _require(required in package_files, f"builder package set missing required file: {required}")
    _require(".vscode/settings.json" not in package_files, "package must not include local VS Code settings")
    _require(not any(path.startswith("release/") for path in package_files), "package must not include generated release artifacts")
    _require(not any("operator_evidence" in path for path in package_files), "package must not include operator evidence")
    _require(not any(path.endswith(".env") or "/.env" in path for path in package_files), "package must not include env files")
    _ok("v5.3.0 release package file set is safe")

    with tempfile.TemporaryDirectory(prefix="acf_v530_package_gate_") as temp:
        package_path = Path(temp) / builder.PACKAGE_BASENAME
        digest, count = builder.build_package(package_path, root=root)
        _require(package_path.exists(), "dry-run package was not created in temp dir")
        _require(len(digest) == 64, "package sha256 should be 64 hex characters")
        _require(count == len(package_files), "package file count should match builder file set")
        with zipfile.ZipFile(package_path, "r") as archive:
            names = set(archive.namelist())
        for required in REQUIRED_ZIP_ENTRIES:
            _require(required in names, f"dry-run package missing required entry: {required}")
        _require(".vscode/settings.json" not in names, "dry-run package must not include local VS Code settings")
        _require(not any(name.startswith("release/") for name in names), "dry-run package must not include release artifacts")
        _require(not any("operator_evidence" in name for name in names), "dry-run package must not include operator evidence")
        _require(not any(name.endswith(".env") or "/.env" in name for name in names), "dry-run package must not include env files")
    _ok("v5.3.0 release package dry-run build passed")

    for dep in DEPENDENCIES:
        _run_dependency(root, dep)

    print("v530_release_package_gate_status: accepted")
    print("v530_release_package_dry_run_succeeded: True")
    print("v530_release_package_created_in_release_dir: False")
    print("v530_release_package_sha256_present: True")
    print("v530_release_package_excludes_vscode_settings: True")
    print("v530_release_package_excludes_private_evidence: True")
    print("v530_release_package_excludes_env_files: True")
    print("v530_provider_execution_executed: False")
    print("v530_microphone_accessed: False")
    print("v530_audio_handled: False")
    print("v530_tag_authorization: ready-for-final-release-package-build")
    _ok("v5.3.0 release package gate passed")


if __name__ == "__main__":
    main()
