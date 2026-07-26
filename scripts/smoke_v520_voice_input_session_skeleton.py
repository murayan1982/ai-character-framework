"""v5.2.0 public voice-input session skeleton smoke."""

from __future__ import annotations

import importlib
import inspect
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
    path = root / "docs" / "v520_voice_input_session_skeleton.md"
    _require(path.exists(), "missing docs/v520_voice_input_session_skeleton.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Public Voice Input Session Skeleton",
        "create_voice_input_session",
        "VoiceInputSession",
        "VoiceInputSessionInfo",
        "listen_result",
        "text_fallback_result",
        "close()",
        "dispose()",
        "context manager support",
        "real_stt_disabled",
        "real_stt_not_implemented",
        "voice_input.started",
        "voice_input.unavailable",
        "voice_input.closed",
        "Import safety",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"voice-input session skeleton doc missing phrase: {phrase}")
    _ok("v5.2.0 public voice-input session skeleton doc is documented")


def _assert_import_safe(root: Path):
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
    _ok("public voice-input session import stays provider/internal safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "create_voice_input_session",
        "VoiceInputSession",
        "VoiceInputSessionInfo",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")

    sig = inspect.signature(framework.create_voice_input_session)
    _require(all(param.kind is inspect.Parameter.KEYWORD_ONLY for param in sig.parameters.values()), "create_voice_input_session should be keyword-only")
    _ok("framework exports public voice-input session symbols")


def _assert_session_contract(framework) -> None:
    events = []

    session = framework.create_voice_input_session(language="ja-JP", public_metadata={"token": "secret"})
    _require(isinstance(session.info, framework.VoiceInputSessionInfo), "session.info should be VoiceInputSessionInfo")
    _require(session.info.session_type == "voice_input", "session.info session_type mismatch")
    _require(session.info.language == "ja-JP", "session.info language mismatch")
    _require(session.info.public_metadata["token"] == "<redacted>", "session info should redact secret-like metadata")
    _require(not session.is_closed, "new VoiceInputSession should be open")

    session.on_event(events.append)
    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "default listen_result should be unavailable")
    _require(result.public_error_code == framework.VoiceInputErrorCode.UNAVAILABLE, "unavailable error code mismatch")
    _require(result.public_metadata["reason"] == "real_stt_disabled", "default unavailable reason mismatch")
    _require(any(event["type"] == "voice_input.started" for event in events), "listen_result should emit started event")
    _require(any(event["type"] == "voice_input.unavailable" for event in events), "listen_result should emit unavailable event")

    fallback = session.text_fallback_result("hello", public_metadata={"api_key": "secret"})
    _require(fallback.outcome == framework.VoiceInputOutcome.COMPLETED, "text fallback should complete")
    _require(fallback.text == "hello", "text fallback text mismatch")
    _require(fallback.public_metadata["api_key"] == "<redacted>", "text fallback metadata should redact secret-like keys")

    session.close()
    session.dispose()
    _require(session.is_closed, "VoiceInputSession should be closed after close/dispose")
    closed = session.listen_result()
    _require(closed.outcome == framework.VoiceInputOutcome.CLOSED, "closed session should return closed result")
    _require(closed.public_error_code == framework.VoiceInputErrorCode.SESSION_CLOSED, "closed error code mismatch")
    _ok("VoiceInputSession skeleton lifecycle and result contract are mock-safe")


def _assert_real_stt_guarded_path(framework) -> None:
    session = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "guarded real STT skeleton should be unavailable")
    _require(result.public_metadata["reason"] == "real_stt_not_implemented", "guarded real STT skeleton reason mismatch")
    _require(result.public_metadata["provider_status"] == "real_stt_not_implemented", "guarded real STT provider_status mismatch")
    _require("should-not-leak" not in repr(session.info), "session info should not leak credential values")
    _require("should-not-leak" not in repr(result), "result should not leak credential values")
    _ok("VoiceInputSession real STT placeholder remains provider-neutral")


def _assert_context_manager(framework) -> None:
    with framework.create_voice_input_session() as session:
        _require(not session.is_closed, "VoiceInputSession should be open inside context")
    _require(session.is_closed, "VoiceInputSession context manager should close on exit")
    _ok("VoiceInputSession context manager closes on exit")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_session_contract(framework)
    _assert_real_stt_guarded_path(framework)
    _assert_context_manager(framework)
    _ok("v5.2.0 public voice-input session skeleton is mock-safe")


if __name__ == "__main__":
    main()
