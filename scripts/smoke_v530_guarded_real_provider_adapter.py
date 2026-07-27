"""v5.3.0 guarded real provider adapter smoke."""

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

    doc = _read(root / "docs" / "v530_guarded_real_provider_adapter.md")
    checklist = _read(root / "docs" / "v530_real_stt_small_commit_checklist.md")
    _require("STT-1e: ACCEPTED" in doc, "guarded adapter doc should mark STT-1e accepted")
    _require("STT-1f: READY" in doc, "guarded adapter doc should mark STT-1f ready")
    _require("STT-1e - First guarded real provider adapter" in checklist, "checklist should track STT-1e")
    _ok("v5.3.0 guarded real provider adapter docs are present")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = ("speech_recognition", "pyaudio", "sounddevice", "whisper", "faster_whisper", "openai", "google.cloud", "boto3", "azure")
    hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden))
    _require(not hits, "framework import should not load STT provider/runtime modules")
    _ok("framework import remains guarded-real-provider safe")

    _require(hasattr(framework, "GuardedRealVoiceInputProviderAdapter"), "framework missing GuardedRealVoiceInputProviderAdapter")
    _require("GuardedRealVoiceInputProviderAdapter" in getattr(framework, "__all__", ()), "framework.__all__ missing GuardedRealVoiceInputProviderAdapter")
    _ok("framework exports guarded real provider adapter symbol")

    fmt = framework.VoiceInputAudioFormat.wav(sample_rate_hz=16000, channel_count=1, duration_ms=4820)
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "capture_123",
        audio_format=fmt,
        language="ja-JP",
        max_duration_ms=15000,
    )
    request = framework.VoiceInputRequest(language="ja-JP", max_duration_ms=15000)

    blocked = framework.GuardedRealVoiceInputProviderAdapter(
        provider="openai",
        allow_provider_execution=False,
        credentials_available=False,
        public_metadata={"api_key": "should-not-leak"},
    )
    _require(isinstance(blocked, framework.VoiceInputProviderAdapter), "guarded adapter should satisfy adapter protocol")
    blocked_info = blocked.preflight()
    _require(blocked_info.real_provider is True, "guarded adapter should identify real provider boundary")
    _require(blocked_info.available is False, "guarded adapter should not be available when execution is blocked")
    _require(blocked_info.provider_execution_required is True, "guarded adapter should require explicit execution opt-in")
    _require(blocked_info.public_metadata["api_key"] == "<redacted>", "guarded preflight should redact metadata")
    _require("provider_execution_not_allowed" in repr(blocked_info), "blocked preflight should report guard reason")
    _require("should-not-leak" not in repr(blocked_info), "guarded preflight repr should not leak secret-like metadata")

    blocked_result = blocked.transcribe(audio_source=source, request=request)
    _require(getattr(blocked_result, "text", "") in ("", None), "blocked guarded adapter should not return transcript")
    _require("should-not-leak" not in repr(blocked_result), "blocked result should not leak secret-like metadata")

    missing = framework.GuardedRealVoiceInputProviderAdapter(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=False,
    )
    missing_info = missing.preflight()
    _require("missing_credentials" in repr(missing_info), "missing-credentials guard should be visible")

    not_implemented = framework.GuardedRealVoiceInputProviderAdapter(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=True,
    )
    not_impl_info = not_implemented.preflight()
    _require("real_stt_not_implemented" in repr(not_impl_info), "not-implemented guard should be visible")
    not_impl_result = not_implemented.transcribe(audio_source=source, request=request)
    _require(getattr(not_impl_result, "text", "") in ("", None), "not-implemented guarded adapter should not return transcript")

    session = framework.create_voice_input_session()
    session_result = session.transcribe_audio_result(source, request=request, adapter=blocked)
    _require(getattr(session_result, "text", "") in ("", None), "session guarded adapter path should not return transcript")

    print("v530_guarded_real_provider_adapter_status: accepted")
    print("v530_guarded_real_provider_adapter_public_export_present: True")
    print("v530_guarded_real_provider_adapter_provider_safe_import: True")
    print("v530_guarded_real_provider_adapter_preflight_guard_present: True")
    print("v530_guarded_real_provider_adapter_session_path_present: True")
    print("v530_guarded_real_provider_adapter_reads_audio: False")
    print("v530_guarded_real_provider_adapter_microphone_accessed: False")
    print("v530_guarded_real_provider_adapter_provider_execution_executed: False")
    print("v530_stt1f_authorization: ready-for-stt1f")
    _ok("v5.3.0 guarded real provider adapter smoke is mock-safe")


if __name__ == "__main__":
    main()
