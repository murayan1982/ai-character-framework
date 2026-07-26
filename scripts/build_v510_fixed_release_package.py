"""Build and verify the fixed v5.1.0 release package.

This script is intentionally mock-safe. It runs the v5.1.0 release readiness
smoke on the source tree, creates a fixed ZIP, extracts that ZIP, and runs the
same readiness gate inside the extracted tree.

It does not call provider APIs, does not create real voice artifacts, and does
not create or push a git tag.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


VERSION = "5.1.0"
ARCHIVE_STEM = f"ai-character-framework_v{VERSION}"
ARCHIVE_NAME = f"{ARCHIVE_STEM}.zip"
MANIFEST_NAME = f"{ARCHIVE_STEM}_manifest.json"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "release",
    "tmp",
    "venv",
}

EXCLUDED_FILE_NAMES = {
    ".coverage",
}

REQUIRED_ARCHIVE_FILES = [
    "README.md",
    "framework/__init__.py",
    "framework/audio/voice_output.py",
    "framework/text_chat_result.py",
    "framework/capabilities.py",
    "framework/provider_config.py",
    "docs/v510_release_readiness_gate.md",
    "docs/v510_public_contract_conformance_gate.md",
    "docs/v510_package_import_readiness.md",
    "docs/v510_opaque_voice_artifact_contract.md",
    "scripts/smoke_v510_release_readiness_gate.py",
    "scripts/smoke_v510_public_contract_conformance_gate.py",
    "scripts/smoke_v510_package_import_readiness.py",
    "scripts/check_release_package.py",
]


class ReleasePackageFailure(RuntimeError):
    """Raised when release package validation fails."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleasePackageFailure(message)


def _run(command: list[str], *, cwd: Path) -> None:
    printable = " ".join(command)
    print(f"[RUN] {printable}")
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        check=False,
    )
    _require(completed.returncode == 0, f"command failed with code {completed.returncode}: {printable}")


def _is_excluded_dir(path: Path) -> bool:
    parts = tuple(path.parts)
    if len(parts) >= 2 and parts[0] == "config" and parts[1] == "tokens":
        return True
    if "tokens" in parts and "config" in parts:
        return True
    return any(part in EXCLUDED_DIR_NAMES for part in parts)


def _should_copy_file(path: Path) -> bool:
    if _is_excluded_dir(path):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False

    lower_name = path.name.lower()
    if lower_name == ".env" or (lower_name.startswith(".env.") and lower_name != ".env.example"):
        return False
    if lower_name.endswith("_token.json"):
        return False
    if path.suffix.lower() in {".mp3", ".wav", ".m4a"}:
        return False

    if path.name.startswith("apply_") and path.suffix == ".py":
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    return True


def _copy_source_tree(root: Path, staging_root: Path) -> None:
    target_root = staging_root / ARCHIVE_STEM
    target_root.mkdir(parents=True, exist_ok=True)

    for source in sorted(root.rglob("*")):
        rel = source.relative_to(root)

        if source.is_dir():
            if _is_excluded_dir(rel):
                continue
            (target_root / rel).mkdir(parents=True, exist_ok=True)
            continue

        if not _should_copy_file(rel):
            continue

        destination = target_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    for required in REQUIRED_ARCHIVE_FILES:
        _require((target_root / required).is_file(), f"required release file missing from staging tree: {required}")

    _require(not (target_root / ".git").exists(), "staging tree must not include .git")
    _require(not (target_root / "venv").exists(), "staging tree must not include venv")
    _require(not (target_root / ".venv").exists(), "staging tree must not include .venv")
    _require(not (target_root / "release").exists(), "staging tree must not include existing release output")


def _create_zip(staging_root: Path, archive_path: Path) -> None:
    source_root = staging_root / ARCHIVE_STEM
    if archive_path.exists():
        archive_path.unlink()

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_root.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = Path(ARCHIVE_STEM) / file_path.relative_to(source_root)
            zf.write(file_path, arcname.as_posix())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_archive_layout(archive_path: Path) -> dict[str, object]:
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = sorted(zf.namelist())

    prefix = f"{ARCHIVE_STEM}/"
    _require(names, "release archive is empty")
    _require(all(name.startswith(prefix) for name in names), "archive entries must be rooted under fixed release directory")

    required_entries = [prefix + required for required in REQUIRED_ARCHIVE_FILES]
    missing = [entry for entry in required_entries if entry not in names]
    _require(not missing, "required archive entries missing: " + ", ".join(missing))

    forbidden_fragments = [
        "/.git/",
        "/.venv/",
        "/venv/",
        "/__pycache__/",
        "/release/",
        "/config/tokens/",
        "/output/",
        "/temp/",
    ]
    forbidden = [
        name
        for name in names
        if any(fragment in name for fragment in forbidden_fragments)
        or name.endswith(".pyc")
        or Path(name).name.startswith("apply_")
        or Path(name).name.lower().endswith("_token.json")
        or Path(name).name.lower() == ".env"
        or (Path(name).name.lower().startswith(".env.") and Path(name).name.lower() != ".env.example")
        or Path(name).suffix.lower() in {".mp3", ".wav", ".m4a"}
    ]
    _require(not forbidden, "forbidden archive entries present: " + ", ".join(forbidden[:12]))

    return {
        "entry_count": len(names),
        "required_entries": required_entries,
    }


def _verify_extracted_archive(archive_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="fw_v510_release_extract_") as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(temp_root)

        extracted_root = temp_root / ARCHIVE_STEM
        _require(extracted_root.is_dir(), "extracted release root missing")

        _run([sys.executable, "-m", "compileall", "-q", "."], cwd=extracted_root)
        _run([sys.executable, "scripts/smoke_v510_release_readiness_gate.py"], cwd=extracted_root)


def _write_manifest(archive_path: Path, manifest_path: Path, layout: dict[str, object]) -> None:
    manifest = {
        "version": VERSION,
        "archive_name": archive_path.name,
        "archive_size_bytes": archive_path.stat().st_size,
        "sha256": _sha256(archive_path),
        "mock_safe": True,
        "provider_execution": False,
        "tag_created": False,
        "layout": layout,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    root = _repo_root()
    release_dir = root / "release"
    release_dir.mkdir(exist_ok=True)

    archive_path = release_dir / ARCHIVE_NAME
    manifest_path = release_dir / MANIFEST_NAME

    _run([sys.executable, "scripts/smoke_v510_release_readiness_gate.py"], cwd=root)

    with tempfile.TemporaryDirectory(prefix="fw_v510_release_stage_") as temp_dir:
        staging_root = Path(temp_dir)
        _copy_source_tree(root, staging_root)
        _create_zip(staging_root, archive_path)

    layout = _verify_archive_layout(archive_path)
    _verify_extracted_archive(archive_path)
    _write_manifest(archive_path, manifest_path, layout)

    print(f"[OK] built fixed v{VERSION} release package: {archive_path}")
    print(f"[OK] wrote release manifest: {manifest_path}")
    print(f"[INFO] sha256={_sha256(archive_path)}")
    print("[OK] v5.1.0 fixed release package is verified")


if __name__ == "__main__":
    main()
