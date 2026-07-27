"""v5.3.0 host-audio source contract smoke."""

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

    doc = _read(root / "docs" / "v530_host_audio_source_contract.md")
    checklist = _read(root / "docs" / "v530_real_stt_small_commit_checklist.md")
    _require("STT-1b: ACCEPTED" in doc, "host-audio doc should mark STT-1b accepted")
    _require("STT-1c: READY" in doc, "host-audio doc should mark STT-1c ready")
    _require("STT-1b - Provider-neutral host-audio source contract" in checklist, "checklist should track STT-1b")
    _ok("v5.3.0 host-audio source contract docs are present")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = ("speech_recognition", "pyaudio", "sounddevice", "whisper", "faster_whisper", "google.cloud", "boto3", "azure")
    hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden))
    _require(not hits, "framework import should not load STT provider/runtime modules")
    _ok("framework import remains host-audio/provider safe")

    required = (
        "VoiceInputAudioSourceKind",
        "VoiceInputAudioEncoding",
        "VoiceInputAudioFormat",
        "VoiceInputAudioRef",
        "VoiceInputAudioSource",
    )
    for name in required:
        _require(hasattr(framework, name), f"framework missing public host-audio symbol: {name}")
        _require(name in getattr(framework, "__all__", ()), f"framework.__all__ missing host-audio symbol: {name}")
    _ok("framework exports public host-audio source symbols")

    fmt = framework.VoiceInputAudioFormat.wav(
        sample_rate_hz=16000,
        channel_count=1,
        duration_ms=4820,
        api_key="should-not-leak",
    )
    _require(fmt.encoding == framework.VoiceInputAudioEncoding.WAV, "wav helper should set encoding")
    _require(fmt.mime_type == "audio/wav", "wav helper should set mime type")
    _require(fmt.public_metadata["api_key"] == "<redacted>", "audio format metadata should redact secrets")
    _require("should-not-leak" not in repr(fmt), "audio format repr should not leak secret-like metadata")

    ref = framework.VoiceInputAudioRef.opaque_id(
        "capture_123",
        audio_format=fmt,
        public_metadata={"token": "should-not-leak"},
    )
    _require(ref.source_kind == framework.VoiceInputAudioSourceKind.OPAQUE_ID, "opaque ref kind mismatch")
    _require(ref.audio_id == "capture_123", "opaque ref should preserve audio id")
    _require(ref.value == "capture_123", "opaque ref should preserve value")
    _require(ref.public_metadata["token"] == "<redacted>", "audio ref metadata should redact secrets")
    _require("should-not-leak" not in repr(ref), "audio ref repr should not leak secret-like metadata")

    source = framework.VoiceInputAudioSource.from_opaque_id(
        "capture_123",
        audio_format=fmt,
        language="ja-JP",
        max_duration_ms=15000,
        public_metadata={"credential": "should-not-leak"},
    )
    _require(source.source_kind == framework.VoiceInputAudioSourceKind.OPAQUE_ID, "source kind mismatch")
    _require(source.audio_id == "capture_123", "source should expose audio id")
    _require(source.language == "ja-JP", "source should preserve language")
    _require(source.max_duration_ms == 15000, "source should preserve max duration")
    _require(source.public_metadata["credential"] == "<redacted>", "audio source metadata should redact secrets")
    _require("should-not-leak" not in repr(source), "audio source repr should not leak secret-like metadata")

    file_source = framework.VoiceInputAudioSource.from_file_path(
        "private/path/not/read.wav",
        audio_format=fmt,
        language="ja-JP",
    )
    _require(file_source.source_kind == framework.VoiceInputAudioSourceKind.FILE_PATH, "file source kind mismatch")
    _require(file_source.ref.value == "private/path/not/read.wav", "file source should preserve path as data only")

    try:
        framework.VoiceInputAudioFormat(sample_rate_hz=0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid sample rate should fail")

    try:
        framework.VoiceInputAudioSource.from_opaque_id("", max_duration_ms=15000)
    except ValueError:
        pass
    else:
        raise AssertionError("empty opaque id should fail")

    try:
        framework.VoiceInputAudioSource.from_opaque_id("capture_123", max_duration_ms=0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid max duration should fail")

    print("v530_host_audio_source_contract_status: accepted")
    print("v530_host_audio_source_public_exports_present: True")
    print("v530_host_audio_source_provider_safe_import: True")
    print("v530_host_audio_source_reads_audio: False")
    print("v530_host_audio_source_microphone_accessed: False")
    print("v530_host_audio_source_provider_execution_executed: False")
    print("v530_stt1c_authorization: ready-for-stt1c")
    _ok("v5.3.0 host-audio source contract smoke is mock-safe")


if __name__ == "__main__":
    main()
