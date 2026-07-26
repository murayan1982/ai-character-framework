#!/usr/bin/env python
"""Smoke check for v5.1.0 fixed release package verification.

This gate builds the local v5.1.0 fixed release zip, validates basic manifest and
zip hygiene, extracts it to a temporary host-app-like location, and imports the
public framework API from outside the repository root.

The smoke is intentionally mock-safe. It does not publish a release, create a git
tag, call provider APIs, or require provider credentials.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


VERSION = "v5.1.0"
ZIP_NAME = "ai-character-framework_v5.1.0.zip"
MANIFEST_NAME = "ai-character-framework_v5.1.0_manifest.json"

FORBIDDEN_ZIP_PARTS = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".release_build",
    ".venv",
    "venv",
    "__pycache__",
    "output",
    "tmp",
}

FORBIDDEN_ZIP_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".log",
)


class ContractFailure(AssertionError):
    """Raised when the fixed release package contract is not met."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _run(root: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    print("[RUN] " + " ".join(command))
    completed = subprocess.run(
        command,
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip())
    _require(completed.returncode == 0, f"command failed with code {completed.returncode}: {' '.join(command)}")
    return completed


def _assert_doc(root: Path) -> None:
    doc = root / "docs" / "v510_fixed_release_package_verification.md"
    _require(doc.exists(), "fixed release package verification doc missing")
    text = doc.read_text(encoding="utf-8", errors="replace")
    for phrase in [
        "fixed release package verification gate",
        "release/ai-character-framework_v5.1.0.zip",
        "release/ai-character-framework_v5.1.0_manifest.json",
        "excludes local-only artifacts",
        "imports from outside the repository root",
        "mock-safe",
    ]:
        _require(phrase in text, f"fixed release package verification doc missing phrase: {phrase}")
    print("[OK] v5.1.0 fixed release package verification doc is documented")


def _build_release_package(root: Path) -> tuple[Path, Path]:
    builder = root / "scripts" / "build_v510_fixed_release_package.py"
    _require(builder.exists(), "v5.1.0 fixed release package builder script missing")
    _run(root, [sys.executable, str(builder.relative_to(root))])

    release_dir = root / "release"
    zip_path = release_dir / ZIP_NAME
    manifest_path = release_dir / MANIFEST_NAME

    _require(zip_path.exists(), f"fixed release zip missing: {zip_path}")
    _require(zip_path.is_file(), f"fixed release zip is not a file: {zip_path}")
    _require(zip_path.stat().st_size > 0, "fixed release zip is empty")
    _require(manifest_path.exists(), f"fixed release manifest missing: {manifest_path}")
    _require(manifest_path.is_file(), f"fixed release manifest is not a file: {manifest_path}")

    print("[OK] v5.1.0 fixed release package builder produced local artifacts")
    return zip_path, manifest_path


def _assert_manifest(manifest_path: Path) -> None:
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    _require(VERSION in text, "fixed release manifest does not mention v5.1.0")
    _require(ZIP_NAME in text or "ai-character-framework_v5.1.0" in text, "fixed release manifest does not mention release package name")

    try:
        manifest = json.loads(text)
    except json.JSONDecodeError:
        manifest = None

    if isinstance(manifest, dict):
        serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
        _require("v5.1.0" in serialized, "fixed release manifest JSON missing v5.1.0 marker")

    print("[OK] v5.1.0 fixed release manifest is present and version-marked")


def _zip_names(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    _require(names, "fixed release zip has no entries")
    return names


def _assert_zip_hygiene(zip_path: Path) -> None:
    names = _zip_names(zip_path)

    normalized = [name.replace("\\", "/").strip("/") for name in names]
    _require(any(name.endswith("framework/__init__.py") or name == "framework/__init__.py" for name in normalized), "fixed release zip missing framework package")

    forbidden_hits: list[str] = []
    for name in normalized:
        parts = set(Path(name).parts)
        if parts.intersection(FORBIDDEN_ZIP_PARTS):
            forbidden_hits.append(name)
            continue
        if name.endswith(FORBIDDEN_ZIP_SUFFIXES):
            forbidden_hits.append(name)
            continue
        lower = name.lower()
        if lower.startswith("release/") or "/release/" in lower:
            forbidden_hits.append(name)
            continue
        if lower.startswith("config/tokens/") or "/config/tokens/" in lower:
            forbidden_hits.append(name)
            continue
        if lower.startswith("apply_") or "/apply_" in lower:
            forbidden_hits.append(name)
            continue
        if lower.endswith("_token.json"):
            forbidden_hits.append(name)
            continue

    _require(not forbidden_hits, "fixed release zip contains local-only artifacts: " + ", ".join(forbidden_hits[:16]))
    print("[OK] v5.1.0 fixed release zip excludes local-only artifacts")


def _find_import_root(extract_root: Path) -> Path:
    candidates: list[Path] = []
    for init_file in extract_root.rglob("framework/__init__.py"):
        candidates.append(init_file.parent.parent)

    _require(candidates, "extracted fixed release package has no framework/__init__.py")

    # Prefer the shallowest candidate. It is the PYTHONPATH root for import framework.
    candidates.sort(key=lambda path: len(path.relative_to(extract_root).parts))
    return candidates[0]


def _assert_extracted_package_imports(zip_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="fw_v510_fixed_release_verify_") as temp_dir:
        temp_root = Path(temp_dir)
        extract_root = temp_root / "extracted"
        host_cwd = temp_root / "host_app"
        extract_root.mkdir()
        host_cwd.mkdir()

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_root)

        import_root = _find_import_root(extract_root)

        child_code = r"""
import sys

forbidden = {"tts.voice_engine", "elevenlabs", "openai", "google.generativeai"}

import framework

loaded = sorted(
    name for name in sys.modules
    if name in forbidden or any(name.startswith(prefix + ".") for prefix in forbidden)
)
if loaded:
    raise SystemExit("forbidden modules loaded during fixed release package import: " + ", ".join(loaded[:16]))

required = {
    "create_text_chat_session",
    "TextChatResult",
    "CapabilityStatus",
    "FrameworkCapabilities",
    "get_capabilities",
    "create_voice_output_session",
    "VoiceOutputSession",
    "VoiceOutputSessionInfo",
    "VoiceOutputRequest",
    "VoiceArtifactRef",
    "VoiceOutputResult",
}
missing = sorted(required.difference(set(getattr(framework, "__all__", []))))
if missing:
    raise SystemExit("missing public symbols: " + ", ".join(missing))

caps = framework.get_capabilities()
if not hasattr(caps, "voice_output"):
    raise SystemExit("capability snapshot missing voice_output")

voice_session = framework.create_voice_output_session()
voice_request = framework.VoiceOutputRequest(
    text="fixed release package verification",
    requested_audio_format="wav",
)
voice_result = voice_session.speak(voice_request)
if voice_result.audio_ready:
    raise SystemExit("mock-safe fixed release package verification unexpectedly produced playable audio")
if voice_result.audio_artifact_ref is not None:
    raise SystemExit("mock-safe fixed release package verification unexpectedly exposed artifact ref")

voice_session.close()
closed_result = voice_session.speak(voice_request)
if getattr(closed_result, "request_state", None) != "failed":
    raise SystemExit("closed voice session did not return failed state")
if getattr(closed_result, "audio_ready", True):
    raise SystemExit("closed voice session unexpectedly returned playable audio")

ref = framework.VoiceArtifactRef("voice-artifact:v510-fixed-release-smoke")
if "v510-fixed-release-smoke" not in repr(ref):
    raise SystemExit("VoiceArtifactRef repr does not preserve opaque display id")

print("[OK] extracted fixed release package imports from outside repository root")
print("[OK] extracted fixed release public API exercise is provider-neutral and mock-safe")
"""

        completed = subprocess.run(
            [sys.executable, "-c", child_code],
            cwd=str(host_cwd),
            env={
                **os.environ,
                "PYTHONPATH": str(import_root),
                "PYTHONNOUSERSITE": "1",
            },
            text=True,
            capture_output=True,
            check=False,
        )

        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.stderr:
            print(completed.stderr.rstrip())

        _require(completed.returncode == 0, f"fixed release package child process failed with code {completed.returncode}")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    zip_path, manifest_path = _build_release_package(root)
    _assert_manifest(manifest_path)
    _assert_zip_hygiene(zip_path)
    _assert_extracted_package_imports(zip_path)
    print("[OK] v5.1.0 fixed release package verification is mock-safe")


if __name__ == "__main__":
    main()
