"""DRC-driven v5.2.0 realtime roadmap smoke."""

from __future__ import annotations

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


def _assert_roadmap(root: Path) -> None:
    path = root / "docs" / "roadmap_feature_v5.2.0.md"
    _require(path.exists(), "missing docs/roadmap_feature_v5.2.0.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "Public Voice Input / Realtime Runtime Boundary Foundation",
        "DRC-side RT-1 requirement",
        "Public voice-input / STT session",
        "Unified realtime lifecycle / event contract",
        "Hard cancel / TTS queue / flush / barge-in",
        "Public motion / Live2D / VTS adapter",
        "Release a new FW version",
        "Return to DRC and re-evaluate RT-1",
        "DRC must not",
        "import FW internals",
        "create_voice_input_session",
        "VoiceInputSession",
        "RealtimeSession",
        "RealtimeEvent",
        "InterruptRequest",
        "BargeInPolicy",
        "create_motion_session",
        "MotionSession",
        "VTube Studio adapter boundary",
        "v5.2.0",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"roadmap missing phrase: {phrase}")
    forbidden_phrases = [
        "DRC should implement provider-specific STT",
        "DRC should own VTube Studio WebSocket",
        "real provider execution required",
    ]
    for phrase in forbidden_phrases:
        _require(phrase not in text, f"roadmap contains forbidden phrase: {phrase}")
    _ok("v5.2.0 DRC-driven realtime roadmap is documented")


def _assert_checklist(root: Path) -> None:
    path = root / "docs" / "v520_drc_runtime_contract_checklist.md"
    _require(path.exists(), "missing docs/v520_drc_runtime_contract_checklist.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "Phase 0 - Planning and inventory",
        "Phase 1 - Public voice-input / STT session",
        "Phase 2 - Unified realtime lifecycle / event contract",
        "Phase 3 - Hard cancel / TTS queue / flush / barge-in",
        "Phase 4 - Public motion / Live2D / VTS adapter",
        "Phase 5 - Release readiness",
        "Phase 6 - Return to DRC",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"checklist missing phrase: {phrase}")
    _ok("v5.2.0 DRC runtime contract checklist is documented")


def _assert_readme(root: Path) -> None:
    path = root / "README.md"
    _require(path.exists(), "missing README.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    _require("roadmap_feature_v5.2.0.md" in text, "README should link v5.2.0 roadmap")
    _require("DRC RT-1" in text, "README should mention DRC RT-1 driver")
    _ok("README links v5.2.0 DRC-driven runtime roadmap")


def main() -> None:
    root = _repo_root()
    _assert_roadmap(root)
    _assert_checklist(root)
    _assert_readme(root)
    _ok("v5.2.0 DRC-driven runtime roadmap smoke is mock-safe")


if __name__ == "__main__":
    main()
