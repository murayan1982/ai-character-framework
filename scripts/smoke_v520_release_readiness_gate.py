"""v5.2.0 source-tree release readiness gate."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


class ContractFailure(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _assert_doc(root: Path) -> None:
    path = root / "docs" / "v520_release_readiness_gate.md"
    _require(path.exists(), "missing docs/v520_release_readiness_gate.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Release Readiness Gate",
        "Public voice-input / STT session",
        "Unified realtime lifecycle / event contract",
        "Hard cancel / TTS queue / flush / barge-in",
        "Public motion / Live2D / VTS adapter",
        "smoke_v520_voice_input_public_contract_conformance_gate.py",
        "smoke_v520_realtime_public_contract_conformance_gate.py",
        "smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
        "smoke_v520_motion_public_contract_conformance_gate.py",
        "check_release_package.py",
        "Honest runtime status",
        "real STT is not implemented",
        "real hard cancel is not implemented",
        "real Live2D / VTS adapter runtime is not implemented",
        "fixed v5.2.0 release package builder",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"release readiness doc missing phrase: {phrase}")
    _ok("v5.2.0 release readiness gate doc is documented")


def _assert_readme_and_checklist(root: Path) -> None:
    readme = root / "README.md"
    checklist = root / "docs" / "v520_drc_runtime_contract_checklist.md"
    notes = root / "docs" / "v510_host_app_sdk_readiness_notes.md"

    _require(readme.exists(), "missing README.md")
    _require(checklist.exists(), "missing docs/v520_drc_runtime_contract_checklist.md")
    _require(notes.exists(), "missing docs/v510_host_app_sdk_readiness_notes.md")

    readme_text = readme.read_text(encoding="utf-8", errors="replace")
    checklist_text = checklist.read_text(encoding="utf-8", errors="replace")
    notes_text = notes.read_text(encoding="utf-8", errors="replace")

    _require("v520_release_readiness_gate.md" in readme_text, "README should link v5.2.0 release readiness gate")
    _require("Commit 24 - v5.2.0 release readiness gate" in checklist_text, "checklist should track commit 24")
    _require("v5.2.0 release readiness gate checkpoint" in notes_text, "readiness notes should track v5.2.0 release readiness gate")
    _ok("README/checklist/readiness notes track v5.2.0 release readiness gate")


def _assert_framework_public_exports(root: Path):
    sys.path.insert(0, str(root))
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    after = set(sys.modules)
    loaded = after - before

    forbidden_fragments = [
        "pyaudio",
        "sounddevice",
        "speech_recognition",
        "whisper",
        "faster_whisper",
        "elevenlabs",
        "websocket",
        "websockets",
        "vtube",
        "vts",
        "live2d",
    ]
    hits = sorted(name for name in loaded if any(fragment in name.lower() for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded provider/runtime modules: " + ", ".join(hits[:16]))

    required_symbols = [
        # Voice input / STT
        "VoiceInputRequest",
        "VoiceInputResult",
        "create_voice_input_session",
        "VoiceInputSession",
        "VoiceInputSessionInfo",
        "get_voice_input_capabilities",
        # Realtime
        "RealtimeState",
        "RealtimeEventType",
        "RealtimeEvent",
        "RealtimeTurn",
        "RealtimeTurnResult",
        "create_realtime_session",
        "RealtimeSession",
        "RealtimeSessionInfo",
        # Interrupt / output control
        "InterruptRequest",
        "InterruptResult",
        "TTSQueueState",
        "OutputFlushRequest",
        "OutputFlushResult",
        "BargeInPolicy",
        "BargeInDecision",
        # Motion
        "MotionCapability",
        "MotionRequest",
        "MotionResult",
        "create_motion_session",
        "MotionSession",
        "MotionSessionInfo",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required_symbols:
        _require(hasattr(framework, name), f"framework missing v5.2.0 public symbol: {name}")
        _require(name in public, f"framework.__all__ missing v5.2.0 public symbol: {name}")

    _ok("framework exports v5.2.0 public runtime contract symbols safely")
    return framework


def _assert_honest_default_runtime_flags(framework) -> None:
    voice = framework.create_voice_input_session()
    _require(not voice.info.real_stt_enabled, "voice-input should not enable real STT by default")
    _require(not voice.capabilities.supports_real_stt, "voice-input should not claim real STT support yet")

    realtime = framework.create_realtime_session()
    _require(not realtime.info.real_runtime_enabled, "realtime should not enable real runtime by default")
    _require(realtime.info.supports_interrupt, "realtime should expose public interrupt control")
    _require(not realtime.info.hard_cancel_supported, "realtime should not claim real hard cancel")
    _require(not realtime.info.tts_queue_flush_supported, "realtime should not claim real TTS queue flush")

    motion = framework.create_motion_session()
    _require(not motion.info.real_adapter_enabled, "motion should not enable real adapter by default")
    _require(not motion.info.real_adapter_supported, "motion should not claim real adapter support")
    _require(motion.info.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "motion mock adapter should be available")

    _ok("v5.2.0 default runtime flags are honest and mock-safe")


def _run_script(root: Path, relative: str) -> None:
    path = root / relative
    _require(path.exists(), f"missing required readiness script: {relative}")
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    _require(completed.returncode == 0, f"readiness script failed: {relative}")
    _ok(f"readiness dependency passed: {relative}")


def _assert_required_gates_pass(root: Path) -> None:
    required_scripts = [
        "scripts/smoke_v520_voice_input_public_contract_conformance_gate.py",
        "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
        "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
        "scripts/smoke_v520_motion_public_contract_conformance_gate.py",
        "scripts/check_release_package.py",
    ]
    for relative in required_scripts:
        _run_script(root, relative)
    _ok("all required v5.2.0 release readiness dependencies passed")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_readme_and_checklist(root)
    framework = _assert_framework_public_exports(root)
    _assert_honest_default_runtime_flags(framework)
    _assert_required_gates_pass(root)
    _ok("v5.2.0 source-tree release readiness gate passed")


if __name__ == "__main__":
    main()
