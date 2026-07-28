"""v5.4.0 candidate real STT provider execution requirements smoke."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def main() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    req = _read(root / "docs" / "v540_real_stt_provider_execution_requirements.md")
    checklist = _read(root / "docs" / "v540_real_stt_provider_execution_small_commit_checklist.md")
    readme = _read(root / "README.md")

    _require("requirements definition: ACCEPTED" in req, "requirements doc should mark requirements definition accepted")
    _require("implementation: NOT_STARTED" in req, "requirements doc should keep implementation not started")
    _require("private real-provider acceptance: NOT_STARTED" in req, "requirements doc should keep private real-provider acceptance not started")
    _require("v5.4.0 Candidate Real STT Provider Execution" in req, "requirements doc missing v5.4.0 candidate title")
    _require("DRC private staged WAV" in req, "requirements doc missing DRC target path")
    _require("FW-REQ-1" in req and "FW-REQ-11" in req, "requirements doc missing FW requirement range")
    _require("REQ-0 - Requirements definition" in checklist, "checklist missing REQ-0")
    _require("REQ-6 - DRC released-FW adoption gate" in checklist, "checklist missing DRC adoption gate")
    _require("v5.4.0 candidate development: Real STT Provider Execution" in readme, "README missing v5.4.0 candidate note")
    _ok("v5.4.0 real STT provider execution requirements docs are present")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = (
        "speech_recognition", "pyaudio", "sounddevice", "whisper", "faster_whisper",
        "openai", "google.cloud", "boto3", "azure",
    )
    provider_import_hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden))
    _require(not provider_import_hits, "framework import loaded STT provider/runtime modules")
    _ok("framework import remains provider safe during requirements definition")

    required_v530_symbols = (
        "VoiceInputRequest", "VoiceInputResult", "VoiceInputSession",
        "VoiceInputAudioSource", "VoiceInputAudioFormat", "VoiceInputProviderAdapter",
        "VoiceInputProviderAdapterInfo", "FakeVoiceInputProviderAdapter",
        "GuardedRealVoiceInputProviderAdapter", "create_voice_input_session",
    )
    for name in required_v530_symbols:
        _require(hasattr(framework, name), f"framework missing required v5.3.0 baseline symbol: {name}")

    guarded = framework.GuardedRealVoiceInputProviderAdapter(provider="openai", allow_provider_execution=True, credentials_available=True)
    info = guarded.preflight()
    _require("real_stt_not_implemented" in repr(info), "requirements definition should not implement real provider execution")
    _require(getattr(info, "available", True) is False, "guarded real adapter should remain unavailable in requirements definition")
    _ok("v5.3.0 baseline remains unchanged: real STT execution not implemented")

    print("v540_real_stt_provider_execution_requirements_status: accepted")
    print("v540_candidate_version_selected_for_requirements: True")
    print("v540_implementation_started: False")
    print("v540_private_real_provider_acceptance_started: False")
    print("v540_public_real_stt_execution_present: False")
    print("v540_provider_execution_executed: False")
    print("v540_microphone_accessed: False")
    print("v540_audio_handled: False")
    print("v540_drc_repo_changed: False")
    print("v540_release_package_created: False")
    print("v540_tag_created: False")
    print("v540_req1_authorization: ready-for-provider-execution-configuration")
    _ok("v5.4.0 real STT provider execution requirements smoke is documentation-only")


if __name__ == "__main__":
    main()
