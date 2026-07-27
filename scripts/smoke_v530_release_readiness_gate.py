"""v5.3.0 release readiness gate smoke."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


DEPENDENCIES = (
    "scripts/smoke_v530_drc_public_handoff_verification.py",
    "scripts/smoke_v530_guarded_real_provider_adapter.py",
    "scripts/smoke_v530_voice_input_session_adapter_wiring.py",
    "scripts/smoke_v530_lazy_provider_adapter_fake.py",
    "scripts/smoke_v530_host_audio_source_contract.py",
    "scripts/smoke_v530_real_stt_provider_boundary_inventory.py",
    "scripts/smoke_v520_voice_input_public_contract_conformance_gate.py",
    "scripts/smoke_v520_release_readiness_gate.py",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _run_dependency(root: Path, script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        raise AssertionError(f"readiness dependency failed: {script}")
    print(f"[OK] readiness dependency passed: {script}")


def main() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    doc = _read(root / "docs" / "v530_release_readiness_gate.md")
    checklist = _read(root / "docs" / "v530_real_stt_small_commit_checklist.md")
    readme = _read(root / "README.md")

    _require(
        "v5.3.0 release readiness: ACCEPTED" in doc,
        "release readiness doc should mark accepted",
    )
    _require(
        "v5.3.0 release package/tag: READY" in doc,
        "release readiness doc should mark release package/tag ready",
    )
    _require("v5.3.0 release readiness" in checklist, "checklist missing release readiness section")
    _require("v5.3.0 release readiness gate" in readme, "README missing v5.3.0 release readiness gate")
    _ok("v5.3.0 release readiness gate doc is documented")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = (
        "speech_recognition",
        "pyaudio",
        "sounddevice",
        "whisper",
        "faster_whisper",
        "openai",
        "google.cloud",
        "boto3",
        "azure",
    )
    provider_import_hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden))
    _require(not provider_import_hits, "framework import loaded STT provider/runtime modules")
    _ok("framework import remains v5.3.0 release-readiness provider safe")

    required_public_symbols = (
        "VoiceInputRequest",
        "VoiceInputResult",
        "VoiceInputSession",
        "VoiceInputSessionInfo",
        "create_voice_input_session",
        "get_voice_input_capabilities",
        "VoiceInputAudioSourceKind",
        "VoiceInputAudioEncoding",
        "VoiceInputAudioFormat",
        "VoiceInputAudioRef",
        "VoiceInputAudioSource",
        "VoiceInputProviderAdapter",
        "VoiceInputProviderAdapterInfo",
        "FakeVoiceInputProviderAdapter",
        "GuardedRealVoiceInputProviderAdapter",
    )
    for name in required_public_symbols:
        _require(hasattr(framework, name), f"framework missing v5.3.0 public symbol: {name}")
        _require(name in getattr(framework, "__all__", ()), f"framework.__all__ missing v5.3.0 public symbol: {name}")
    _ok("framework exports v5.3.0 public voice-input contract symbols safely")

    session = framework.create_voice_input_session()
    _require(hasattr(session, "transcribe_audio_result"), "VoiceInputSession missing transcribe_audio_result")
    _require(hasattr(session, "listen_audio_result"), "VoiceInputSession missing listen_audio_result")
    _require(bool(getattr(session.capabilities, "provider_execution_allowed", False)) is False, "provider execution must not be allowed by default")

    source = framework.VoiceInputAudioSource.from_opaque_id(
        "release_readiness_capture_id",
        audio_format=framework.VoiceInputAudioFormat.wav(sample_rate_hz=16000, channel_count=1, duration_ms=1000),
        language="ja-JP",
        max_duration_ms=15000,
    )
    fake_result = session.transcribe_audio_result(
        source,
        request=framework.VoiceInputRequest(language="ja-JP", max_duration_ms=15000),
        adapter=framework.FakeVoiceInputProviderAdapter(transcript="release readiness fake transcript"),
    )
    _require(getattr(fake_result, "text", None) == "release readiness fake transcript", "fake adapter path should return typed transcript")

    guarded = framework.GuardedRealVoiceInputProviderAdapter(provider="openai", allow_provider_execution=False)
    guarded_result = session.transcribe_audio_result(
        source,
        request=framework.VoiceInputRequest(language="ja-JP", max_duration_ms=15000),
        adapter=guarded,
    )
    _require(getattr(guarded_result, "text", "") in ("", None), "guarded real adapter should remain blocked")
    _ok("v5.3.0 public voice-input runtime contract remains mock-safe")

    for dep in DEPENDENCIES:
        _run_dependency(root, dep)

    print("v530_release_readiness_gate_status: accepted")
    print("v530_public_voice_input_contract_present: True")
    print("v530_host_audio_source_contract_present: True")
    print("v530_lazy_provider_adapter_present: True")
    print("v530_voice_input_session_adapter_wiring_present: True")
    print("v530_guarded_real_provider_adapter_present: True")
    print("v530_drc_public_handoff_verification_present: True")
    print("v530_public_real_stt_execution_present: False")
    print("v530_provider_execution_executed: False")
    print("v530_microphone_accessed: False")
    print("v530_audio_handled: False")
    print("v530_drc_rt3_status: blocked-pending-real-provider-execution")
    print("v530_release_package_authorization: ready-for-release-package")
    _ok("v5.3.0 source-tree release readiness gate passed")


if __name__ == "__main__":
    main()
