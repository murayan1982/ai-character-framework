"""Build the fixed AI-Character-Framework v5.2.0 release package.

The builder is intentionally provider-safe. It runs the v5.2.0 source-tree
release readiness gate before packaging unless --skip-checks is provided.

The produced zip is deterministic for the same committed source tree: file order,
zip timestamps, permissions, and manifest content are normalized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

VERSION = "5.2.0"
PACKAGE_BASENAME = f"ai-character-framework_v{VERSION}"
PACKAGE_FILENAME = f"{PACKAGE_BASENAME}.zip"
SHA256_FILENAME = f"{PACKAGE_BASENAME}.sha256.txt"
MANIFEST_ARCNAME = f"RELEASE_MANIFEST_v{VERSION}.json"

NORMALIZED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)

EXCLUDED_DIR_NAMES = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".release_build",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "release",
    "venv",
}

EXCLUDED_FILE_SUFFIXES = {
    ".log",
    ".pyc",
    ".pyo",
    ".tmp",
    ".zip",
}

EXCLUDED_FILE_NAMES = {
    ".coverage",
    ".DS_Store",
    "Thumbs.db",
}


@dataclass(frozen=True)
class FileEntry:
    path: Path
    arcname: str
    size: int
    sha256: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _git_commit(root: Path) -> str:
    completed = _run(root, ["git", "rev-parse", "HEAD"])
    if completed.returncode != 0:
        raise SystemExit("git rev-parse HEAD failed:\n" + completed.stdout)
    return completed.stdout.strip()


def _assert_git_clean(root: Path, *, allow_dirty: bool) -> None:
    if allow_dirty:
        return

    completed = _run(root, ["git", "status", "--porcelain"])
    if completed.returncode != 0:
        raise SystemExit("git status --porcelain failed:\n" + completed.stdout)

    if completed.stdout.strip():
        raise SystemExit(
            "working tree is not clean; commit or stash changes before fixed release packaging "
            "(or pass --allow-dirty for local experiments only)\n"
            + completed.stdout
        )


def _run_readiness_gate(root: Path, *, skip_checks: bool) -> None:
    if skip_checks:
        return

    readiness = root / "scripts" / "smoke_v520_release_readiness_gate.py"
    if not readiness.exists():
        raise SystemExit("missing scripts/smoke_v520_release_readiness_gate.py")

    completed = _run(root, [sys.executable, str(readiness)])
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.returncode != 0:
        raise SystemExit("v5.2.0 release readiness gate failed")


def _is_excluded(root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    lowered_parts = {part.lower() for part in parts}
    name = path.name
    lower_name = name.lower()

    if lowered_parts & EXCLUDED_DIR_NAMES:
        return True

    if "operator_evidence" in lowered_parts:
        return True

    if name in EXCLUDED_FILE_NAMES:
        return True

    if path.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
        return True

    if name.startswith("apply_") and name.endswith(".py"):
        return True

    if lower_name.startswith(".env"):
        return True

    if lower_name.endswith(".secret") or lower_name.endswith(".secrets"):
        return True

    if lower_name in {"secrets.json", "credentials.json", "token.json"}:
        return True

    return False


def _iter_release_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file() and not _is_excluded(root, path):
            yield path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _collect_entries(root: Path) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for path in _iter_release_files(root):
        data = path.read_bytes()
        entries.append(
            FileEntry(
                path=path,
                arcname=path.relative_to(root).as_posix(),
                size=len(data),
                sha256=_sha256_bytes(data),
            )
        )
    return entries


def _manifest_bytes(*, root: Path, entries: list[FileEntry], git_commit: str) -> bytes:
    manifest = {
        "package": "ai-character-framework",
        "version": VERSION,
        "git_commit": git_commit,
        "builder": "scripts/build_v520_release_package.py",
        "readiness_gate": "scripts/smoke_v520_release_readiness_gate.py",
        "deterministic_zip": True,
        "normalized_zip_datetime": NORMALIZED_ZIP_DATETIME,
        "file_count": len(entries),
        "files": [
            {
                "path": entry.arcname,
                "bytes": entry.size,
                "sha256": entry.sha256,
            }
            for entry in entries
        ],
    }
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def _zipinfo(arcname: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(arcname, NORMALIZED_ZIP_DATETIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def _write_zip(output_path: Path, *, root: Path, entries: list[FileEntry], manifest: bytes) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for entry in entries:
            archive.writestr(_zipinfo(entry.arcname), entry.path.read_bytes())
        archive.writestr(_zipinfo(MANIFEST_ARCNAME), manifest)


def _write_sha256(output_path: Path, digest: str) -> Path:
    sha_path = output_path.with_name(SHA256_FILENAME)
    sha_path.write_text(f"{digest}  {output_path.name}\n", encoding="utf-8")
    return sha_path


def build_release_package(
    *,
    output_path: Path | None = None,
    allow_dirty: bool = False,
    skip_checks: bool = False,
    dry_run: bool = False,
) -> Path:
    root = _repo_root()
    output_path = output_path or root / "release" / PACKAGE_FILENAME

    _assert_git_clean(root, allow_dirty=allow_dirty)
    _run_readiness_gate(root, skip_checks=skip_checks)

    git_commit = _git_commit(root)
    entries = _collect_entries(root)
    manifest = _manifest_bytes(root=root, entries=entries, git_commit=git_commit)

    if dry_run:
        print("[DRY-RUN] v5.2.0 release package builder ready")
        print(f"package: {output_path}")
        print(f"version: {VERSION}")
        print(f"git_commit: {git_commit}")
        print(f"file_count: {len(entries)}")
        print(f"manifest: {MANIFEST_ARCNAME}")
        return output_path

    _write_zip(output_path, root=root, entries=entries, manifest=manifest)
    digest = _sha256_bytes(output_path.read_bytes())
    sha_path = _write_sha256(output_path, digest)

    print("[OK] v5.2.0 fixed release package created")
    print(f"package: {output_path}")
    print(f"sha256: {digest}")
    print(f"sha256_file: {sha_path}")
    print(f"file_count: {len(entries)}")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the fixed AI-Character-Framework v5.2.0 release package.")
    parser.add_argument("--output", type=Path, default=None, help="Output zip path. Defaults to release/ai-character-framework_v5.2.0.zip")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow packaging a dirty working tree. Use only for local experiments.")
    parser.add_argument("--skip-checks", action="store_true", help="Skip v5.2.0 release readiness gate. Use only for local experiments.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print planned package metadata without writing files.")
    args = parser.parse_args(argv)

    build_release_package(
        output_path=args.output,
        allow_dirty=args.allow_dirty,
        skip_checks=args.skip_checks,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
