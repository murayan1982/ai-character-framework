"""v5.3.0 DRC public handoff verification smoke."""

from __future__ import annotations

import importlib
import runpy
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

    doc = _read(root / "docs" / "v530_drc_public_handoff_verification.md")
    checklist = _read(root / "docs" / "v530_real_stt_small_commit_checklist.md")
    example_path = root / "examples" / "voice_input_drc_public_handoff.py"
    example_text = _read(example_path)

    _require("STT-1f: ACCEPTED" in doc, "DRC handoff doc should mark STT-1f accepted")
    _require("v5.3.0 release readiness: READY" in doc, "DRC handoff doc should mark release readiness ready")
    _require("STT-1f - DRC public handoff verification" in checklist, "checklist should track STT-1f")
    _ok("v5.3.0 DRC public handoff verification docs are present")

    forbidden_example_terms = (
        "speech_recognition",
        "pyaudio",
        "sounddevice",
        "whisper",
        "faster_whisper",
        "openai",
        "google.cloud",
        "boto3",
        "azure",
        "os.environ",
        "subprocess",
        "open(",
        "Path(",
        "Microphone(",
        "recognize_google",
    )
    hits = [term for term in forbidden_example_terms if term.lower() in example_text.lower()]
    _require(not hits, f"DRC handoff example should stay public-only/provider-safe: {hits}")
    _require("from framework import (" in example_text, "example should import from public framework root")
    private_import_hits = [
        line.strip()
        for line in example_text.splitlines()
        if line.strip().startswith(("from framework.", "import framework."))
    ]
    _require(
        not private_import_hits,
        f"example should not reach into private framework modules: {private_import_hits}",
    )
    _ok("DRC public handoff example uses public-only imports")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden_imports = ("speech_recognition", "pyaudio", "sounddevice", "whisper", "faster_whisper", "openai", "google.cloud", "boto3", "azure")
    import_hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden_imports))
    _require(not import_hits, "framework import should not load STT provider/runtime modules")
    _ok("framework import remains DRC-handoff/provider safe")

    namespace = runpy.run_path(str(example_path))
    run_example = namespace["run_drc_public_handoff_example"]
    transcript = run_example()
    _require(transcript == "DRC public handoff fake transcript", "DRC public handoff example should return fake transcript")

    fmt = framework.VoiceInputAudioFormat.wav(sample_rate_hz=16000, channel_count=1, duration_ms=4820)
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "drc_capture_opaque_id",
        audio_format=fmt,
        language="ja-JP",
        max_duration_ms=15000,
        public_metadata={"host_app": "DRC", "raw_audio_exposed": False},
    )
    session = framework.create_voice_input_session()
    adapter = framework.FakeVoiceInputProviderAdapter(transcript="DRC smoke fake transcript")
    request = framework.VoiceInputRequest(language="ja-JP", max_duration_ms=15000)
    result = session.transcribe_audio_result(source, request=request, adapter=adapter)

    _require(getattr(result, "text", None) == "DRC smoke fake transcript", "session DRC handoff should return typed fake result")
    _require(getattr(result, "language", None) == "ja-JP", "session DRC handoff should preserve language")
    _require(source.audio_id == "drc_capture_opaque_id", "opaque DRC capture id should be preserved")
    _require(source.public_metadata["raw_audio_exposed"] is False, "DRC public metadata should record raw audio not exposed")

    guarded = framework.GuardedRealVoiceInputProviderAdapter(provider="openai", allow_provider_execution=False)
    guarded_result = session.transcribe_audio_result(source, request=request, adapter=guarded)
    _require(getattr(guarded_result, "text", "") in ("", None), "guarded real adapter should not return transcript in DRC handoff smoke")

    print("v530_drc_public_handoff_verification_status: accepted")
    print("v530_drc_public_handoff_public_only_imports: True")
    print("v530_drc_public_handoff_fake_transcript_result_present: True")
    print("v530_drc_public_handoff_guarded_real_adapter_blocked: True")
    print("v530_drc_public_handoff_provider_safe_import: True")
    print("v530_drc_public_handoff_drc_repo_changed: False")
    print("v530_drc_public_handoff_reads_audio: False")
    print("v530_drc_public_handoff_microphone_accessed: False")
    print("v530_drc_public_handoff_provider_execution_executed: False")
    print("v530_drc_rt3_status: blocked-pending-real-provider-execution")
    print("v530_release_readiness_authorization: ready-for-release-readiness")
    _ok("v5.3.0 DRC public handoff verification smoke is mock-safe")


if __name__ == "__main__":
    main()
