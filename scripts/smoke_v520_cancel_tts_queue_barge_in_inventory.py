"""v5.2.0 hard cancel / TTS queue / flush / barge-in inventory smoke."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


class ContractFailure(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _info(message: str) -> None:
    print(f"[INFO] {message}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _assert_inventory_doc(root: Path) -> None:
    path = root / "docs" / "v520_cancel_tts_queue_barge_in_inventory.md"
    _require(path.exists(), "missing docs/v520_cancel_tts_queue_barge_in_inventory.md")
    text = path.read_text(encoding="utf-8", errors="replace")

    required_phrases = [
        "v5.2.0 Hard Cancel / TTS Queue / Flush / Barge-in Inventory",
        "Hard cancel / TTS queue / flush / barge-in",
        "DRC RT-1",
        "InterruptScope",
        "InterruptReason",
        "InterruptRequest",
        "InterruptResult",
        "TTSQueueState",
        "OutputFlushRequest",
        "OutputFlushResult",
        "BargeInPolicy",
        "BargeInDecision",
        "RealtimeSession.interrupt",
        "RealtimeSession.cancel_current_turn",
        "RealtimeSession.flush_output",
        "RealtimeSession.set_barge_in_policy",
        "current_turn",
        "llm_stream",
        "tts_queue",
        "voice_output",
        "user_barge_in",
        "flush_output",
        "hard_cancel",
        "realtime.interrupt.requested",
        "realtime.output.flush.completed",
        "realtime.barge_in.detected",
        "Honest capability requirements",
        "Relationship to existing public contracts",
        "feat/test: add public interrupt and output control types",
    ]

    for phrase in required_phrases:
        _require(phrase in text, f"cancel/TTS/barge-in inventory missing phrase: {phrase}")

    forbidden_phrases = [
        "DRC should manipulate TTS queues directly",
        "raw audio paths may be exposed",
        "provider payloads may be exposed",
        "hard cancel is always supported",
    ]
    for phrase in forbidden_phrases:
        _require(phrase not in text, f"cancel/TTS/barge-in inventory contains forbidden phrase: {phrase}")

    _ok("v5.2.0 hard cancel / TTS queue / flush / barge-in inventory is documented")


def _assert_readme_link(root: Path) -> None:
    readme = root / "README.md"
    _require(readme.exists(), "missing README.md")
    text = readme.read_text(encoding="utf-8", errors="replace")
    _require("v520_cancel_tts_queue_barge_in_inventory.md" in text, "README should link cancel/TTS/barge-in inventory")
    _ok("README links v5.2.0 cancel/TTS/barge-in inventory")


def _assert_checklist(root: Path) -> None:
    path = root / "docs" / "v520_drc_runtime_contract_checklist.md"
    _require(path.exists(), "missing docs/v520_drc_runtime_contract_checklist.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    _require("Phase 3 - Hard cancel / TTS queue / flush / barge-in" in text, "checklist should contain phase 3")
    _require("Commit 14 - Hard cancel / TTS queue / flush / barge-in inventory" in text, "checklist should track commit 14")
    _ok("checklist tracks hard cancel / TTS queue / flush / barge-in inventory")


def _assert_framework_import_safe(root: Path) -> None:
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
    ]
    hits = sorted(name for name in loaded if any(fragment in name for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded cancel/TTS/provider modules: " + ", ".join(hits[:16]))
    _require(hasattr(framework, "create_realtime_session"), "realtime public contract should remain exported")
    _ok("framework import remains cancel/TTS/provider safe before interruption implementation")


def _assert_source_inventory(root: Path) -> None:
    candidate_dirs = [root / "framework", root / "core", root / "plugins", root / "llm", root / "stt"]
    existing = [path.relative_to(root).as_posix() for path in candidate_dirs if path.exists()]
    _info("existing source areas for future cancel/TTS/barge-in inventory: " + ", ".join(existing))
    _require((root / "framework").exists(), "framework package should exist")
    _ok("source inventory has a framework package baseline")


def main() -> None:
    root = _repo_root()
    _assert_inventory_doc(root)
    _assert_readme_link(root)
    _assert_checklist(root)
    _assert_framework_import_safe(root)
    _assert_source_inventory(root)
    _ok("v5.2.0 hard cancel / TTS queue / flush / barge-in inventory smoke is mock-safe")


if __name__ == "__main__":
    main()
