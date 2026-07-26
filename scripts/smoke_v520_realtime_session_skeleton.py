"""v5.2.0 public realtime session skeleton smoke."""

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
    path = root / "docs" / "v520_realtime_session_skeleton.md"
    _require(path.exists(), "missing docs/v520_realtime_session_skeleton.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Public Realtime Session Skeleton",
        "create_realtime_session",
        "RealtimeSession",
        "RealtimeSessionInfo",
        "run_turn",
        "emit_created",
        "close()",
        "dispose()",
        "context manager support",
        "realtime.turn.started",
        "realtime.voice_input.started",
        "realtime.text_chat.completed",
        "realtime.voice_output.completed",
        "realtime.turn.completed",
        "Import safety",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"realtime session skeleton doc missing phrase: {phrase}")
    _ok("v5.2.0 public realtime session skeleton doc is documented")


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
        "websocket",
        "websockets",
    ]
    hits = sorted(name for name in loaded if any(fragment in name for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded realtime/provider modules: " + ", ".join(hits[:16]))
    _ok("public realtime session import stays provider/internal safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "create_realtime_session",
        "RealtimeSession",
        "RealtimeSessionInfo",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")

    sig = inspect.signature(framework.create_realtime_session)
    _require(sig.parameters, "create_realtime_session should expose explicit parameters")
    _require(all(param.kind is inspect.Parameter.KEYWORD_ONLY for param in sig.parameters.values()), "create_realtime_session should be keyword-only")
    _ok("framework exports public realtime session symbols")


def _assert_session_info(framework) -> None:
    session = framework.create_realtime_session(public_metadata={"token": "should-not-leak"})
    _require(isinstance(session.info, framework.RealtimeSessionInfo), "session.info should be RealtimeSessionInfo")
    _require(session.info.session_type == "realtime", "RealtimeSessionInfo session_type mismatch")
    _require(session.info.state == framework.RealtimeState.IDLE, "new realtime session should start idle")
    _require(session.info.public_metadata["token"] == "<redacted>", "RealtimeSessionInfo should redact secret-like metadata")
    _require("should-not-leak" not in repr(session.info), "RealtimeSessionInfo repr should not leak secret-like metadata")
    _require(not session.is_closed, "new realtime session should be open")
    _ok("RealtimeSessionInfo is provider-neutral and secret-safe")


def _assert_event_flow(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)

    created = session.emit_created()
    _require(created.type == framework.RealtimeEventType.SESSION_CREATED, "emit_created event type mismatch")
    _require(created.state == framework.RealtimeState.IDLE, "emit_created state mismatch")

    result = session.run_turn(input_text="hello", public_metadata={"api_key": "should-not-leak"})
    _require(result.outcome == framework.RealtimeState.COMPLETED, "run_turn should complete in mock skeleton")
    _require(result.is_completed, "run_turn result should be completed")
    _require(result.is_terminal, "run_turn result should be terminal")
    _require(result.input_text == "hello", "run_turn should preserve input_text")
    _require(result.public_metadata["mock_runtime"], "run_turn should mark mock runtime")
    _require(result.public_metadata["api_key"] == "<redacted>", "run_turn metadata should redact secret-like keys")
    _require("should-not-leak" not in repr(result), "run_turn result repr should not leak secret-like metadata")
    _require(session.state == framework.RealtimeState.IDLE, "session should return to idle after completed mock turn")

    event_types = [event.type for event in events]
    expected_order = [
        framework.RealtimeEventType.SESSION_CREATED,
        framework.RealtimeEventType.TURN_STARTED,
        framework.RealtimeEventType.VOICE_INPUT_STARTED,
        framework.RealtimeEventType.VOICE_INPUT_COMPLETED,
        framework.RealtimeEventType.TEXT_CHAT_STARTED,
        framework.RealtimeEventType.TEXT_CHAT_COMPLETED,
        framework.RealtimeEventType.VOICE_OUTPUT_STARTED,
        framework.RealtimeEventType.VOICE_OUTPUT_COMPLETED,
        framework.RealtimeEventType.TURN_COMPLETED,
    ]
    _require(event_types == expected_order, "realtime mock event order mismatch")
    _require(all(event.session_id == session.info.session_id for event in events), "events should include session_id")
    _require(all(event.boundary == "realtime" for event in events), "events should use realtime boundary")
    _ok("RealtimeSession emits deterministic public mock event flow")


def _assert_closed_behavior(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)
    session.close()
    session.dispose()
    _require(session.is_closed, "RealtimeSession should be closed after close/dispose")
    _require(session.state == framework.RealtimeState.CLOSED, "RealtimeSession state should be closed after close")
    _require(events[-1].type == framework.RealtimeEventType.SESSION_CLOSED, "close should emit session.closed")

    result = session.run_turn(input_text="after close")
    _require(result.outcome == framework.RealtimeState.CLOSED, "closed session run_turn should return closed result")
    _require(result.public_error_code == framework.RealtimeErrorCode.SESSION_CLOSED, "closed session error code mismatch")
    _ok("RealtimeSession closed behavior is provider-neutral")


def _assert_context_manager(framework) -> None:
    with framework.create_realtime_session() as session:
        _require(not session.is_closed, "RealtimeSession should be open inside context")
    _require(session.is_closed, "RealtimeSession context manager should close on exit")
    _require(session.state == framework.RealtimeState.CLOSED, "RealtimeSession context manager should set closed state")
    _ok("RealtimeSession context manager closes on exit")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_session_info(framework)
    _assert_event_flow(framework)
    _assert_closed_behavior(framework)
    _assert_context_manager(framework)
    _ok("v5.2.0 public realtime session skeleton is mock-safe")


if __name__ == "__main__":
    main()
