"""Build the deterministic AI Character Framework v6.0.0 source package.

The builder uses Git membership, rejects private artifact path names before
filtering, writes normalized ZIP metadata, and never imports Framework or
provider modules.  ``additional_files`` exists only for the exact reviewed
FW-RT6-14c checkpoint; official artifacts must be built from a clean commit.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import subprocess
import tarfile
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath


VERSION = "6.0.0"
TAG = f"v{VERSION}"
PACKAGE_BASENAME = f"ai-character-framework_v{VERSION}.zip"
DEFAULT_OUTPUT = Path("release") / PACKAGE_BASENAME
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)

REQUIRED_PACKAGE_FILES = frozenset(
    {
        ".env.example",
        "LICENSE.txt",
        "README.md",
        "pyproject.toml",
        "requirements.txt",
        "framework/__init__.py",
        "framework/version.py",
        "docs/RELEASE_NOTES.md",
        "docs/release_notes_v6.0.0.md",
        "docs/release_package_policy.md",
        "docs/v600_deterministic_release.md",
        "scripts/build_v600_release_package.py",
        "scripts/check_v600_release_readiness.py",
        "scripts/check_v600_release_package_smoke.py",
        "scripts/operator_v600_github_release.py",
    }
)

EXCLUDE_EXACT = frozenset({".gitignore", ".vscode/settings.json"})
EXCLUDE_PREFIXES = (
    ".git/",
    ".github/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".tox/",
    ".venv/",
    "build/",
    "dist/",
    "release/",
    "venv/",
)
EXCLUDE_SUFFIXES = (
    ".log",
    ".pyc",
    ".pyd",
    ".pyo",
)
PRIVATE_PREFIXES = (
    "artifacts/",
    "config/tokens/",
    "evidence/",
    "operator_evidence/",
    "private/",
)
PRIVATE_BASENAMES = frozenset(
    {
        ".env",
        "bootstrap_evidence.json",
        "private_operator_config.json",
        "real_motion_operator_evidence.json",
        "real_runtime_operator_evidence.json",
        "vts_private_config.json",
    }
)
PRIVATE_SUFFIXES = (
    "_credentials.json",
    "_evidence.json",
    "_private_config.json",
    "_secret.json",
    "_token.json",
)
PRIVATE_MEDIA_SUFFIXES = (
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
)


def repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()).resolve()


def _run_git(root: Path, *arguments: str, binary: bool = False):
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=not binary,
    ).stdout


def git_tracked_files(root: Path) -> list[str]:
    output = _run_git(root, "ls-files", "-z", binary=True)
    return [
        item.decode("utf-8").replace("\\", "/")
        for item in output.split(b"\0")
        if item
    ]


def git_changed_files(root: Path) -> set[str]:
    commands = (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    paths: set[str] = set()
    for arguments in commands:
        output = _run_git(root, *arguments)
        paths.update(
            line.strip().replace("\\", "/")
            for line in output.splitlines()
            if line.strip()
        )
    paths.discard(".vscode/settings.json")
    return paths


def normalize_member(raw: str) -> str:
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    first_part = path.parts[0] if path.parts else ""
    if (
        not normalized
        or normalized == "."
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or ":" in first_part
    ):
        raise RuntimeError("unsafe package member path rejected")
    return path.as_posix()


def private_artifact_hits(paths: Iterable[str]) -> list[str]:
    hits: set[str] = set()
    for raw in paths:
        normalized = normalize_member(raw)
        folded = normalized.casefold()
        basename = PurePosixPath(folded).name
        if basename == ".env.example":
            continue
        if (
            basename in PRIVATE_BASENAMES
            or basename.startswith(".env.")
            or basename.endswith(PRIVATE_SUFFIXES)
            or folded.endswith(PRIVATE_MEDIA_SUFFIXES)
            or any(
                folded.startswith(prefix) or f"/{prefix}" in folded
                for prefix in PRIVATE_PREFIXES
            )
        ):
            hits.add(normalized)
    return sorted(hits)


def is_included(path: str) -> bool:
    normalized = normalize_member(path)
    folded = normalized.casefold()
    if normalized in EXCLUDE_EXACT:
        return False
    if any(folded.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if any(folded.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return False
    return True


def package_files(
    root: Path | None = None,
    *,
    additional_files: Iterable[str] = (),
) -> list[str]:
    root = (root or repo_root()).resolve()
    tracked = set(git_tracked_files(root))
    tracked_private = private_artifact_hits(tracked)
    if tracked_private:
        raise RuntimeError(
            "tracked private artifact rejected before filtering: "
            + ", ".join(tracked_private)
        )

    extras = {normalize_member(path) for path in additional_files if path}
    if extras:
        unexpected = sorted(extras - git_changed_files(root))
        if unexpected:
            raise RuntimeError(
                "candidate package member is not a changed file: "
                + ", ".join(unexpected)
            )
        missing = sorted(path for path in extras if not (root / path).is_file())
        if missing:
            raise RuntimeError(
                "candidate package member is unavailable: " + ", ".join(missing)
            )
        extra_private = private_artifact_hits(extras)
        if extra_private:
            raise RuntimeError(
                "private candidate artifact rejected: " + ", ".join(extra_private)
            )

    files = sorted(path for path in tracked | extras if is_included(path))
    missing_required = sorted(REQUIRED_PACKAGE_FILES - set(files))
    if missing_required:
        raise RuntimeError(
            "required v6.0.0 package files missing: " + ", ".join(missing_required)
        )
    return files


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    return info


def _source_bytes(
    root: Path,
    files: Iterable[str],
    *,
    worktree_files: set[str],
) -> dict[str, bytes]:
    """Read committed members from Git blobs and candidate members from disk."""

    requested = set(files)
    archive_bytes = _run_git(root, "archive", "--format=tar", "HEAD", binary=True)
    contents: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive.getmembers():
            normalized = member.name.replace("\\", "/")
            if normalized not in requested or normalized in worktree_files:
                continue
            stream = archive.extractfile(member)
            if stream is not None:
                contents[normalized] = stream.read()
    for relative in worktree_files:
        if relative in requested:
            contents[relative] = (root / relative).read_bytes()
    missing = sorted(requested - set(contents))
    if missing:
        raise RuntimeError("package source bytes unavailable: " + ", ".join(missing))
    return contents


def assert_clean_main(root: Path) -> None:
    branch = _run_git(root, "branch", "--show-current").strip()
    head = _run_git(root, "rev-parse", "HEAD").strip()
    origin_main = _run_git(root, "rev-parse", "origin/main").strip()
    status = _run_git(root, "status", "--porcelain", "--untracked-files=all").strip()
    if branch != "main" or status or head != origin_main:
        raise RuntimeError("official package build requires clean main at origin/main")


def build_package(
    output: Path,
    *,
    root: Path | None = None,
    additional_files: Iterable[str] = (),
) -> tuple[str, int]:
    root = (root or repo_root()).resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = package_files(root, additional_files=additional_files)
    worktree_files = {normalize_member(path) for path in additional_files if path}
    contents = _source_bytes(root, files, worktree_files=worktree_files)
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative in files:
            archive.writestr(_zip_info(relative), contents[relative])
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return digest, len(files)


def dry_run(
    root: Path | None = None,
    *,
    additional_files: Iterable[str] = (),
) -> tuple[str, int]:
    root = (root or repo_root()).resolve()
    with tempfile.TemporaryDirectory(prefix="acf_v600_release_") as temporary:
        output = Path(temporary) / PACKAGE_BASENAME
        return build_package(output, root=root, additional_files=additional_files)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic v6.0.0 package")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    root = repo_root()
    if arguments.dry_run:
        digest, count = dry_run(root)
        output_marker = "temporary-directory-only"
    else:
        assert_clean_main(root)
        output = (root / arguments.output).resolve()
        digest, count = build_package(output, root=root)
        output_marker = output.name
    print("fwrt6_14c_package_builder_status: completed")
    print(f"fwrt6_14c_package_version: {VERSION}")
    print(f"fwrt6_14c_package_output: {output_marker}")
    print(f"fwrt6_14c_package_file_count: {count}")
    print(f"fwrt6_14c_package_sha256: {digest}")
    print(f"fwrt6_14c_official_artifact_written: {not arguments.dry_run}")
    print("fwrt6_14c_provider_network_device_execution: False")
    print("fwrt6_14c_private_artifact_read: False")
    print("fwrt6_14c_tag_push_release_execution: False")


if __name__ == "__main__":
    main()
