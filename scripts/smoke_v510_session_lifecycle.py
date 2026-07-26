"""Mock-safe session lifecycle / close contract smoke for FW v5.1.0."""

from __future__ import annotations

import sys
from pathlib import Path


FORBIDDEN_IMPORT_FRAGMENTS = (
    "elevenlabs",
    "tts.voice_engine",
    "voice_engine",
)


class ContractFailure(AssertionError):
    pass


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_importable() -> Path:
    root = _repo_root()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root


def _assert_import_safe() -> None:
    loaded = set(sys.modules)
    forbidden = [name for name in loaded if any(fragment in name for fragment in FORBIDDEN_IMPORT_FRAGMENTS)]
    _require(not forbidden, "session lifecycle imported forbidden provider/internal modules: " + ", ".join(sorted(forbidden)))
    _ok("session lifecycle import stays provider/internal safe")


def _assert_doc(root: Path) -> None:
    doc_path = root / "docs" / "v510_session_lifecycle_contract.md"
    _require(doc_path.exists(), "missing docs/v510_session_lifecycle_contract.md")
    text = doc_path.read_text(encoding="utf-8", errors="replace")
    for phrase in (
        "close()",
        "dispose()",
        "context manager",
        "is_closed",
        "session_closed",
        "close() is idempotent",
    ):
        _require(phrase in text, f"session lifecycle doc missing phrase: {phrase}")
    _ok("session lifecycle contract doc is documented")


def _assert_common_lifecycle(session: object, label: str) -> None:
    for attr in ("close", "dispose", "__enter__", "__exit__", "is_closed"):
        _require(hasattr(session, attr), f"{label} missing lifecycle attribute: {attr}")
    _require(session.is_closed is False, f"{label} should start open")
    session.close()
    session.close()
    _require(session.is_closed is True, f"{label} close() should be idempotent and mark closed")
    session.dispose()
    _require(session.is_closed is True, f"{label} dispose() should preserve closed state")
    _ok(f"{label} lifecycle methods are idempotent")


def _get_text_chat_session_class(framework: object) -> type:
    """Return TextChatSession class without constructing a provider-backed session."""

    candidate = getattr(framework, "TextChatSession", None)
    if candidate is not None:
        return candidate

    facade_module = sys.modules.get("framework.facade")
    candidate = getattr(facade_module, "TextChatSession", None) if facade_module is not None else None
    _require(candidate is not None, "TextChatSession class should be available after framework import")
    return candidate


def _make_text_chat_session_without_provider(framework: object) -> object:
    """Create a lifecycle-only TextChatSession instance without provider setup."""

    session_cls = _get_text_chat_session_class(framework)
    session = object.__new__(session_cls)
    if hasattr(session, "_fw_public_closed"):
        session._fw_public_closed = False
    return session


def _assert_text_chat_lifecycle(framework: object) -> None:
    session = _make_text_chat_session_without_provider(framework)
    _assert_common_lifecycle(session, "TextChatSession")

    result = session.ask_result("hello after close")
    _require(isinstance(result, framework.TextChatResult), "closed ask_result should return TextChatResult")
    _require(result.outcome == "failed", "closed ask_result should fail")
    _require(result.public_error_code == "session_closed", "closed ask_result should use session_closed")
    _require(result.retryable is False, "closed ask_result should not be retryable")
    _require("closed" in (result.safe_message or "").lower(), "closed ask_result should expose safe closed message")
    _ok("TextChatSession closed ask_result returns provider-neutral session_closed")

    context_session = _make_text_chat_session_without_provider(framework)
    with context_session as entered_session:
        _require(entered_session is context_session, "TextChatSession __enter__ should return itself")
    _require(context_session.is_closed, "TextChatSession context manager should close on exit")
    _ok("TextChatSession context manager closes on exit")


def _assert_voice_output_lifecycle(framework: object) -> None:
    session = framework.create_voice_output_session()
    _assert_common_lifecycle(session, "VoiceOutputSession")

    request = framework.VoiceOutputRequest(
        text="hello after close",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="v510_session_lifecycle",
        language_code="ja",
    )
    result = session.speak(request)
    _require(result.request_state in {"failed", "unavailable", "skipped"}, "closed speak should be non-playable")
    _require(result.audio_ready is False, "closed speak must not be audio_ready")
    _require(result.audio_url is None, "closed speak must not expose audio_url")
    _require(result.audio_artifact_ref is None, "closed speak must not expose audio_artifact_ref")
    _require(result.has_audio_handoff is False, "closed speak must not expose audio handoff")
    metadata = getattr(result, "public_metadata", {}) or {}
    _require(metadata.get("public_error_code") == "session_closed", "closed speak should expose session_closed public error code")
    _ok("VoiceOutputSession closed speak returns provider-neutral non-playable result")

    with framework.create_voice_output_session() as context_session:
        _require(context_session.is_closed is False, "VoiceOutputSession context should enter open")
    _require(context_session.is_closed is True, "VoiceOutputSession context manager should close on exit")
    _ok("VoiceOutputSession context manager closes on exit")


def main() -> None:
    root = _ensure_repo_importable()
    import framework  # noqa: PLC0415

    _assert_import_safe()
    _assert_doc(root)
    _assert_text_chat_lifecycle(framework)
    _assert_voice_output_lifecycle(framework)
    _assert_import_safe()
    _ok("v5.1.0 session lifecycle contract is mock-safe")


if __name__ == "__main__":
    main()
