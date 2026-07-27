"""Build the v5.3.0 release package.

This script creates a deterministic source package from git-tracked files only.
It excludes generated release archives, local editor settings, private evidence,
and environment files.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
import zipfile
from pathlib import Path

VERSION = "5.3.0"
PACKAGE_BASENAME = "ai-character-framework_v5.3.0.zip"
DEFAULT_OUTPUT = Path("release") / PACKAGE_BASENAME

REQUIRED_PACKAGE_FILES = {
    "README.md",
    "framework/__init__.py",
    "framework/voice_input_audio.py",
    "framework/voice_input_provider_adapter.py",
    "framework/voice_input_session.py",
    "docs/v530_real_stt_provider_boundary_inventory.md",
    "docs/v530_host_audio_source_contract.md",
    "docs/v530_lazy_provider_adapter_fake.md",
    "docs/v530_voice_input_session_adapter_wiring.md",
    "docs/v530_guarded_real_provider_adapter.md",
    "docs/v530_drc_public_handoff_verification.md",
    "docs/v530_release_readiness_gate.md",
    "examples/voice_input_drc_public_handoff.py",
    "scripts/smoke_v530_real_stt_provider_boundary_inventory.py",
    "scripts/smoke_v530_host_audio_source_contract.py",
    "scripts/smoke_v530_lazy_provider_adapter_fake.py",
    "scripts/smoke_v530_voice_input_session_adapter_wiring.py",
    "scripts/smoke_v530_guarded_real_provider_adapter.py",
    "scripts/smoke_v530_drc_public_handoff_verification.py",
    "scripts/smoke_v530_release_readiness_gate.py",
}

EXCLUDE_PREFIXES = (
    ".git/",
    ".github/workflows/private",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".venv/",
    "venv/",
    "operator_evidence/",
    "private/",
    "release/",
)

EXCLUDE_SUFFIXES = (
    ".env",
    ".env.local",
    ".pyc",
    ".pyo",
    ".zip",
)

EXCLUDE_EXACT = {
    ".vscode/settings.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_ls_files(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(root),
        check=True,
        stdout=subprocess.PIPE,
    )
    return [
        part.decode("utf-8").replace("\\", "/")
        for part in completed.stdout.split(b"\0")
        if part
    ]


def _is_included(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized in EXCLUDE_EXACT:
        return False
    if any(normalized.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if any(normalized.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return False
    if "/.env" in normalized or "/operator_evidence/" in normalized:
        return False
    return True


def package_files(root: Path | None = None) -> list[str]:
    root = root or repo_root()
    files = sorted(path for path in _git_ls_files(root) if _is_included(path))
    missing = sorted(path for path in REQUIRED_PACKAGE_FILES if path not in files)
    if missing:
        raise RuntimeError(f"required v{VERSION} package files missing from git-tracked package set: {missing}")
    return files


def build_package(output: Path, *, root: Path | None = None) -> tuple[str, int]:
    root = root or repo_root()
    output = output if output.is_absolute() else root / output
    output.parent.mkdir(parents=True, exist_ok=True)

    files = package_files(root)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in files:
            source = root / rel
            info = zipfile.ZipInfo(rel)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, source.read_bytes())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return digest, len(files)


def build_dry_run(*, root: Path | None = None) -> tuple[str, int, Path]:
    root = root or repo_root()
    with tempfile.TemporaryDirectory(prefix="acf_v530_release_package_") as temp:
        output = Path(temp) / PACKAGE_BASENAME
        digest, count = build_package(output, root=root)
        # Materialize digest/count while the temp package exists, then return a
        # non-release path marker for smoke output.
        return digest, count, output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v5.3.0 release package")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="release package output path")
    parser.add_argument("--dry-run", action="store_true", help="build in a temporary directory instead of release/")
    args = parser.parse_args()

    root = repo_root()
    if args.dry_run:
        digest, count, output = build_dry_run(root=root)
        print("v530_release_package_dry_run: True")
        print(f"v530_release_package_path: {output}")
    else:
        output = Path(args.output)
        digest, count = build_package(output, root=root)
        resolved = output if output.is_absolute() else root / output
        print("v530_release_package_dry_run: False")
        print(f"v530_release_package_path: {resolved}")

    print(f"v530_release_package_file_count: {count}")
    print(f"v530_release_package_sha256: {digest}")
    print("v530_release_package_provider_execution_executed: False")
    print("v530_release_package_microphone_accessed: False")
    print("v530_release_package_audio_handled: False")


if __name__ == "__main__":
    main()
