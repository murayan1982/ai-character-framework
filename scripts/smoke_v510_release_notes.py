"""Release note smoke for AI-Character-Framework v5.1.0."""

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


def _assert_release_notes(root: Path) -> None:
    path = root / "docs" / "release_notes_v5.1.0.md"
    _require(path.exists(), "missing docs/release_notes_v5.1.0.md")

    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "AI-Character-Framework v5.1.0 Release Notes",
        "Installable SDK / Stable Host App Integration Boundary",
        "TextChatResult",
        "ask_result",
        "VoiceOutputSession.speak",
        "CapabilityStatus",
        "FrameworkCapabilities",
        "get_capabilities",
        "FW-owned provider config",
        "close()",
        "dispose()",
        "VoiceArtifactRef",
        "Package import readiness",
        "fixed release package",
        "secret hygiene",
        ".env.example",
        "sha256=137f9f85602957b068881d8d26e34570bafa8e000c4a624fc19871b313612545",
        "Known transition baseline",
        "create_text_chat_session",
        "Not included in v5.1.0",
        "Release artifact policy",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"release notes missing phrase: {phrase}")

    forbidden_phrases = [
        "v5.1.0 is not released",
        "NOT_RELEASED",
        "real provider execution is required",
    ]
    for phrase in forbidden_phrases:
        _require(phrase not in text, f"release notes contain stale/incorrect phrase: {phrase}")

    _ok("v5.1.0 release notes are documented")


def _assert_readme_link(root: Path) -> None:
    readme = root / "README.md"
    _require(readme.exists(), "missing README.md")
    text = readme.read_text(encoding="utf-8", errors="replace")
    _require("release_notes_v5.1.0.md" in text, "README should link v5.1.0 release notes")
    _ok("README links v5.1.0 release notes")


def main() -> None:
    root = _repo_root()
    _assert_release_notes(root)
    _assert_readme_link(root)
    _ok("v5.1.0 release note cleanup is mock-safe")


if __name__ == "__main__":
    main()
