\
"""Build the deterministic AI-Character-Framework v5.4.0 source package.

The package is created from git-tracked files only. Generated release archives,
local editor settings, environment files, bytecode/cache files, and private
operator evidence/audio/transcripts are excluded.

The default command writes the final ZIP and SHA-256 sidecar under ``release/``.
Use ``--dry-run`` to build only in a temporary directory.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
import zipfile
from pathlib import Path


VERSION = "5.4.0"
PACKAGE_BASENAME = f"ai-character-framework_v{VERSION}.zip"
DEFAULT_OUTPUT = Path("release") / PACKAGE_BASENAME

REQUIRED_PACKAGE_FILES = {
    "README.md",
    "framework/__init__.py",
    "framework/voice_input_audio.py",
    "framework/voice_input_provider_adapter.py",
    "framework/voice_input_session.py",
    "framework/voice_input_provider_execution.py",
    "framework/openai_voice_input_provider_adapter.py",
    "framework/openai_voice_input_fake_execution.py",
    "framework/openai_voice_input_real_provider.py",
    "docs/v540_provider_execution_configuration_status.md",
    "docs/v540_openai_adapter_client_injection_contract.md",
    "docs/v540_openai_fake_execution_boundary.md",
    "docs/v540_openai_real_provider_runtime.md",
    "docs/v540_openai_private_real_provider_operator_acceptance.md",
    "docs/v540_real_stt_provider_execution_requirements.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "docs/v540_release_readiness_gate.md",
    "docs/v540_release_package_gate.md",
    "scripts/operator_v540_openai_private_real_provider_acceptance.py",
    "scripts/verify_v540_openai_private_real_provider_evidence.py",
    "scripts/smoke_v540_provider_execution_configuration_status.py",
    "scripts/smoke_v540_openai_adapter_client_injection_contract.py",
    "scripts/smoke_v540_openai_fake_execution_boundary.py",
    "scripts/smoke_v540_openai_real_provider_runtime.py",
    "scripts/smoke_v540_openai_private_real_provider_operator_acceptance.py",
    "scripts/smoke_v540_real_stt_provider_execution_requirements.py",
    "scripts/smoke_v540_release_readiness_gate.py",
    "scripts/smoke_v540_release_package_gate.py",
    "scripts/build_v540_release_package.py",
}

EXCLUDE_PREFIXES = (
    ".git/",
    ".github/workflows/private",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".tox/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "operator_evidence/",
    "release/",
)

EXCLUDE_SUFFIXES = (
    ".env",
    ".env.local",
    ".pyc",
    ".pyo",
    ".pyd",
    ".wav",
)

EXCLUDE_EXACT = {
    ".vscode/settings.json",
}

PRIVATE_BASENAMES = {
    "operator_evidence.json",
    "private_transcript.txt",
    "private_staged_audio.wav",
    "private_stt_sample.wav",
}

ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _git_ls_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8").replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _is_included(path: str) -> bool:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    basename = Path(normalized).name.lower()

    if normalized in EXCLUDE_EXACT:
        return False
    if any(normalized.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if any(lower.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return False
    if "/.env" in lower or "/operator_evidence/" in lower:
        return False
    if basename in PRIVATE_BASENAMES:
        return False
    return True


def package_files(root: Path | None = None) -> list[str]:
    root = root or repo_root()
    files = sorted(
        path
        for path in _git_ls_files(root)
        if _is_included(path)
    )
    missing = sorted(
        path for path in REQUIRED_PACKAGE_FILES if path not in files
    )
    if missing:
        raise RuntimeError(
            f"required v{VERSION} package files missing from "
            f"git-tracked package set: {missing}"
        )
    return files


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    return info


def build_package(
    output: Path,
    *,
    root: Path | None = None,
) -> tuple[str, int]:
    root = root or repo_root()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files = package_files(root)

    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative in files:
            source = root / relative
            archive.writestr(_zip_info(relative), source.read_bytes())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(
        f"{digest}  {output.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    return digest, len(files)


def dry_run(root: Path | None = None) -> tuple[str, int]:
    root = root or repo_root()
    with tempfile.TemporaryDirectory(
        prefix="acf_v540_release_package_"
    ) as temp:
        output = Path(temp) / PACKAGE_BASENAME
        digest, count = build_package(output, root=root)
        if not output.is_file():
            raise RuntimeError("dry-run package was not created")
        if not output.with_suffix(output.suffix + ".sha256").is_file():
            raise RuntimeError("dry-run SHA-256 sidecar was not created")
        return digest, count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build v5.4.0 release package"
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="release package output path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build in a temporary directory instead of release/",
    )
    args = parser.parse_args()

    root = repo_root()
    if args.dry_run:
        digest, count = dry_run(root)
        output_marker = "temporary-directory-only"
    else:
        output = (root / args.output).resolve()
        digest, count = build_package(output, root=root)
        output_marker = output.name

    print("v540_release_package_builder_status: completed")
    print(f"v540_release_package_version: {VERSION}")
    print(f"v540_release_package_output: {output_marker}")
    print(f"v540_release_package_file_count: {count}")
    print(f"v540_release_package_sha256: {digest}")
    print(
        "v540_release_package_created_in_release_dir:",
        not args.dry_run,
    )
    print("v540_release_package_provider_execution_executed: False")
    print("v540_release_package_openai_sdk_imported: False")
    print("v540_release_package_credential_read: False")
    print("v540_release_package_private_evidence_read: False")
    print("v540_release_package_private_audio_read: False")
    print("v540_release_package_private_transcript_read: False")
    print("v540_release_package_microphone_accessed: False")
    print("v540_release_package_drc_changed: False")
    print("v540_release_package_tag_created: False")
    print("v540_release_package_push_performed: False")


if __name__ == "__main__":
    main()
