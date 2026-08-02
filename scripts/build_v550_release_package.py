"""Build the deterministic AI-Character-Framework v5.5.0 package.

The final command writes the ZIP and SHA-256 sidecar under ``release/``.
FW-VTS-0f4a invokes this module only through temporary-directory builds.

The builder checks git-tracked path names for private VTube Studio artifacts
before filtering. It never opens private token, configuration, or evidence
files.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path


VERSION = "5.5.0"
PACKAGE_BASENAME = f"ai-character-framework_v{VERSION}.zip"
DEFAULT_OUTPUT = Path("release") / PACKAGE_BASENAME

REQUIRED_PACKAGE_FILES = {
    "README.md",
    ".env.example",
    "requirements.txt",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_adapter_execution.py",
    "framework/motion_session.py",
    "framework/vtube_studio_transport.py",
    "framework/vtube_studio_pyvts_transport.py",
    "framework/vtube_studio_motion_composition.py",
    "docs/v550_motion_adapter_configuration_status.md",
    "docs/v550_vtube_studio_transport_protocol_fake.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_release_readiness_gate.md",
    "docs/v550_release_package_gate.md",
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
    "scripts/smoke_v550_vtube_studio_transport_protocol_fake.py",
    "scripts/smoke_v550_vtube_studio_pyvts_transport.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/smoke_v550_release_package_gate.py",
    "scripts/check_v550_release_package_gate.py",
    "scripts/build_v550_release_package.py",
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
    "release/",
)

EXCLUDE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pyd",
    ".wav",
)

EXCLUDE_EXACT = {
    ".vscode/settings.json",
}

PRIVATE_TRACKED_PREFIXES = (
    "config/tokens/",
    "operator_evidence/",
)

PRIVATE_TRACKED_BASENAMES = {
    "vts_private_config.json",
    "bootstrap_evidence.json",
    "real_motion_operator_evidence.json",
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


def _git_changed_paths(root: Path) -> set[str]:
    commands = (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    paths: set[str] = set()
    for command in commands:
        completed = subprocess.run(
            ["git", *command],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        paths.update(
            line.strip().replace("\\", "/")
            for line in completed.stdout.splitlines()
            if line.strip()
        )
    paths.discard(".vscode/settings.json")
    return paths


def private_tracked_hits(paths: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for raw in paths:
        normalized = raw.replace("\\", "/")
        lower = normalized.casefold()
        basename = Path(normalized).name.casefold()

        if any(
            lower.startswith(prefix)
            or f"/{prefix}" in lower
            for prefix in PRIVATE_TRACKED_PREFIXES
        ):
            hits.append(normalized)
            continue
        if basename.endswith("_token.json"):
            hits.append(normalized)
            continue
        if basename in PRIVATE_TRACKED_BASENAMES:
            hits.append(normalized)

    return sorted(set(hits))


def _is_private_env(path: str) -> bool:
    normalized = path.replace("\\", "/")
    basename = Path(normalized).name.casefold()
    if basename == ".env.example":
        return False
    return basename == ".env" or basename.startswith(".env.")


def _is_included(path: str) -> bool:
    normalized = path.replace("\\", "/")
    lower = normalized.casefold()

    if normalized in EXCLUDE_EXACT:
        return False
    if any(lower.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if any(lower.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return False
    if _is_private_env(normalized):
        return False
    return True


def package_files(
    root: Path | None = None,
    *,
    additional_files: Iterable[str] = (),
) -> list[str]:
    root = root or repo_root()
    tracked = set(_git_ls_files(root))

    private_hits = private_tracked_hits(tracked)
    if private_hits:
        raise RuntimeError(
            "tracked private VTS artifact rejected before package filtering: "
            + ", ".join(private_hits)
        )

    extras = {
        item.replace("\\", "/")
        for item in additional_files
        if item
    }
    if extras:
        changed = _git_changed_paths(root)
        unexpected = sorted(extras - changed)
        if unexpected:
            raise RuntimeError(
                "explicit package worktree file is not changed: "
                + ", ".join(unexpected)
            )
        missing_extra = sorted(
            item for item in extras if not (root / item).is_file()
        )
        if missing_extra:
            raise RuntimeError(
                "explicit package worktree file is unavailable: "
                + ", ".join(missing_extra)
            )
        private_extra_hits = private_tracked_hits(extras)
        if private_extra_hits:
            raise RuntimeError(
                "private VTS artifact rejected from explicit package surface: "
                + ", ".join(private_extra_hits)
            )

    candidates = tracked | extras
    files = sorted(
        path for path in candidates if _is_included(path)
    )

    missing = sorted(
        path for path in REQUIRED_PACKAGE_FILES if path not in files
    )
    if missing:
        raise RuntimeError(
            f"required v{VERSION} package files missing from package set: "
            f"{missing}"
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
    additional_files: Iterable[str] = (),
) -> tuple[str, int]:
    root = root or repo_root()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files = package_files(
        root,
        additional_files=additional_files,
    )

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


def dry_run(
    root: Path | None = None,
    *,
    additional_files: Iterable[str] = (),
) -> tuple[str, int]:
    root = root or repo_root()
    with tempfile.TemporaryDirectory(
        prefix="acf_v550_release_package_"
    ) as temporary:
        output = Path(temporary) / PACKAGE_BASENAME
        digest, count = build_package(
            output,
            root=root,
            additional_files=additional_files,
        )
        if not output.is_file():
            raise RuntimeError("dry-run package was not created")
        if not output.with_suffix(
            output.suffix + ".sha256"
        ).is_file():
            raise RuntimeError("dry-run SHA-256 sidecar was not created")
        return digest, count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build v5.5.0 release package"
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

    print("v550_release_package_builder_status: completed")
    print(f"v550_release_package_version: {VERSION}")
    print(f"v550_release_package_output: {output_marker}")
    print(f"v550_release_package_file_count: {count}")
    print(f"v550_release_package_sha256: {digest}")
    print(
        "v550_release_package_created_in_release_dir:",
        not args.dry_run,
    )
    print("v550_release_package_rejects_tracked_private_vts: True")
    print("v550_actual_pyvts_imported_by_builder: False")
    print("v550_websocket_connected_by_builder: False")
    print("v550_network_execution_by_builder: False")
    print("v550_private_token_read_by_builder: False")
    print("v550_private_evidence_read_by_builder: False")
    print("v550_real_motion_execution_by_builder: False")
    print("v550_drc_repo_changed_by_builder: False")
    print("v550_tag_created_by_builder: False")
    print("v550_push_performed_by_builder: False")


if __name__ == "__main__":
    main()
