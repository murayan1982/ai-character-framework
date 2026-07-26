"""Mock-safe capability snapshot smoke for FW v5.1.0."""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path


FORBIDDEN_MODULE_FRAGMENTS = (
    "tts.voice_engine",
    "elevenlabs",
    "openai",
    "vts",
    "voice_input",
)

FORBIDDEN_PUBLIC_FRAGMENTS = (
    "api_key",
    "API_KEY",
    "secret",
    "ElevenLabs",
    "OpenAI",
    "voice_id",
    "model_id",
    "C:\\",
    "/home/",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_importable() -> Path:
    root = _repo_root()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _info(message: str) -> None:
    print(f"[INFO] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _assert_doc(root: Path) -> None:
    doc_path = root / "docs" / "v510_capability_snapshot_contract.md"
    _require(doc_path.exists(), "missing docs/v510_capability_snapshot_contract.md")
    text = _read_text(doc_path)
    for phrase in (
        "get_capabilities",
        "CapabilityStatus",
        "FrameworkCapabilities",
        "Guarded does not mean implemented",
        "Configured does not mean successful",
        "public_boundary_missing",
        "provider-neutral",
    ):
        _require(phrase in text, f"capability snapshot doc missing phrase: {phrase}")
    _ok("capability snapshot contract doc is documented")


def _assert_no_forbidden_imports() -> None:
    loaded = sorted(sys.modules)
    forbidden = [name for name in loaded if any(fragment in name.lower() for fragment in FORBIDDEN_MODULE_FRAGMENTS)]
    _require(not forbidden, f"capability import loaded forbidden provider/internal modules: {forbidden}")
    _ok("capability snapshot import stays provider/internal safe")


def _assert_public_exports(framework: object) -> None:
    exports = set(getattr(framework, "__all__", ()))
    for name in ("get_capabilities", "CapabilityStatus", "FrameworkCapabilities"):
        _require(name in exports, f"{name} is not exported via framework.__all__")
        _require(hasattr(framework, name), f"framework.{name} is missing")
    _require(dataclasses.is_dataclass(framework.CapabilityStatus), "CapabilityStatus should be a dataclass")
    _require(dataclasses.is_dataclass(framework.FrameworkCapabilities), "FrameworkCapabilities should be a dataclass")
    _ok("capability snapshot public API is exported")


def _assert_default_snapshot(framework: object) -> None:
    snapshot = framework.get_capabilities()
    _require(isinstance(snapshot, framework.FrameworkCapabilities), "get_capabilities should return FrameworkCapabilities")
    _require(snapshot.schema_version == "v5.1.capabilities", "unexpected capability schema version")

    text_chat = snapshot.text_chat
    _require(isinstance(text_chat, framework.CapabilityStatus), "text_chat should be CapabilityStatus")
    _require(text_chat.supported is True, "text_chat should be supported")
    _require(text_chat.configured is True, "text_chat should be configured")
    _require(text_chat.available is True, "text_chat should be available")
    _require(text_chat.status == "available", "text_chat status should be available")

    voice_output = snapshot.voice_output
    _require(voice_output.supported is True, "voice_output boundary should be supported")
    _require(voice_output.available is False, "voice_output should not claim availability by default")
    _require(voice_output.reason_code in {"real_tts_disabled", "provider_not_configured"}, "voice_output default reason should be public-safe")
    _require(voice_output.public_metadata.get("provider_details_exposed") == "false", "voice_output should not expose provider details")

    for name in ("voice_input", "realtime", "motion"):
        capability = getattr(snapshot, name)
        _require(capability.supported is False, f"{name} should not be supported yet")
        _require(capability.configured is False, f"{name} should not be configured")
        _require(capability.available is False, f"{name} should not be available")
        _require(capability.reason_code == "public_boundary_missing", f"{name} should report public_boundary_missing")

    public_repr = repr(snapshot.to_public_dict())
    leaked = [fragment for fragment in FORBIDDEN_PUBLIC_FRAGMENTS if fragment in public_repr]
    _require(not leaked, f"capability snapshot may expose private/provider details: {leaked}")
    _ok("default capability snapshot is provider-neutral and mock-safe")


def _assert_guarded_voice_output_snapshot(framework: object) -> None:
    original = {key: os.environ.get(key) for key in (
        "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
        "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
    )}
    try:
        os.environ["FRAMEWORK_VOICE_OUTPUT_REAL_TTS"] = "1"
        os.environ["FRAMEWORK_VOICE_OUTPUT_PROVIDER"] = "configured-provider"
        os.environ.pop("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION", None)
        snapshot = framework.get_capabilities()
        voice_output = snapshot.voice_output
        _require(voice_output.supported is True, "guarded voice_output should be supported")
        _require(voice_output.configured is True, "guarded voice_output should be configured")
        _require(voice_output.available is False, "guarded voice_output should not be available")
        _require(voice_output.blocked is True, "guarded voice_output should be blocked")
        _require(voice_output.status == "blocked", "guarded voice_output status should be blocked")
        _require(voice_output.reason_code == "provider_execution_guarded", "guarded voice_output reason should be provider_execution_guarded")
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    _ok("guarded voice output capability is not treated as available")


def main() -> None:
    root = _ensure_repo_importable()
    import framework  # noqa: PLC0415

    _assert_no_forbidden_imports()
    _assert_doc(root)
    _assert_public_exports(framework)
    _assert_default_snapshot(framework)
    _assert_guarded_voice_output_snapshot(framework)
    _assert_no_forbidden_imports()
    _ok("v5.1.0 capability snapshot is mock-safe")


if __name__ == "__main__":
    main()
