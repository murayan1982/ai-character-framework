"""Mock-safe capability snapshot smoke for FW v5.1 compatibility and v6 detail."""

from __future__ import annotations

import dataclasses
import inspect
import os
import sys
from pathlib import Path


FORBIDDEN_MODULE_FRAGMENTS = (
    "tts.voice_engine",
    "elevenlabs",
    "openai",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
)
FORBIDDEN_PUBLIC_FRAGMENTS = (
    "api_key",
    "API_KEY",
    "secret",
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _assert_doc(root: Path) -> None:
    text = _read_text(root / "docs" / "v510_capability_snapshot_contract.md")
    for phrase in (
        "get_capabilities",
        "CapabilityStatus",
        "FrameworkCapabilities",
        "Guarded does not mean implemented",
        "v5.1.capabilities",
        "v6.realtime_capabilities",
        "mock_realtime_available",
        "public_boundary_missing",
    ):
        _require(phrase in text, f"capability snapshot doc missing phrase: {phrase}")
    _ok("capability snapshot compatibility contract is documented")


def _assert_no_forbidden_imports() -> None:
    loaded = sorted(sys.modules)
    forbidden = [
        name
        for name in loaded
        if any(fragment in name.lower() for fragment in FORBIDDEN_MODULE_FRAGMENTS)
    ]
    _require(
        not forbidden,
        f"capability import loaded forbidden provider/runtime modules: {forbidden}",
    )
    _ok("capability snapshot import stays provider/runtime safe")


def _assert_public_exports(framework: object) -> None:
    exports = set(getattr(framework, "__all__", ()))
    for name in ("get_capabilities", "CapabilityStatus", "FrameworkCapabilities"):
        _require(name in exports, f"{name} is not exported via framework.__all__")
        _require(hasattr(framework, name), f"framework.{name} is missing")
    _require(dataclasses.is_dataclass(framework.CapabilityStatus), "CapabilityStatus should be a dataclass")
    _require(dataclasses.is_dataclass(framework.FrameworkCapabilities), "FrameworkCapabilities should be a dataclass")
    signature = inspect.signature(framework.get_capabilities)
    _require(
        tuple(signature.parameters) == ("project_root", "real_tts_enabled"),
        "get_capabilities parameter compatibility drift",
    )
    _require(
        all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in signature.parameters.values()
        ),
        "get_capabilities should remain keyword-only",
    )
    _ok("capability snapshot public API and signature are preserved")


def _assert_default_snapshot(framework: object) -> None:
    snapshot = framework.get_capabilities()
    _require(isinstance(snapshot, framework.FrameworkCapabilities), "get_capabilities should return FrameworkCapabilities")
    _require(snapshot.schema_version == "v5.1.capabilities", "unexpected compatibility schema version")

    _require(snapshot.text_chat.status == "available", "text chat should remain available")
    _require(snapshot.voice_output.supported is True, "voice output boundary should be supported")
    _require(snapshot.voice_output.available is False, "voice output real runtime should not be available by default")

    for name, reason in (
        ("voice_input", "mock_voice_input_available"),
        ("realtime", "mock_realtime_available"),
        ("motion", "mock_motion_available"),
    ):
        capability = getattr(snapshot, name)
        _require(capability.supported is True, f"{name} public boundary should be supported")
        _require(capability.configured is True, f"{name} mock runtime should be configured")
        _require(capability.available is True, f"{name} mock runtime should be available")
        _require(capability.status == "fallback", f"{name} should identify fallback runtime")
        _require(capability.reason_code == reason, f"{name} truthful reason drift")

    detailed = snapshot.realtime_snapshot
    _require(isinstance(detailed, framework.RealtimeCapabilitySnapshot), "detailed snapshot should be attached")
    _require(detailed.schema_version == "v6.realtime_capabilities", "detailed schema drift")
    _require(detailed.snapshot_scope is framework.CapabilitySnapshotScope.GLOBAL, "snapshot should be global")
    _require(detailed.session_id is None, "global snapshot should not have a session ID")
    _require(detailed.snapshot_generation == 1, "global snapshot generation drift")
    _require(detailed.text_generation.runtime.fake_runtime is True, "text fake runtime should be explicit")
    _require(detailed.voice_input.runtime.fake_runtime is True, "voice input fake runtime should be explicit")
    _require(detailed.motion.runtime.fake_runtime is True, "motion fake runtime should be explicit")
    _require(detailed.voice_output.runtime.usable is False, "voice output should not overclaim usability")
    _require(detailed.hard_cancel_supported is False, "provider hard cancel overclaim")
    _require(detailed.tts_queue_flush_supported is False, "TTS queue flush overclaim")

    public_repr = repr(snapshot.to_public_dict())
    leaked = [fragment for fragment in FORBIDDEN_PUBLIC_FRAGMENTS if fragment in public_repr]
    _require(not leaked, f"capability snapshot may expose private/provider details: {leaked}")
    _ok("default compatibility and detailed snapshots are truthful")


def _assert_guarded_voice_output_snapshot(framework: object) -> None:
    keys = (
        "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
        "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
    )
    original = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["FRAMEWORK_VOICE_OUTPUT_REAL_TTS"] = "1"
        os.environ["FRAMEWORK_VOICE_OUTPUT_PROVIDER"] = "configured-provider"
        os.environ.pop("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION", None)
        snapshot = framework.get_capabilities()
        voice_output = snapshot.voice_output
        _require(voice_output.configured is True, "guarded voice output should be configured")
        _require(voice_output.available is False, "guarded voice output should not be available")
        _require(voice_output.blocked is True, "guarded voice output should be blocked")
        _require(voice_output.reason_code == "provider_execution_guarded", "guard reason drift")
        detailed = snapshot.realtime_snapshot.voice_output.runtime
        _require(detailed.configured is True, "detailed voice output config drift")
        _require(detailed.guarded is True, "detailed voice output guard drift")
        _require(detailed.runtime_available is False, "guard must not imply runtime availability")
        _require(detailed.real_runtime is False, "guard must not imply selected real runtime")
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    _ok("guarded voice output is not treated as runtime success")


def main() -> None:
    root = _ensure_repo_importable()
    import framework  # noqa: PLC0415

    _assert_no_forbidden_imports()
    _assert_doc(root)
    _assert_public_exports(framework)
    _assert_default_snapshot(framework)
    _assert_guarded_voice_output_snapshot(framework)
    _assert_no_forbidden_imports()
    _ok("v5.1 capability compatibility and v6 detailed aggregation passed")


if __name__ == "__main__":
    main()
