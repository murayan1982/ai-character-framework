"""v5.2.0 public realtime lifecycle event type smoke."""

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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _assert_doc(root: Path) -> None:
    path = root / "docs" / "v520_realtime_lifecycle_event_types.md"
    _require(path.exists(), "missing docs/v520_realtime_lifecycle_event_types.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Public Realtime Lifecycle Event Types",
        "RealtimeState",
        "RealtimeEventType",
        "RealtimeErrorCode",
        "RealtimeEvent",
        "RealtimeTurn",
        "RealtimeTurnResult",
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
        "realtime.session.closed",
        "Import safety",
        "create_realtime_session",
        "RealtimeSession",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"realtime lifecycle event type doc missing phrase: {phrase}")
    _ok("v5.2.0 public realtime lifecycle event type doc is documented")


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
    _ok("public realtime type import stays provider/internal safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "RealtimeState",
        "RealtimeEventType",
        "RealtimeErrorCode",
        "RealtimeEvent",
        "RealtimeTurn",
        "RealtimeTurnResult",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")
    _ok("framework exports public realtime lifecycle/event types")


def _assert_state_contract(framework) -> None:
    expected_states = {
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
    }
    actual_states = {state.value for state in framework.RealtimeState}
    _require(expected_states.issubset(actual_states), "RealtimeState missing expected states")

    expected_events = {
        "realtime.session.created",
        "realtime.turn.started",
        "realtime.voice_input.started",
        "realtime.voice_input.completed",
        "realtime.text_chat.started",
        "realtime.text_chat.completed",
        "realtime.voice_output.started",
        "realtime.voice_output.completed",
        "realtime.motion.started",
        "realtime.motion.completed",
        "realtime.turn.completed",
        "realtime.turn.interrupted",
        "realtime.turn.failed",
        "realtime.session.closed",
    }
    actual_events = {event.value for event in framework.RealtimeEventType}
    _require(expected_events.issubset(actual_events), "RealtimeEventType missing expected events")
    _ok("RealtimeState and RealtimeEventType values conform")


def _assert_event_contract(framework) -> None:
    event = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
        previous_state=framework.RealtimeState.IDLE,
        turn_id="turn-1",
        session_id="session-1",
        public_metadata={"purpose": "smoke", "api_key": "should-not-leak"},
    )
    _require(event.type == framework.RealtimeEventType.TURN_STARTED, "RealtimeEvent type mismatch")
    _require(event.state == framework.RealtimeState.LISTENING, "RealtimeEvent state mismatch")
    _require(event.previous_state == framework.RealtimeState.IDLE, "RealtimeEvent previous_state mismatch")
    _require(event.public_metadata["api_key"] == "<redacted>", "RealtimeEvent should redact secret-like metadata")
    _require("should-not-leak" not in repr(event), "RealtimeEvent repr should not leak secret-like metadata")

    event_dict = event.as_dict()
    _require(event_dict["type"] == "realtime.turn.started", "RealtimeEvent.as_dict type mismatch")
    _require(event_dict["state"] == "listening", "RealtimeEvent.as_dict state mismatch")
    _require(event_dict["previous_state"] == "idle", "RealtimeEvent.as_dict previous_state mismatch")
    _require(event_dict["public_metadata"]["api_key"] == "<redacted>", "RealtimeEvent.as_dict metadata should remain redacted")
    _ok("RealtimeEvent contract is provider-neutral and secret-safe")


def _assert_turn_contract(framework) -> None:
    turn = framework.RealtimeTurn(
        input_text="hello",
        state=framework.RealtimeState.IDLE,
        session_id="session-1",
        public_metadata={"token": "should-not-leak"},
    )
    _require(turn.turn_id, "RealtimeTurn should generate turn_id")
    _require(turn.input_text == "hello", "RealtimeTurn should preserve input_text")
    _require(turn.state == framework.RealtimeState.IDLE, "RealtimeTurn state mismatch")
    _require(turn.public_metadata["token"] == "<redacted>", "RealtimeTurn metadata should redact secret-like keys")
    _require("should-not-leak" not in repr(turn), "RealtimeTurn repr should not leak secret-like metadata")

    completed = framework.RealtimeTurnResult.completed(
        turn_id=turn.turn_id,
        input_text="hello",
        output_text="world",
        public_metadata={"secret": "should-not-leak"},
    )
    _require(completed.outcome == framework.RealtimeState.COMPLETED, "RealtimeTurnResult completed outcome mismatch")
    _require(completed.output_text == "world", "RealtimeTurnResult output_text mismatch")
    _require(completed.is_completed, "completed turn result should be completed")
    _require(completed.is_terminal, "completed turn result should be terminal")
    _require(completed.public_metadata["secret"] == "<redacted>", "RealtimeTurnResult metadata should redact secret-like keys")

    interrupted = framework.RealtimeTurnResult.interrupted(turn_id=turn.turn_id)
    _require(interrupted.outcome == framework.RealtimeState.INTERRUPTED, "interrupted outcome mismatch")
    _require(interrupted.public_error_code == framework.RealtimeErrorCode.INTERRUPTED, "interrupted error code mismatch")
    _require(interrupted.retryable, "interrupted result should be retryable")

    failed = framework.RealtimeTurnResult.failed(turn_id=turn.turn_id)
    _require(failed.outcome == framework.RealtimeState.FAILED, "failed outcome mismatch")
    _require(failed.public_error_code == framework.RealtimeErrorCode.STAGE_FAILED, "failed error code mismatch")

    closed = framework.RealtimeTurnResult.closed(turn_id=turn.turn_id)
    _require(closed.outcome == framework.RealtimeState.CLOSED, "closed outcome mismatch")
    _require(closed.public_error_code == framework.RealtimeErrorCode.SESSION_CLOSED, "closed error code mismatch")
    _ok("RealtimeTurn and RealtimeTurnResult contracts are provider-neutral and secret-safe")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_state_contract(framework)
    _assert_event_contract(framework)
    _assert_turn_contract(framework)
    _ok("v5.2.0 public realtime lifecycle event types are mock-safe")


if __name__ == "__main__":
    main()
