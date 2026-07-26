"""Final v5.1.0 release tag readiness gate.

This smoke is intentionally mock-safe. By default it can run while this
checkpoint itself is still uncommitted. Use --require-clean-tree only after
committing the checkpoint and immediately before creating the release tag.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


VERSION = "5.1.0"
TAG = "v5.1.0"


class ContractFailure(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _warn(message: str) -> None:
    print(f"[WARN] {message}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run(root: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    printable = " ".join(command)
    print(f"[RUN] {printable}")
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env.setdefault("FRAMEWORK_VOICE_OUTPUT_REAL_TTS", "0")
    env.setdefault("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION", "0")
    return subprocess.run(command, cwd=root, text=True, env=env)


def _run_required(root: Path, command: list[str]) -> None:
    completed = _run(root, command)
    _require(completed.returncode == 0, f"command failed with code {completed.returncode}: {' '.join(command)}")


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_available(root: Path) -> bool:
    completed = _git(root, ["rev-parse", "--is-inside-work-tree"])
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _assert_doc(root: Path) -> None:
    doc = root / "docs" / "v510_final_release_tag_readiness.md"
    _require(doc.exists(), "missing docs/v510_final_release_tag_readiness.md")
    text = doc.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.1.0 Final Release Tag Readiness",
        "fixed release package verification passes",
        "working tree is clean before the release tag is created",
        "`v5.1.0` tag does not already exist",
        "must not",
        "call real provider APIs",
        "commit generated release ZIPs",
        "create or push Git tags",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"final release tag readiness doc missing phrase: {phrase}")
    _ok("v5.1.0 final release tag readiness doc is documented")


def _assert_required_files(root: Path) -> None:
    required_files = [
        "README.md",
        ".env.example",
        "install.bat",
        "run.bat",
        "docs/v510_release_readiness_gate.md",
        "docs/v510_fixed_release_package.md",
        "docs/v510_fixed_release_package_verification.md",
        "docs/v510_final_release_tag_readiness.md",
        "scripts/check_release_package.py",
        "scripts/build_v510_fixed_release_package.py",
        "scripts/smoke_v510_release_readiness_gate.py",
        "scripts/smoke_v510_fixed_release_package_verification.py",
        "scripts/smoke_v510_final_release_tag_readiness.py",
    ]
    missing = [item for item in required_files if not (root / item).exists()]
    _require(not missing, "missing required final release readiness files: " + ", ".join(missing))
    _ok("v5.1.0 final release tag readiness required files are present")


def _assert_release_artifacts(root: Path, expected_version: str) -> None:
    release_dir = root / "release"
    zip_path = release_dir / f"ai-character-framework_v{expected_version}.zip"
    manifest_path = release_dir / f"ai-character-framework_v{expected_version}_manifest.json"

    _require(zip_path.exists(), f"missing fixed release ZIP: {zip_path}")
    _require(manifest_path.exists(), f"missing fixed release manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
    manifest_text = json.dumps(manifest, sort_keys=True)
    _require(expected_version in manifest_text, "release manifest is not version-marked")
    _require(zip_path.stat().st_size > 0, "fixed release ZIP is empty")

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    _require(any(name.endswith(".env.example") for name in names), "release ZIP should include .env.example")
    forbidden_hits = []
    for name in names:
        normalized = name.replace("\\", "/")
        lower = normalized.lower()
        if lower.endswith(".env.example"):
            continue
        if (
            "/config/tokens/" in normalized
            or lower.endswith("_token.json")
            or lower.endswith(".env")
            or "/.env." in lower
            or lower.endswith((".mp3", ".wav", ".m4a"))
        ):
            forbidden_hits.append(name)
    _require(not forbidden_hits, "release ZIP contains local-only/private artifacts: " + ", ".join(forbidden_hits[:16]))
    _ok("v5.1.0 final release artifacts are present and secret-safe")


def _assert_git_state(root: Path, *, expected_tag: str, require_clean_tree: bool, allow_existing_tag: bool) -> None:
    if not _git_available(root):
        _warn("git repository not available; skipping strict Git state checks")
        return

    tag_check = _git(root, ["rev-parse", "--verify", f"refs/tags/{expected_tag}"])
    if tag_check.returncode == 0:
        _require(allow_existing_tag, f"tag already exists: {expected_tag}")
        _warn(f"tag already exists and was allowed: {expected_tag}")
    else:
        _ok(f"release tag is available: {expected_tag}")

    status = _git(root, ["status", "--porcelain"])
    _require(status.returncode == 0, "git status failed")
    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    if require_clean_tree:
        _require(not dirty_lines, "working tree must be clean before tagging:\n" + "\n".join(dirty_lines[:32]))
        _ok("working tree is clean for final release tagging")
    elif dirty_lines:
        _warn(f"working tree has {len(dirty_lines)} pending change(s); run with --require-clean-tree after commit and before tagging")
    else:
        _ok("working tree is clean")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", default=VERSION)
    parser.add_argument("--expected-tag", default=TAG)
    parser.add_argument("--require-clean-tree", action="store_true")
    parser.add_argument("--allow-existing-tag", action="store_true")
    args = parser.parse_args()

    root = _repo_root()

    _assert_doc(root)
    _assert_required_files(root)

    _run_required(root, [sys.executable, "scripts/smoke_v510_release_readiness_gate.py"])
    _run_required(root, [sys.executable, "scripts/smoke_v510_fixed_release_package_verification.py"])
    _run_required(root, [sys.executable, "scripts/check_release_package.py"])

    _assert_release_artifacts(root, args.expected_version)
    _assert_git_state(
        root,
        expected_tag=args.expected_tag,
        require_clean_tree=args.require_clean_tree,
        allow_existing_tag=args.allow_existing_tag,
    )

    _ok("v5.1.0 final release tag readiness is mock-safe")


if __name__ == "__main__":
    main()
