"""Verify the fixed AI-Character-Framework v5.2.0 release package."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

VERSION = "5.2.0"
PACKAGE_FILENAME = f"ai-character-framework_v{VERSION}.zip"
SHA256_FILENAME = f"ai-character-framework_v{VERSION}.sha256.txt"
MANIFEST_ARCNAME = f"RELEASE_MANIFEST_v{VERSION}.json"
NORMALIZED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)

REQUIRED_ARCNAMES = {
    "README.md",
    "framework/__init__.py",
    "framework/voice_input.py",
    "framework/voice_input_session.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "framework/output_control.py",
    "framework/motion.py",
    "framework/motion_session.py",
    "scripts/smoke_v520_release_readiness_gate.py",
    "scripts/build_v520_release_package.py",
    "scripts/verify_v520_release_package.py",
    "docs/v520_release_readiness_gate.md",
    "docs/v520_fixed_release_package_builder.md",
    "docs/v520_fixed_release_package_verification.md",
    "docs/v520_voice_input_public_types.md",
    "docs/v520_realtime_public_contract_conformance_gate.md",
    "docs/v520_interrupt_output_control_public_contract_conformance_gate.md",
    "docs/v520_motion_public_contract_conformance_gate.md",
}

FORBIDDEN_ARCNAME_FRAGMENTS = {
    "/.git/",
    ".git/",
    "/.venv/",
    ".venv/",
    "/venv/",
    "operator_evidence",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".release_build",
}

FORBIDDEN_BASENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.json",
    "token.json",
}


class VerificationFailure(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    _require(MANIFEST_ARCNAME in archive.namelist(), f"missing {MANIFEST_ARCNAME}")
    return json.loads(archive.read(MANIFEST_ARCNAME).decode("utf-8"))


def _assert_sha256_sidecar(package_path: Path) -> None:
    sha_path = package_path.with_name(SHA256_FILENAME)
    _require(sha_path.exists(), f"missing SHA-256 sidecar: {sha_path}")

    text = sha_path.read_text(encoding="utf-8").strip()
    expected = _sha256_file(package_path)
    _require(expected in text, "SHA-256 sidecar does not contain package digest")
    _require(package_path.name in text, "SHA-256 sidecar does not reference package filename")
    _ok("SHA-256 sidecar matches package")


def _assert_zip_structure(package_path: Path) -> tuple[zipfile.ZipFile, list[str]]:
    _require(package_path.exists(), f"missing package: {package_path}")
    _require(package_path.name == PACKAGE_FILENAME, f"unexpected package filename: {package_path.name}")

    archive = zipfile.ZipFile(package_path, "r")
    names = archive.namelist()
    _require(len(names) == len(set(names)), "zip entries should be unique")
    _require(MANIFEST_ARCNAME in names, f"zip should contain {MANIFEST_ARCNAME}")

    # The builder writes source files in sorted order, then appends the generated
    # release manifest last. The manifest cannot be part of the sorted source-file
    # list because its content depends on that list.
    source_names = [name for name in names if name != MANIFEST_ARCNAME]
    _require(source_names == sorted(source_names), "zip source entries should be sorted")
    _require(names[-1] == MANIFEST_ARCNAME, f"{MANIFEST_ARCNAME} should be the final generated entry")

    for info in archive.infolist():
        _require(info.date_time == NORMALIZED_ZIP_DATETIME, f"zip timestamp is not normalized: {info.filename}")
        _require(not info.is_dir(), f"zip should not contain explicit directory entry: {info.filename}")
        arc = info.filename
        lower = arc.lower()
        _require(not arc.startswith("/") and ".." not in Path(arc).parts, f"unsafe arcname: {arc}")
        for fragment in FORBIDDEN_ARCNAME_FRAGMENTS:
            _require(fragment not in lower, f"forbidden path fragment in package: {arc}")
        _require(Path(arc).name not in FORBIDDEN_BASENAMES, f"forbidden basename in package: {arc}")
        _require(not Path(arc).name.startswith("apply_"), f"patch apply script leaked into package: {arc}")
        _require(not lower.endswith(".pyc"), f"pyc leaked into package: {arc}")
        _require(not lower.endswith(".zip"), f"nested zip leaked into package: {arc}")

    _ok("zip structure is deterministic and release-safe")
    return archive, names


def _assert_manifest(archive: zipfile.ZipFile, names: list[str]) -> None:
    manifest = _read_manifest(archive)

    _require(manifest.get("package") == "ai-character-framework", "manifest package mismatch")
    _require(manifest.get("version") == VERSION, "manifest version mismatch")
    _require(manifest.get("builder") == "scripts/build_v520_release_package.py", "manifest builder mismatch")
    _require(manifest.get("readiness_gate") == "scripts/smoke_v520_release_readiness_gate.py", "manifest readiness gate mismatch")
    _require(manifest.get("deterministic_zip") is True, "manifest should mark deterministic_zip true")
    _require(tuple(manifest.get("normalized_zip_datetime", ())) == NORMALIZED_ZIP_DATETIME, "manifest normalized datetime mismatch")

    files = manifest.get("files")
    _require(isinstance(files, list), "manifest files should be a list")
    manifest_paths = [entry["path"] for entry in files]
    zip_without_manifest = [name for name in names if name != MANIFEST_ARCNAME]
    _require(manifest_paths == zip_without_manifest, "manifest file order should match zip entries excluding manifest")
    _require(manifest.get("file_count") == len(files), "manifest file_count mismatch")

    zip_names = set(names)
    for required in REQUIRED_ARCNAMES:
        _require(required in zip_names, f"required release file missing: {required}")

    for entry in files:
        path = entry["path"]
        data = archive.read(path)
        _require(entry["bytes"] == len(data), f"manifest byte count mismatch: {path}")
        _require(entry["sha256"] == _sha256_bytes(data), f"manifest sha256 mismatch: {path}")

    _ok("release manifest matches package contents")


def verify_release_package(package_path: Path) -> None:
    _assert_sha256_sidecar(package_path)
    archive, names = _assert_zip_structure(package_path)
    try:
        _assert_manifest(archive, names)
    finally:
        archive.close()
    _ok("v5.2.0 fixed release package verification passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the fixed AI-Character-Framework v5.2.0 release package.")
    parser.add_argument(
        "--package",
        type=Path,
        default=Path("release") / PACKAGE_FILENAME,
        help="Path to release zip. Defaults to release/ai-character-framework_v5.2.0.zip",
    )
    args = parser.parse_args(argv)

    verify_release_package(args.package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
