"""v5.2.0 final release tag readiness gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

VERSION = "5.2.0"
TAG = f"v{VERSION}"
PACKAGE = Path("release") / f"ai-character-framework_v{VERSION}.zip"


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
    path = root / "docs" / "v520_final_release_tag_readiness.md"
    _require(path.exists(), "missing docs/v520_final_release_tag_readiness.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Final Release Tag Readiness",
        "scripts/smoke_v520_final_release_tag_readiness.py",
        "smoke_v520_release_readiness_gate.py",
        "smoke_v520_fixed_release_package_builder.py",
        "smoke_v520_fixed_release_package_verification.py",
        "build_v520_release_package.py",
        "verify_v520_release_package.py",
        "v5.2.0",
        "--require-package",
        "git tag v5.2.0",
        "does not create the release package",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"final release tag readiness doc missing phrase: {phrase}")
    _ok("v5.2.0 final release tag readiness doc is documented")


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

    _require("v520_final_release_tag_readiness.md" in readme_text, "README should link final release tag readiness")
    _require("Commit 27 - Final release tag readiness for v5.2.0" in checklist_text, "checklist should track commit 27")
    _require("v5.2.0 final release tag readiness checkpoint" in notes_text, "readiness notes should track final tag readiness")
    _ok("README/checklist/readiness notes track final release tag readiness")


def _assert_git_state(root: Path, *, allow_dirty: bool, allow_existing_tag: bool) -> None:
    head = _run(root, ["git", "rev-parse", "HEAD"])
    _require(head.returncode == 0, "git HEAD should resolve")
    _require(len(head.stdout.strip()) >= 7, "git HEAD should produce a commit hash")
    _ok(f"git HEAD resolves: {head.stdout.strip()}")

    status = _run(root, ["git", "status", "--porcelain"])
    _require(status.returncode == 0, "git status should run")
    if not allow_dirty:
        _require(not status.stdout.strip(), "working tree must be clean for final tag readiness")
        _ok("working tree is clean")
    else:
        _ok("working tree dirty check skipped for local checkpoint mode")

    tag = _run(root, ["git", "rev-parse", "--verify", TAG])
    if tag.returncode == 0:
        _require(allow_existing_tag, f"{TAG} already exists")
        _ok(f"{TAG} already exists and was allowed")
    else:
        _ok(f"{TAG} does not already exist locally")


def _run_required_script(root: Path, relative: str) -> None:
    path = root / relative
    _require(path.exists(), f"missing required script: {relative}")
    completed = _run(root, [sys.executable, str(path)])
    _require(completed.returncode == 0, f"required script failed: {relative}")
    _ok(f"required script passed: {relative}")


def _assert_release_gates(root: Path) -> None:
    required = [
        "scripts/smoke_v520_release_readiness_gate.py",
        "scripts/smoke_v520_fixed_release_package_builder.py",
        "scripts/smoke_v520_fixed_release_package_verification.py",
    ]
    for relative in required:
        _run_required_script(root, relative)
    _ok("v5.2.0 final release prerequisite gates passed")


def _assert_package_tooling(root: Path) -> None:
    required = [
        "scripts/build_v520_release_package.py",
        "scripts/verify_v520_release_package.py",
    ]
    for relative in required:
        _require((root / relative).exists(), f"missing package tooling: {relative}")
    _ok("v5.2.0 package builder and verifier are present")


def _assert_final_package(root: Path, *, require_package: bool) -> None:
    package_path = root / PACKAGE
    if not require_package:
        _ok("final package verification not required in local checkpoint mode")
        return

    _require(package_path.exists(), f"missing final package: {package_path}")
    completed = _run(
        root,
        [
            sys.executable,
            str(root / "scripts" / "verify_v520_release_package.py"),
            "--package",
            str(package_path),
        ],
    )
    _require(completed.returncode == 0, "final package verification failed")
    _ok("final fixed release package is present and verified")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run FW v5.2.0 final release tag readiness checks.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow dirty working tree for local checkpoint validation.")
    parser.add_argument("--allow-existing-tag", action="store_true", help="Allow v5.2.0 tag to already exist.")
    parser.add_argument("--require-package", action="store_true", help="Require and verify release/ai-character-framework_v5.2.0.zip.")
    args = parser.parse_args(argv)

    root = _repo_root()
    _assert_doc(root)
    _assert_readme_and_checklist(root)
    _assert_git_state(root, allow_dirty=args.allow_dirty, allow_existing_tag=args.allow_existing_tag)
    _assert_package_tooling(root)
    _assert_release_gates(root)
    _assert_final_package(root, require_package=args.require_package)
    _ok("v5.2.0 final release tag readiness gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
