"""Mock-safe package import readiness smoke for FW v5.1.0.

The smoke verifies that the public framework package can be imported from a
host-app-like working directory outside the repository root. It does not call
providers, validate credentials, publish a package, or create real artifacts.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class ContractFailure(AssertionError):
    """Raised when the package import readiness contract fails."""


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _info(message: str) -> None:
    print(f"[INFO] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _copy_package(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "venv",
    )
    shutil.copytree(src, dst, ignore=ignore)


def _provider_safe_env(package_root: Path, repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(package_root)
    env["FW_V510_REPO_ROOT"] = str(repo_root)
    env["FRAMEWORK_VOICE_OUTPUT_REAL_TTS"] = "0"
    env["FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION"] = "0"

    for key in list(env):
        upper = key.upper()
        if (
            upper.startswith("OPENAI_")
            or upper.startswith("ELEVENLABS_")
            or upper.startswith("GOOGLE_API")
            or upper.startswith("GEMINI_")
        ):
            env.pop(key, None)
    return env


CHILD_CODE = r'''
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

forbidden = {"tts.voice_engine", "elevenlabs", "openai", "google.generativeai"}
repo_root = Path(os.environ["FW_V510_REPO_ROOT"]).resolve()
cwd = Path.cwd().resolve()
assert cwd != repo_root, f"child process unexpectedly ran from repo root: {cwd}"

baseline = set(sys.modules)
import framework

loaded_after_import = sorted(
    name for name in sys.modules
    if name not in baseline and (name in forbidden or any(name.startswith(prefix + ".") for prefix in forbidden))
)
assert not loaded_after_import, "provider/internal modules loaded by package import: " + ", ".join(loaded_after_import)

expected_symbols = {
    "create_text_chat_session",
    "TextChatSessionInfo",
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
missing = sorted(expected_symbols.difference(set(getattr(framework, "__all__", ()))))
assert not missing, "missing public symbols from package import: " + ", ".join(missing)

voice_factory_sig = str(inspect.signature(framework.create_voice_output_session))
assert "project_root" in voice_factory_sig, "voice output factory signature lost project_root boundary"
assert "default_voice_profile_id" in voice_factory_sig, "voice output factory signature lost default_voice_profile_id"

text_result = framework.TextChatResult.completed(
    "package import ok",
    public_metadata={"boundary": "text_chat", "source": "package_import_readiness"},
)
assert text_result.is_completed is True, "TextChatResult.completed should be completed"
assert text_result.text == "package import ok", "TextChatResult text was not preserved"
assert "api_key" not in repr(text_result).lower(), "TextChatResult repr should be public-safe"

artifact_ref = framework.VoiceArtifactRef.from_id(
    "voice_artifact_pkg_import_001",
    audio_format="mp3",
    content_type="audio/mpeg",
)
assert str(artifact_ref) == "voice_artifact_pkg_import_001", "VoiceArtifactRef should stringify to opaque ID"
try:
    framework.VoiceArtifactRef.from_id("C:" + chr(92) + "private" + chr(92) + "audio.mp3")
except ValueError:
    pass
else:
    raise AssertionError("VoiceArtifactRef accepted a local/private path-like ID")

request = framework.VoiceOutputRequest(
    text="package import readiness voice check",
    requested_audio_format="mp3",
)
with framework.create_voice_output_session() as voice_session:
    result = voice_session.speak(request)
    assert hasattr(result, "request_state"), "VoiceOutputResult lost request_state"
    assert result.audio_ready is False, "mock-safe package readiness must not create real audio"
    assert result.has_audio_handoff is False, "non-playable mock-safe result must not expose handoff"
assert voice_session.is_closed is True, "VoiceOutputSession context manager should close on exit"

loaded_after_exercise = sorted(
    name for name in sys.modules
    if name not in baseline and (name in forbidden or any(name.startswith(prefix + ".") for prefix in forbidden))
)
assert not loaded_after_exercise, "provider/internal modules loaded by mock-safe package exercise: " + ", ".join(loaded_after_exercise)

print(json.dumps({
    "cwd": str(cwd),
    "repo_root": str(repo_root),
    "voice_factory_signature": voice_factory_sig,
    "voice_request_state": result.request_state,
    "public_symbol_count": len(getattr(framework, "__all__", ())),
}, ensure_ascii=False, sort_keys=True))
'''


def _assert_doc(root: Path) -> None:
    doc_path = root / "docs" / "v510_package_import_readiness.md"
    _require(doc_path.exists(), "package import readiness doc is missing")
    text = doc_path.read_text(encoding="utf-8", errors="replace")
    for phrase in (
        "import framework works from outside the repository root",
        "VoiceOutputSession.speak(...) is usable through the package-like import path",
        "does not publish a wheel",
        "DRC should be able to depend on FW as a package-like SDK",
    ):
        _require(phrase in text, f"package import readiness doc missing phrase: {phrase}")
    _ok("v5.1.0 package import readiness doc is documented")


def _copy_sdk_source_tree(root: Path, package_root: Path) -> None:
    """Copy FW-owned importable source packages to a package-like tree.

    v5.1.0 still has transition absolute imports such as ``llm.*`` and
    ``config.*`` from the public framework facade. This smoke keeps the
    repository root and host app CWD out of PYTHONPATH, while copying the
    FW-owned root-level Python source directories together like a
    source-distribution-style tree.
    """

    excluded_dirs = {
        ".git",
        ".github",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "docs",
        "examples",
        "release",
        "scripts",
        "tests",
        "tmp",
    }

    copied = []
    for child in sorted(root.iterdir()):
        if child.name in excluded_dirs:
            continue
        if child.name.lower() in {"venv", ".venv"}:
            continue
        if child.name.startswith("."):
            continue

        if child.is_dir():
            has_python_source = any(
                path.suffix == ".py" and "__pycache__" not in path.parts
                for path in child.rglob("*.py")
            )
            if not has_python_source:
                continue

            shutil.copytree(
                child,
                package_root / child.name,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".ruff_cache",
                ),
            )
            copied.append(child.name)
            continue

        if child.is_file() and child.suffix == ".py" and not child.name.startswith("apply_"):
            shutil.copy2(child, package_root / child.name)
            copied.append(child.name)

    _require((package_root / "framework").exists(), "framework package was not copied")
    _require((package_root / "llm").exists(), "llm package was not copied for source-distribution-like import")
    _require((package_root / "config").exists(), "config package was not copied for source-distribution-like import")
    _require(not (package_root / "venv").exists(), "local venv directory should not be copied")
    _require(not (package_root / ".venv").exists(), "local .venv directory should not be copied")
    print("[INFO] copied source packages for package-like import: " + ", ".join(copied))


def _run_child_package_import(root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="fw_v510_package_import_") as temp_dir:
        temp_root = Path(temp_dir)
        package_root = temp_root / "sdk_package"
        host_cwd = temp_root / "host_app"
        package_root.mkdir()
        host_cwd.mkdir()

        _copy_sdk_source_tree(root, package_root)

        child_code = r"""
import sys

forbidden = {"tts.voice_engine", "elevenlabs", "openai", "google.generativeai"}

import framework

loaded = sorted(
    name for name in sys.modules
    if name in forbidden or any(name.startswith(prefix + ".") for prefix in forbidden)
)
if loaded:
    raise SystemExit("forbidden modules loaded during package import: " + ", ".join(loaded[:16]))

required = {
    "create_text_chat_session",
    "TextChatResult",
    "get_capabilities",
    "create_voice_output_session",
    "VoiceOutputSession",
    "VoiceOutputRequest",
    "VoiceOutputResult",
    "VoiceArtifactRef",
}
missing = sorted(required.difference(set(getattr(framework, "__all__", []))))
if missing:
    raise SystemExit("missing public symbols: " + ", ".join(missing))

caps = framework.get_capabilities()
if not hasattr(caps, "voice_output"):
    raise SystemExit("capability snapshot missing voice_output")

session = framework.create_voice_output_session()
request = framework.VoiceOutputRequest(text="package import readiness", requested_audio_format="wav")
result = session.speak(request)
if result.audio_ready:
    raise SystemExit("mock-safe package readiness unexpectedly produced playable audio")
if result.audio_artifact_ref is not None:
    raise SystemExit("mock-safe package readiness unexpectedly exposed artifact ref")

ref = framework.VoiceArtifactRef("voice-artifact:v510-package-import-smoke")
if "v510-package-import-smoke" not in repr(ref):
    raise SystemExit("VoiceArtifactRef repr does not preserve opaque display id")

print("[OK] framework package imports from outside repository root")
print("[OK] package-like public API exercise is provider-neutral and mock-safe")
"""

        completed = subprocess.run(
            [sys.executable, "-c", child_code],
            cwd=str(host_cwd),
            env={
                **os.environ,
                "PYTHONPATH": str(package_root),
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

        _require(completed.returncode == 0, f"package import child process failed with code {completed.returncode}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    _require((root / "framework").exists(), "run this smoke from the FW repository root")
    _assert_doc(root)
    _run_child_package_import(root)
    _ok("v5.1.0 package import readiness is mock-safe")


if __name__ == "__main__":
    main()
