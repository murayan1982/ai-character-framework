"""v5.2.0 realtime lifecycle / event contract inventory smoke."""

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
    path = root / "docs" / "v520_realtime_lifecycle_event_inventory.md"
    _require(path.exists(), "missing docs/v520_realtime_lifecycle_event_inventory.md")
    text = path.read_text(encoding="utf-8", errors="replace")

    required_phrases = [
        "v5.2.0 Realtime Lifecycle / Event Contract Inventory",
        "Unified realtime lifecycle / event contract",
        "DRC RT-1",
        "create_realtime_session",
        "RealtimeSession",
        "RealtimeSessionInfo",
        "RealtimeState",
        "RealtimeEventType",
        "RealtimeEvent",
        "RealtimeTurn",
        "RealtimeTurnResult",
        "RealtimeErrorCode",
        "idle",
        "listening",
        "transcribing",
        "thinking",
        "speaking",
        "motion",
        "interrupted",
        "failed",
        "completed",
        "closed",
        "realtime.session.created",
        "realtime.turn.started",
        "realtime.voice_input.started",
        "realtime.text_chat.completed",
        "realtime.voice_output.completed",
        "realtime.turn.interrupted",
        "realtime.session.closed",
        "Event payload rules",
        "Turn model",
        "Relationship to existing public contracts",
        "feat/test: add public realtime lifecycle event types",
    ]

    for phrase in required_phrases:
        _require(phrase in text, f"realtime lifecycle inventory missing phrase: {phrase}")

    forbidden_phrases = [
        "DRC should import realtime internals",
        "real realtime provider execution is required",
        "provider raw JSON may be exposed",
        "VTS token may be exposed",
    ]
    for phrase in forbidden_phrases:
        _require(phrase not in text, f"realtime lifecycle inventory contains forbidden phrase: {phrase}")

    _ok("v5.2.0 realtime lifecycle / event inventory is documented")


def _assert_readme_link(root: Path) -> None:
    readme = root / "README.md"
    _require(readme.exists(), "missing README.md")
    text = readme.read_text(encoding="utf-8", errors="replace")
    _require("v520_realtime_lifecycle_event_inventory.md" in text, "README should link realtime lifecycle inventory")
    _ok("README links v5.2.0 realtime lifecycle inventory")


def _assert_checklist(root: Path) -> None:
    path = root / "docs" / "v520_drc_runtime_contract_checklist.md"
    _require(path.exists(), "missing docs/v520_drc_runtime_contract_checklist.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    _require("Phase 2 - Unified realtime lifecycle / event contract" in text, "checklist should contain phase 2")
    _require("Commit 9 - Realtime lifecycle / event inventory" in text, "checklist should track commit 9")
    _ok("checklist tracks realtime lifecycle / event inventory")


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
    _require(not hits, "import framework eagerly loaded realtime/provider modules: " + ", ".join(hits[:16]))
    _require(hasattr(framework, "create_voice_input_session"), "voice-input public contract should remain exported")
    _ok("framework import remains realtime/provider safe before realtime implementation")


def _assert_source_inventory(root: Path) -> None:
    candidate_dirs = [root / "framework", root / "core", root / "plugins", root / "llm", root / "stt"]
    existing = [path.relative_to(root).as_posix() for path in candidate_dirs if path.exists()]
    _info("existing source areas for future realtime inventory: " + ", ".join(existing))
    _require((root / "framework").exists(), "framework package should exist")
    _ok("source inventory has a framework package baseline")


def main() -> None:
    root = _repo_root()
    _assert_inventory_doc(root)
    _assert_readme_link(root)
    _assert_checklist(root)
    _assert_framework_import_safe(root)
    _assert_source_inventory(root)
    _ok("v5.2.0 realtime lifecycle / event inventory smoke is mock-safe")


if __name__ == "__main__":
    main()
