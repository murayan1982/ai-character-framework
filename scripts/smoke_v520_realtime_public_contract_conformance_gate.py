"""v5.2.0 public realtime contract conformance gate."""

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
    path = root / "docs" / "v520_realtime_public_contract_conformance_gate.md"
    _require(path.exists(), "missing docs/v520_realtime_public_contract_conformance_gate.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Realtime Public Contract Conformance Gate",
        "RealtimeState",
        "RealtimeEventType",
        "RealtimeErrorCode",
        "RealtimeEvent",
        "RealtimeTurn",
        "RealtimeTurnResult",
        "create_realtime_session",
        "RealtimeSession",
        "RealtimeSessionInfo",
        "Public import rule",
        "Factory signature rule",
        "Type rule",
        "Session rule",
        "Host-app example rule",
        "Current limitation",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"realtime conformance gate doc missing phrase: {phrase}")
    _ok("v5.2.0 realtime public contract conformance gate doc is documented")


def _import_framework_safely(root: Path):
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
    ]
    hits = sorted(name for name in loaded if any(fragment in name.lower() for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded realtime/provider modules: " + ", ".join(hits[:16]))
    _ok("framework public import stays realtime/provider safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "RealtimeState",
        "RealtimeEventType",
        "RealtimeErrorCode",
        "RealtimeEvent",
        "RealtimeTurn",
        "RealtimeTurnResult",
        "create_realtime_session",
        "RealtimeSession",
        "RealtimeSessionInfo",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")

    _ok("framework exports all public realtime conformance symbols")


def _assert_factory_signature(framework) -> None:
    sig = inspect.signature(framework.create_realtime_session)
    _require(sig.parameters, "create_realtime_session should expose explicit parameters")
    for param in sig.parameters.values():
        _require(
            param.kind is inspect.Parameter.KEYWORD_ONLY,
            f"create_realtime_session parameter should be keyword-only: {param.name}",
        )

    expected = {
        "project_root",
        "public_metadata",
        "real_runtime_enabled",
    }
    _require(expected.issubset(set(sig.parameters)), "create_realtime_session missing expected public parameters")
    _ok("create_realtime_session signature is explicit and keyword-only")


def _assert_state_and_event_types(framework) -> None:
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
    _require(expected_states.issubset(actual_states), "RealtimeState missing expected lifecycle states")

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
    _require(expected_events.issubset(actual_events), "RealtimeEventType missing expected public events")

    expected_errors = {
        "none",
        "unavailable",
        "unsupported",
        "interrupted",
        "session_closed",
        "invalid_request",
        "stage_failed",
        "provider_error",
    }
    actual_errors = {error.value for error in framework.RealtimeErrorCode}
    _require(expected_errors.issubset(actual_errors), "RealtimeErrorCode missing expected public errors")
    _ok("Realtime enum contracts conform")


def _assert_event_and_turn_types(framework) -> None:
    event = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
        previous_state=framework.RealtimeState.IDLE,
        turn_id="turn-1",
        session_id="session-1",
        safe_message="Starting turn.",
        public_metadata={"token": "should-not-leak", "screen": "daily"},
    )
    _require(event.type == framework.RealtimeEventType.TURN_STARTED, "RealtimeEvent type mismatch")
    _require(event.state == framework.RealtimeState.LISTENING, "RealtimeEvent state mismatch")
    _require(event.previous_state == framework.RealtimeState.IDLE, "RealtimeEvent previous_state mismatch")
    _require(type(event.turn_id) is str, "legacy RealtimeEvent turn_id should remain str")
    _require(type(event.session_id) is str, "legacy RealtimeEvent session_id should remain str")
    _require(event.public_metadata["token"] == "<redacted>", "RealtimeEvent should redact secret-like metadata")
    _require("should-not-leak" not in repr(event), "RealtimeEvent repr should not leak secret-like metadata")

    event_dict = event.as_dict()
    _require(event_dict["type"] == "realtime.turn.started", "RealtimeEvent.as_dict type mismatch")
    _require(event_dict["state"] == "listening", "RealtimeEvent.as_dict state mismatch")
    _require(event_dict["previous_state"] == "idle", "RealtimeEvent.as_dict previous_state mismatch")
    _require(event_dict["public_metadata"]["token"] == "<redacted>", "RealtimeEvent.as_dict metadata should be redacted")

    turn = framework.RealtimeTurn(
        input_text="hello",
        session_id="session-1",
        public_metadata={"api_key": "should-not-leak"},
    )
    _require(isinstance(turn.turn_id, framework.TurnId), "new RealtimeTurn should use TurnId")
    _require(type(turn.session_id) is str, "legacy RealtimeTurn session_id should remain str")
    _require(turn.input_text == "hello", "RealtimeTurn should preserve input text")
    _require(turn.state == framework.RealtimeState.IDLE, "RealtimeTurn default state should be idle")
    _require(turn.public_metadata["api_key"] == "<redacted>", "RealtimeTurn should redact secret-like metadata")

    completed = framework.RealtimeTurnResult.completed(
        turn_id=turn.turn_id,
        input_text="hello",
        output_text="world",
        public_metadata={"credential": "should-not-leak"},
    )
    _require(completed.outcome == framework.RealtimeState.COMPLETED, "completed result outcome mismatch")
    _require(type(completed.outcome) is framework.TurnOutcome, "completed outcome should normalize to TurnOutcome")
    _require(completed.recovery_action is framework.RecoveryAction.NONE, "completed recovery action mismatch")
    _require(completed.is_completed, "completed result should be completed")
    _require(completed.is_terminal, "completed result should be terminal")
    _require(completed.public_metadata["credential"] == "<redacted>", "completed result metadata should be redacted")

    interrupted = framework.RealtimeTurnResult.interrupted(turn_id=turn.turn_id)
    _require(interrupted.outcome == framework.RealtimeState.INTERRUPTED, "interrupted result outcome mismatch")
    _require(type(interrupted.outcome) is framework.TurnOutcome, "interrupted outcome should normalize to TurnOutcome")
    _require(interrupted.recovery_action is framework.RecoveryAction.RESET_TURN, "interrupted recovery action mismatch")
    _require(interrupted.public_error_code == framework.RealtimeErrorCode.INTERRUPTED, "interrupted result error code mismatch")
    _require(interrupted.retryable, "interrupted result should be retryable")

    cancelled = framework.RealtimeTurnResult.cancelled(turn_id=turn.turn_id)
    _require(cancelled.outcome is framework.TurnOutcome.CANCELLED, "cancelled result outcome mismatch")
    _require(cancelled.recovery_action is framework.RecoveryAction.RESET_TURN, "cancelled recovery action mismatch")
    _require(cancelled.public_error_code is framework.RealtimeErrorCode.CANCELLED, "cancelled error code mismatch")

    rejected = framework.RealtimeTurnResult.rejected(turn_id=turn.turn_id)
    _require(rejected.outcome is framework.TurnOutcome.REJECTED, "rejected result outcome mismatch")
    _require(rejected.recovery_action is framework.RecoveryAction.REUSE_SESSION, "rejected recovery action mismatch")
    _require(rejected.public_error_code is framework.RealtimeErrorCode.REJECTED, "rejected error code mismatch")

    failed = framework.RealtimeTurnResult.failed(turn_id=turn.turn_id)
    _require(failed.outcome == framework.RealtimeState.FAILED, "failed result outcome mismatch")
    _require(type(failed.outcome) is framework.TurnOutcome, "failed outcome should normalize to TurnOutcome")
    _require(failed.recovery_action is framework.RecoveryAction.RESET_SESSION, "failed recovery action mismatch")
    _require(failed.public_error_code == framework.RealtimeErrorCode.STAGE_FAILED, "failed result error code mismatch")

    closed = framework.RealtimeTurnResult.closed(turn_id=turn.turn_id)
    _require(closed.outcome == framework.RealtimeState.CLOSED, "closed result outcome mismatch")
    _require(type(closed.outcome) is framework.TurnOutcome, "closed outcome should normalize to TurnOutcome")
    _require(closed.recovery_action is framework.RecoveryAction.NONE, "closed recovery action mismatch")
    _require(closed.public_error_code == framework.RealtimeErrorCode.SESSION_CLOSED, "closed result error code mismatch")

    try:
        framework.RealtimeTurnResult(
            turn_id=turn.turn_id,
            outcome=framework.RealtimeState.THINKING,
        )
    except framework.LifecycleTransitionError as exc:
        _require(
            exc.code is framework.LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH,
            "phase/outcome mismatch error code drift",
        )
    else:
        raise ContractFailure("transient RealtimeState was accepted as turn outcome")
    _ok("Realtime event/turn public types conform")


def _assert_session_contract(framework) -> None:
    events = []
    session = framework.create_realtime_session(public_metadata={"secret": "should-not-leak"})
    session.on_event(events.append)

    _require(isinstance(session.info, framework.RealtimeSessionInfo), "session.info should be RealtimeSessionInfo")
    _require(session.info.session_type == "realtime", "session.info session_type mismatch")
    _require(isinstance(session.info.session_id, framework.SessionId), "new session should use SessionId")
    _require(session.info.state == framework.RealtimeState.IDLE, "new session info state should be idle")
    _require(session.state == framework.RealtimeState.IDLE, "new session state should be idle")
    _require(session.info.public_metadata["secret"] == "<redacted>", "session.info metadata should be redacted")
    _require(not session.is_closed, "new RealtimeSession should be open")
    _require(not session.info.real_runtime_enabled, "session should not enable real runtime by default")
    _require(session.info.supports_interrupt, "session should expose public interrupt control")
    _require(session.info.supports_output_flush, "session should expose public output flush control")
    _require(session.info.supports_barge_in_policy, "session should expose public barge-in policy control")
    _require(not session.info.hard_cancel_supported, "real hard cancel should not be claimed yet")
    _require(not session.info.tts_queue_flush_supported, "real TTS queue flush should not be claimed yet")
    _require(not session.info.supports_motion, "motion should not be claimed yet")

    created = session.emit_created()
    _require(created.type == framework.RealtimeEventType.SESSION_CREATED, "emit_created event type mismatch")

    result = session.run_turn(input_text="今日は眠いです。", public_metadata={"password": "should-not-leak"})
    _require(result.outcome == framework.RealtimeState.COMPLETED, "run_turn result outcome mismatch")
    _require(type(result.outcome) is framework.TurnOutcome, "run_turn result should use TurnOutcome")
    _require(result.recovery_action is framework.RecoveryAction.NONE, "run_turn completed recovery mismatch")
    _require(isinstance(result.turn_id, framework.TurnId), "run_turn result should use TurnId")
    _require(result.input_text == "今日は眠いです。", "run_turn should preserve input text")
    _require(result.public_metadata["mock_runtime"], "run_turn should mark mock_runtime")
    _require(result.public_metadata["password"] == "<redacted>", "run_turn metadata should be redacted")
    _require(session.state == framework.RealtimeState.IDLE, "session should return to idle after mock turn")

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
    _require(event_types == expected_order, "RealtimeSession event order mismatch")
    _require(all(event.session_id == session.info.session_id for event in events), "events should expose session_id")
    _require(all(isinstance(event.session_id, framework.SessionId) for event in events), "generated events should use SessionId")
    _require(all(event.turn_id is None or isinstance(event.turn_id, framework.TurnId) for event in events), "generated turn events should use TurnId")
    _require(all(event.boundary == "realtime" for event in events), "events should use realtime boundary")

    session.close()
    session.dispose()
    _require(session.is_closed, "RealtimeSession should be closed after close/dispose")
    _require(session.state == framework.RealtimeState.CLOSED, "closed session state mismatch")
    _require(events[-1].type == framework.RealtimeEventType.SESSION_CLOSED, "close should emit session.closed")

    closed_result = session.run_turn(input_text="after close")
    _require(closed_result.outcome == framework.RealtimeState.CLOSED, "closed session run_turn should return closed result")
    _require(type(closed_result.outcome) is framework.TurnOutcome, "closed run_turn result should use TurnOutcome")
    _require(closed_result.recovery_action is framework.RecoveryAction.NONE, "closed run_turn recovery mismatch")
    _require(closed_result.public_error_code == framework.RealtimeErrorCode.SESSION_CLOSED, "closed session error code mismatch")

    with framework.create_realtime_session() as managed:
        _require(not managed.is_closed, "managed session should be open in context")
    _require(managed.is_closed, "managed session should close on context exit")
    _require(managed.state == framework.RealtimeState.CLOSED, "managed session should set closed state on context exit")
    _ok("public RealtimeSession contract conforms")


def _assert_host_app_examples(root: Path) -> None:
    examples = [
        root / "examples" / "app_realtime_session_event_flow.py",
        root / "examples" / "app_realtime_event_payload_mapping.py",
        root / "examples" / "app_realtime_closed_session_behavior.py",
    ]
    forbidden_phrases = [
        "from stt",
        "import stt",
        "from llm",
        "import llm",
        "from plugins",
        "import speech_recognition",
        "import whisper",
        "import sounddevice",
        "import pyaudio",
        "import websocket",
        "import websockets",
        "sys.path",
        "chdir(",
        "OPENAI_API_KEY =",
        "GOOGLE_API_KEY =",
    ]

    for path in examples:
        _require(path.exists(), f"missing host-app example: {path.relative_to(root)}")
        text = path.read_text(encoding="utf-8", errors="replace")
        _require("import framework" in text, f"{path.name} should use public framework import")
        for phrase in forbidden_phrases:
            _require(phrase not in text, f"{path.name} contains forbidden phrase: {phrase}")

    _ok("realtime host-app examples conform to public-only rule")


def _assert_readme(root: Path) -> None:
    path = root / "README.md"
    _require(path.exists(), "missing README.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_links = [
        "v520_realtime_lifecycle_event_inventory.md",
        "v520_realtime_lifecycle_event_types.md",
        "v520_realtime_session_skeleton.md",
        "v520_realtime_host_app_examples.md",
        "v520_realtime_public_contract_conformance_gate.md",
        "v520_realtime_interrupt_output_control_wiring.md",
    ]
    for link in required_links:
        _require(link in text, f"README missing v5.2.0 realtime link: {link}")
    _ok("README links public realtime contract docs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _import_framework_safely(root)
    _assert_public_exports(framework)
    _assert_factory_signature(framework)
    _assert_state_and_event_types(framework)
    _assert_event_and_turn_types(framework)
    _assert_session_contract(framework)
    _assert_host_app_examples(root)
    _assert_readme(root)
    _ok("v5.2.0 public realtime contract conformance gate passed")


if __name__ == "__main__":
    main()
