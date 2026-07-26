"""v5.2.0 voice-input / STT inventory smoke."""

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
    path = root / "docs" / "v520_voice_input_stt_inventory.md"
    _require(path.exists(), "missing docs/v520_voice_input_stt_inventory.md")
    text = path.read_text(encoding="utf-8", errors="replace")

    required_phrases = [
        "v5.2.0 Voice Input / STT Internal Inventory",
        "DRC RT-1",
        "create_voice_input_session",
        "VoiceInputSession",
        "VoiceInputSessionInfo",
        "VoiceInputRequest",
        "VoiceInputResult",
        "VoiceInputEvent",
        "VoiceInputState",
        "VoiceInputErrorCode",
        "mock-safe construction",
        "no eager provider SDK import",
        "provider-neutral missing credential behavior",
        "guarded real STT execution",
        "close()",
        "dispose()",
        "is_closed",
        "voice_input.started",
        "voice_input.completed",
        "voice_input.failed",
        "DRC must not depend on",
        "feat/test: add public voice input result and request types",
    ]

    for phrase in required_phrases:
        _require(phrase in text, f"voice input inventory missing phrase: {phrase}")

    forbidden_phrases = [
        "DRC should import stt internals",
        "real STT execution is required by default",
        "provider payloads may be exposed",
    ]
    for phrase in forbidden_phrases:
        _require(phrase not in text, f"voice input inventory contains forbidden phrase: {phrase}")

    _ok("v5.2.0 voice-input / STT inventory is documented")


def _assert_readme_link(root: Path) -> None:
    readme = root / "README.md"
    _require(readme.exists(), "missing README.md")
    text = readme.read_text(encoding="utf-8", errors="replace")
    _require("v520_voice_input_stt_inventory.md" in text, "README should link voice-input inventory")
    _ok("README links v5.2.0 voice-input inventory")


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
    ]
    hits = sorted(name for name in loaded if any(fragment in name for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded voice/STT provider modules: " + ", ".join(hits[:16]))
    _require(hasattr(framework, "__all__"), "framework.__all__ should exist before public voice-input additions")
    _ok("framework import remains voice/STT provider safe before public voice-input implementation")


def _assert_source_inventory(root: Path) -> None:
    candidate_dirs = [root / "stt", root / "framework", root / "core", root / "plugins"]
    existing = [path.relative_to(root).as_posix() for path in candidate_dirs if path.exists()]
    _info("existing source areas for future voice-input inventory: " + ", ".join(existing))
    _require((root / "framework").exists(), "framework package should exist")
    _ok("source inventory has a framework package baseline")


def main() -> None:
    root = _repo_root()
    _assert_inventory_doc(root)
    _assert_readme_link(root)
    _assert_framework_import_safe(root)
    _assert_source_inventory(root)
    _ok("v5.2.0 voice-input / STT inventory smoke is mock-safe")


if __name__ == "__main__":
    main()
