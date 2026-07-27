"""v5.3.0 lazy provider adapter + fake adapter smoke."""

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

    doc = _read(root / "docs" / "v530_lazy_provider_adapter_fake.md")
    checklist = _read(root / "docs" / "v530_real_stt_small_commit_checklist.md")
    _require("STT-1c: ACCEPTED" in doc, "adapter doc should mark STT-1c accepted")
    _require("STT-1d: READY" in doc, "adapter doc should mark STT-1d ready")
    _require("STT-1c - Lazy provider adapter protocol and fake adapter" in checklist, "checklist should track STT-1c")
    _ok("v5.3.0 lazy provider adapter docs are present")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = ("speech_recognition", "pyaudio", "sounddevice", "whisper", "faster_whisper", "google.cloud", "boto3", "azure")
    hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden))
    _require(not hits, "framework import should not load STT provider/runtime modules")
    _ok("framework import remains lazy-provider safe")

    required = (
        "VoiceInputProviderAdapter",
        "VoiceInputProviderAdapterInfo",
        "FakeVoiceInputProviderAdapter",
    )
    for name in required:
        _require(hasattr(framework, name), f"framework missing public adapter symbol: {name}")
        _require(name in getattr(framework, "__all__", ()), f"framework.__all__ missing adapter symbol: {name}")
    _ok("framework exports lazy provider adapter symbols")

    fmt = framework.VoiceInputAudioFormat.wav(sample_rate_hz=16000, channel_count=1, duration_ms=4820)
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "capture_123",
        audio_format=fmt,
        language="ja-JP",
        max_duration_ms=15000,
    )
    request = framework.VoiceInputRequest(language="ja-JP")
    adapter = framework.FakeVoiceInputProviderAdapter(
        transcript="これはフェイクSTTです",
        public_metadata={"api_key": "should-not-leak"},
    )

    _require(isinstance(adapter, framework.VoiceInputProviderAdapter), "fake adapter should satisfy adapter protocol")
    info = adapter.preflight()
    _require(isinstance(info, framework.VoiceInputProviderAdapterInfo), "preflight should return adapter info")
    _require(info.adapter_name == "fake", "fake adapter name mismatch")
    _require(info.provider == "fake", "fake provider mismatch")
    _require(info.available is True, "fake adapter should be available")
    _require(info.real_provider is False, "fake adapter must not claim real provider")
    _require(info.provider_execution_required is False, "fake adapter must not require provider execution")
    _require(info.public_metadata["api_key"] == "<redacted>", "adapter info metadata should redact secrets")
    _require("should-not-leak" not in repr(info), "adapter info repr should not leak secret-like metadata")

    result = adapter.transcribe(audio_source=source, request=request)
    _require(getattr(result, "text", None) == "これはフェイクSTTです", "fake adapter should return transcript text")
    _require(getattr(result, "language", None) == "ja-JP", "fake adapter should preserve language")
    _require(getattr(result, "duration_ms", None) in (4820, None), "fake adapter should preserve duration when supported")

    print("v530_lazy_provider_adapter_status: accepted")
    print("v530_lazy_provider_adapter_public_exports_present: True")
    print("v530_fake_adapter_transcript_result_present: True")
    print("v530_lazy_provider_adapter_provider_safe_import: True")
    print("v530_fake_adapter_reads_audio: False")
    print("v530_fake_adapter_microphone_accessed: False")
    print("v530_fake_adapter_provider_execution_executed: False")
    print("v530_stt1d_authorization: ready-for-stt1d")
    _ok("v5.3.0 lazy provider adapter smoke is mock-safe")


if __name__ == "__main__":
    main()
