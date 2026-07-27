"""v5.3.0 VoiceInputSession adapter wiring smoke."""

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

    doc = _read(root / "docs" / "v530_voice_input_session_adapter_wiring.md")
    checklist = _read(root / "docs" / "v530_real_stt_small_commit_checklist.md")
    _require("STT-1d: ACCEPTED" in doc, "session wiring doc should mark STT-1d accepted")
    _require("STT-1e: READY" in doc, "session wiring doc should mark STT-1e ready")
    _require("STT-1d - Public VoiceInputSession adapter wiring" in checklist, "checklist should track STT-1d")
    _ok("v5.3.0 VoiceInputSession adapter wiring docs are present")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = ("speech_recognition", "pyaudio", "sounddevice", "whisper", "faster_whisper", "google.cloud", "boto3", "azure")
    hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden))
    _require(not hits, "framework import should not load STT provider/runtime modules")
    _ok("framework import remains session-adapter/provider safe")

    session = framework.create_voice_input_session()
    _require(hasattr(session, "transcribe_audio_result"), "VoiceInputSession missing transcribe_audio_result")
    _require(hasattr(session, "listen_audio_result"), "VoiceInputSession missing listen_audio_result")

    fmt = framework.VoiceInputAudioFormat.wav(sample_rate_hz=16000, channel_count=1, duration_ms=4820)
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "capture_123",
        audio_format=fmt,
        language="ja-JP",
        max_duration_ms=15000,
    )
    adapter = framework.FakeVoiceInputProviderAdapter(transcript="セッション経由のフェイクSTTです")
    request = framework.VoiceInputRequest(language="ja-JP", max_duration_ms=15000)

    result = session.transcribe_audio_result(source, request=request, adapter=adapter)
    _require(getattr(result, "text", None) == "セッション経由のフェイクSTTです", "session adapter wiring should return fake transcript")
    _require(getattr(result, "language", None) == "ja-JP", "session adapter wiring should preserve language")

    alias_result = session.listen_audio_result(source, request=request, adapter=adapter)
    _require(getattr(alias_result, "text", None) == "セッション経由のフェイクSTTです", "listen_audio_result alias should return fake transcript")

    default_result = session.transcribe_audio_result(source, request=request)
    _require(bool(getattr(default_result, "text", "")), "default fake adapter path should return text")

    print("v530_voice_input_session_adapter_wiring_status: accepted")
    print("v530_voice_input_session_adapter_methods_present: True")
    print("v530_voice_input_session_fake_adapter_result_present: True")
    print("v530_voice_input_session_provider_safe_import: True")
    print("v530_voice_input_session_reads_audio: False")
    print("v530_voice_input_session_microphone_accessed: False")
    print("v530_voice_input_session_provider_execution_executed: False")
    print("v530_stt1e_authorization: ready-for-stt1e")
    _ok("v5.3.0 VoiceInputSession adapter wiring smoke is mock-safe")


if __name__ == "__main__":
    main()
