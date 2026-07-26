"""v5.2.0 fixed release package builder smoke."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class ContractFailure(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _assert_doc(root: Path) -> None:
    path = root / "docs" / "v520_fixed_release_package_builder.md"
    _require(path.exists(), "missing docs/v520_fixed_release_package_builder.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Fixed Release Package Builder",
        "scripts/build_v520_release_package.py",
        "release/ai-character-framework_v5.2.0.zip",
        "release/ai-character-framework_v5.2.0.sha256.txt",
        "requires a clean git working tree",
        "smoke_v520_release_readiness_gate.py",
        "deterministic zip",
        "RELEASE_MANIFEST_v5.2.0.json",
        "SHA-256 sidecar",
        "does not create the final fixed release package",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"fixed release package builder doc missing phrase: {phrase}")
    _ok("v5.2.0 fixed release package builder doc is documented")


def _assert_builder_script(root: Path) -> None:
    path = root / "scripts" / "build_v520_release_package.py"
    _require(path.exists(), "missing scripts/build_v520_release_package.py")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        'VERSION = "5.2.0"',
        "ai-character-framework_v",
        "smoke_v520_release_readiness_gate.py",
        "NORMALIZED_ZIP_DATETIME",
        "RELEASE_MANIFEST_v",
        "sha256",
        "--allow-dirty",
        "--skip-checks",
        "--dry-run",
        "operator_evidence",
        ".env",
        "deterministic_zip",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"fixed release package builder script missing phrase: {phrase}")
    _ok("v5.2.0 fixed release package builder script is present")


def _assert_dry_run(root: Path) -> None:
    output = root / "release" / "_dry_run_should_not_exist_v520.zip"
    if output.exists():
        output.unlink()

    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "build_v520_release_package.py"),
            "--dry-run",
            "--allow-dirty",
            "--skip-checks",
            "--output",
            str(output),
        ],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())

    _require(completed.returncode == 0, "build_v520_release_package.py dry run failed")
    _require("[DRY-RUN] v5.2.0 release package builder ready" in completed.stdout, "dry run should report ready")
    _require("ai-character-framework_v5.2.0" in completed.stdout or "_dry_run_should_not_exist_v520.zip" in completed.stdout, "dry run should report package path")
    _require("RELEASE_MANIFEST_v5.2.0.json" in completed.stdout, "dry run should report manifest")
    _require(not output.exists(), "dry run must not create output package")
    _ok("v5.2.0 fixed release package builder dry run is safe")


def _assert_readme_and_checklist(root: Path) -> None:
    readme = root / "README.md"
    checklist = root / "docs" / "v520_drc_runtime_contract_checklist.md"
    notes = root / "docs" / "v510_host_app_sdk_readiness_notes.md"

    _require(readme.exists(), "missing README.md")
    _require(checklist.exists(), "missing docs/v520_drc_runtime_contract_checklist.md")
    _require(notes.exists(), "missing docs/v510_host_app_sdk_readiness_notes.md")

    readme_text = readme.read_text(encoding="utf-8", errors="replace")
    checklist_text = checklist.read_text(encoding="utf-8", errors="replace")
    notes_text = notes.read_text(encoding="utf-8", errors="replace")

    _require("v520_fixed_release_package_builder.md" in readme_text, "README should link fixed release package builder")
    _require("Commit 25 - Fixed release package builder for v5.2.0" in checklist_text, "checklist should track commit 25")
    _require("v5.2.0 fixed release package builder checkpoint" in notes_text, "readiness notes should track builder checkpoint")
    _ok("README/checklist/readiness notes track fixed release package builder")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_builder_script(root)
    _assert_dry_run(root)
    _assert_readme_and_checklist(root)
    _ok("v5.2.0 fixed release package builder smoke passed")


if __name__ == "__main__":
    main()
