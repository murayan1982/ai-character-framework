"""v5.2.0 fixed release package verification smoke."""

from __future__ import annotations

import shutil
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


def _run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    return completed


def _assert_doc(root: Path) -> None:
    path = root / "docs" / "v520_fixed_release_package_verification.md"
    _require(path.exists(), "missing docs/v520_fixed_release_package_verification.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Fixed Release Package Verification",
        "scripts/verify_v520_release_package.py",
        "release/ai-character-framework_v5.2.0.zip",
        "release/ai-character-framework_v5.2.0.sha256.txt",
        "RELEASE_MANIFEST_v5.2.0.json",
        "SHA-256 sidecar",
        "zip timestamps are normalized",
        "release manifest appended last",
        "operator evidence",
        "does not create the final release package",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"fixed release package verification doc missing phrase: {phrase}")
    _ok("v5.2.0 fixed release package verification doc is documented")


def _assert_verifier_script(root: Path) -> None:
    path = root / "scripts" / "verify_v520_release_package.py"
    _require(path.exists(), "missing scripts/verify_v520_release_package.py")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        'VERSION = "5.2.0"',
        "ai-character-framework_v",
        "RELEASE_MANIFEST_v",
        "SHA256_FILENAME",
        "NORMALIZED_ZIP_DATETIME",
        "REQUIRED_ARCNAMES",
        "FORBIDDEN_ARCNAME_FRAGMENTS",
        "operator_evidence",
        "verify_release_package",
        "v5.2.0 fixed release package verification passed",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"fixed release package verifier missing phrase: {phrase}")
    _ok("v5.2.0 fixed release package verifier script is present")


def _assert_build_and_verify_temp_package(root: Path) -> None:
    temp_dir = root / ".release_build" / "v5.2.0_verification_smoke"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    package_path = temp_dir / "ai-character-framework_v5.2.0.zip"

    build = _run(
        root,
        [
            sys.executable,
            str(root / "scripts" / "build_v520_release_package.py"),
            "--allow-dirty",
            "--skip-checks",
            "--output",
            str(package_path),
        ],
    )
    _require(build.returncode == 0, "temporary v5.2.0 package build failed")
    _require(package_path.exists(), "temporary v5.2.0 package was not created")
    _require(package_path.with_name("ai-character-framework_v5.2.0.sha256.txt").exists(), "temporary SHA-256 sidecar was not created")

    verify = _run(
        root,
        [
            sys.executable,
            str(root / "scripts" / "verify_v520_release_package.py"),
            "--package",
            str(package_path),
        ],
    )
    _require(verify.returncode == 0, "temporary v5.2.0 package verification failed")
    _require("v5.2.0 fixed release package verification passed" in verify.stdout, "verification should report pass")

    _ok("v5.2.0 temporary fixed release package build/verify workflow passed")


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

    _require("v520_fixed_release_package_verification.md" in readme_text, "README should link fixed release package verification")
    _require("Commit 26 - Fixed release package verification for v5.2.0" in checklist_text, "checklist should track commit 26")
    _require("v5.2.0 fixed release package verification checkpoint" in notes_text, "readiness notes should track verification checkpoint")
    _ok("README/checklist/readiness notes track fixed release package verification")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_verifier_script(root)
    _assert_build_and_verify_temp_package(root)
    _assert_readme_and_checklist(root)
    _ok("v5.2.0 fixed release package verification smoke passed")


if __name__ == "__main__":
    main()
