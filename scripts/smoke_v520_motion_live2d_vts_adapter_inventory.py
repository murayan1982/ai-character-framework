"""v5.2.0 motion / Live2D / VTS adapter inventory smoke."""

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
    path = root / "docs" / "v520_motion_live2d_vts_adapter_inventory.md"
    _require(path.exists(), "missing docs/v520_motion_live2d_vts_adapter_inventory.md")
    text = path.read_text(encoding="utf-8", errors="replace")

    required_phrases = [
        "v5.2.0 Motion / Live2D / VTS Adapter Inventory",
        "Public motion / Live2D / VTS adapter",
        "DRC RT-1",
        "create_motion_session",
        "MotionSession",
        "MotionSessionInfo",
        "MotionAdapterStatus",
        "MotionCapability",
        "MotionRequest",
        "MotionResult",
        "MotionEventType",
        "MotionState",
        "MotionErrorCode",
        "RealtimeSession.motion",
        "RealtimeSession.set_motion_adapter",
        "RealtimeSession.get_motion_capabilities",
        "expression",
        "emotion",
        "speaking_state",
        "idle_motion",
        "gesture",
        "look_at",
        "stop_motion",
        "reset_expression",
        "VTS token missing",
        "provider execution not allowed",
        "real adapter not implemented yet",
        "Safety rules",
        "Relationship to existing public contracts",
        "feat/test: add public motion adapter types",
    ]

    for phrase in required_phrases:
        _require(phrase in text, f"motion/Live2D/VTS inventory missing phrase: {phrase}")

    forbidden_phrases = [
        "DRC should own VTS WebSocket directly",
        "VTS tokens may be exposed",
        "raw VTS payloads may be exposed",
        "real VTS connection is required",
    ]
    for phrase in forbidden_phrases:
        _require(phrase not in text, f"motion/Live2D/VTS inventory contains forbidden phrase: {phrase}")

    _ok("v5.2.0 motion / Live2D / VTS adapter inventory is documented")


def _assert_readme_link(root: Path) -> None:
    readme = root / "README.md"
    _require(readme.exists(), "missing README.md")
    text = readme.read_text(encoding="utf-8", errors="replace")
    _require("v520_motion_live2d_vts_adapter_inventory.md" in text, "README should link motion/Live2D/VTS inventory")
    _ok("README links v5.2.0 motion / Live2D / VTS inventory")


def _assert_checklist(root: Path) -> None:
    path = root / "docs" / "v520_drc_runtime_contract_checklist.md"
    _require(path.exists(), "missing docs/v520_drc_runtime_contract_checklist.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    _require("Phase 4 - Public motion / Live2D / VTS adapter" in text, "checklist should contain phase 4")
    _require("Commit 19 - Motion / Live2D / VTS adapter inventory" in text, "checklist should track commit 19")
    _ok("checklist tracks motion / Live2D / VTS adapter inventory")


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
        "vtube",
        "vts",
        "live2d",
    ]
    hits = sorted(name for name in loaded if any(fragment in name.lower() for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded motion/VTS/provider modules: " + ", ".join(hits[:16]))
    _require(hasattr(framework, "create_realtime_session"), "realtime public contract should remain exported")
    _ok("framework import remains motion/VTS/provider safe before motion implementation")


def _assert_source_inventory(root: Path) -> None:
    candidate_dirs = [
        root / "framework",
        root / "core",
        root / "plugins",
        root / "motion",
        root / "live2d",
        root / "vts",
    ]
    existing = [path.relative_to(root).as_posix() for path in candidate_dirs if path.exists()]
    _info("existing source areas for future motion/VTS inventory: " + ", ".join(existing))
    _require((root / "framework").exists(), "framework package should exist")
    _ok("source inventory has a framework package baseline")


def main() -> None:
    root = _repo_root()
    _assert_inventory_doc(root)
    _assert_readme_link(root)
    _assert_checklist(root)
    _assert_framework_import_safe(root)
    _assert_source_inventory(root)
    _ok("v5.2.0 motion / Live2D / VTS adapter inventory smoke is mock-safe")


if __name__ == "__main__":
    main()
