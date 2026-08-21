"""Provider-free adversarial smoke checks for the v6.0.0 package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "6.0.0"
FORBIDDEN_MODULES = frozenset(
    {"elevenlabs", "openai", "pyaudio", "pyvts", "sounddevice", "websocket", "websockets"}
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _changed_files() -> set[str]:
    commands = (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    paths: set[str] = set()
    for arguments in commands:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        paths.update(line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip())
    paths.discard(".vscode/settings.json")
    return paths


def _safe_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in tuple(environment):
        folded = key.casefold()
        if any(word in folded for word in ("api_key", "apikey", "credential", "password", "secret", "token")):
            environment.pop(key, None)
    environment["AI_CHARACTER_FRAMEWORK_REAL_RUNTIME_ENABLED"] = "0"
    environment["AI_CHARACTER_FRAMEWORK_ALLOW_PROVIDER_EXECUTION"] = "0"
    environment["AI_CHARACTER_FRAMEWORK_ALLOW_DEVICE_EXECUTION"] = "0"
    return environment


def _isolated_import(extracted: Path) -> None:
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(extracted)!r}); "
        "import framework; "
        f"assert framework.__version__ == {EXPECTED_VERSION!r}; "
        "assert len(framework.__all__) == 127; "
        "print('package_import_ok')"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=extracted,
        env=_safe_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    _require(completed.returncode == 0, "isolated package import failed")
    _require("package_import_ok" in completed.stdout, "package import marker missing")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run v6.0.0 package smoke checks")
    parser.add_argument("--candidate", action="store_true", help="include exact changed candidate files")
    arguments = parser.parse_args()
    before_modules = set(sys.modules)
    builder = _load("scripts/build_v600_release_package.py", "fwrt6_v600_builder")
    checker = _load("scripts/check_v600_release_readiness.py", "fwrt6_v600_checker")
    extras = _changed_files() if arguments.candidate else set()

    _require(
        builder.private_artifact_hits(
            {
                ".env",
                ".env.local",
                "config/tokens/vts_token.json",
                "operator_evidence/run.json",
                "private/audio/input.wav",
                "output/real_runtime_operator_evidence.json",
            }
        ),
        "private artifact probes were not rejected",
    )
    _require(not builder.private_artifact_hits({".env.example", "docs/public_facade.md"}), "public paths were rejected")
    for unsafe in ("../secret", "/absolute/path", "C:/private/file"):
        try:
            builder.normalize_member(unsafe)
        except RuntimeError:
            pass
        else:
            raise AssertionError("unsafe ZIP member was accepted")

    with tempfile.TemporaryDirectory(prefix="acf_v600_smoke_") as temporary:
        temp = Path(temporary)
        first = temp / "first.zip"
        second = temp / "second.zip"
        first_hash, first_count = builder.build_package(first, root=ROOT, additional_files=extras)
        second_hash, second_count = builder.build_package(second, root=ROOT, additional_files=extras)
        _require(first_count == second_count, "deterministic file count differs")
        _require(first_hash == second_hash, "deterministic SHA-256 differs")
        _require(first.read_bytes() == second.read_bytes(), "deterministic ZIP bytes differ")
        expected = builder.package_files(ROOT, additional_files=extras)
        checker.validate_archive(first, expected_members=expected)
        checker.validate_sidecar(first)

        extracted = temp / "extracted"
        extracted.mkdir()
        with zipfile.ZipFile(first) as archive:
            archive.extractall(extracted)
        _isolated_import(extracted)

        duplicate = temp / "duplicate.zip"
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr("README.md", b"first")
            archive.writestr("README.md", b"second")
        try:
            checker.validate_archive(duplicate)
        except AssertionError:
            pass
        else:
            raise AssertionError("duplicate ZIP entry was accepted")

        private_zip = temp / "private.zip"
        with zipfile.ZipFile(private_zip, "w") as archive:
            archive.writestr("README.md", b"public")
            archive.writestr("config/tokens/vts_token.json", b"not-a-real-token")
        try:
            checker.validate_archive(private_zip)
        except AssertionError:
            pass
        else:
            raise AssertionError("private ZIP member was accepted")

    loaded = set(sys.modules) - before_modules
    _require(loaded.isdisjoint(FORBIDDEN_MODULES), "provider/device module imported by package smoke")
    print("FW-RT6-14c deterministic package smoke: PASS")
    print(f"exact package membership: {first_count} files / PASS")
    print("deterministic rebuild: byte-identical / PASS")
    print("duplicate entry rejection: PASS")
    print("private artifact rejection: PASS")
    print("unsafe member rejection: PASS")
    print("package-import smoke: PASS / framework 6.0.0 / 127 exports")
    print("provider/network/microphone/playback/VTS execution: False")
    print("private artifact contents read: False")
    print("tag/push/GitHub Release execution: False")


if __name__ == "__main__":
    main()
