"""v5.2.0 realtime interrupt / output control wiring smoke."""

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
    path = root / "docs" / "v520_realtime_interrupt_output_control_wiring.md"
    _require(path.exists(), "missing docs/v520_realtime_interrupt_output_control_wiring.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Realtime Interrupt / Output Control Wiring",
        "get_tts_queue_state",
        "interrupt",
        "cancel_current_turn",
        "flush_output",
        "set_barge_in_policy",
        "decide_barge_in",
        "realtime.interrupt.requested",
        "realtime.output.flush.completed",
        "realtime.barge_in.detected",
        "hard_cancel_supported=False",
        "tts_queue_flush_supported=False",
        "Import safety",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"realtime interrupt/output wiring doc missing phrase: {phrase}")
    _ok("v5.2.0 realtime interrupt / output control wiring doc is documented")


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
    _require(not hits, "import framework eagerly loaded interrupt/TTS/provider modules: " + ", ".join(hits[:16]))
    _ok("realtime interrupt/output wiring import stays provider/internal safe")
    return framework


def _assert_event_type_contract(framework) -> None:
    required = {
        "realtime.interrupt.requested",
        "realtime.interrupt.accepted",
        "realtime.interrupt.completed",
        "realtime.interrupt.unsupported",
        "realtime.output.flush.requested",
        "realtime.output.flush.completed",
        "realtime.output.flush.unsupported",
        "realtime.barge_in.detected",
        "realtime.barge_in.accepted",
        "realtime.barge_in.rejected",
    }
    actual = {event.value for event in framework.RealtimeEventType}
    _require(required.issubset(actual), "RealtimeEventType missing interrupt/output-control events")
    _ok("RealtimeEventType includes interrupt/output-control events")


def _assert_session_info_and_queue(framework) -> None:
    session = framework.create_realtime_session(public_metadata={"token": "should-not-leak"})
    info = session.info
    _require(info.supports_interrupt, "RealtimeSessionInfo should expose supports_interrupt")
    _require(info.supports_output_flush, "RealtimeSessionInfo should expose supports_output_flush")
    _require(info.supports_barge_in_policy, "RealtimeSessionInfo should expose supports_barge_in_policy")
    _require(not info.hard_cancel_supported, "RealtimeSessionInfo should not overclaim hard cancel")
    _require(not info.tts_queue_flush_supported, "RealtimeSessionInfo should not overclaim real TTS queue flush")
    _require(info.public_metadata["token"] == "<redacted>", "RealtimeSessionInfo should redact secret-like metadata")

    queue = session.get_tts_queue_state()
    _require(isinstance(queue, framework.TTSQueueState), "get_tts_queue_state should return TTSQueueState")
    _require(queue.queued_count == 0, "mock queue should be empty")
    _require(not queue.supports_flush, "mock queue should not claim real flush support")
    _require(not queue.supports_provider_cancel, "mock queue should not claim provider cancel support")
    _ok("RealtimeSession exposes honest interrupt/output capabilities")


def _assert_interrupt_no_active_turn(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)

    request = framework.InterruptRequest.user_barge_in(public_metadata={"api_key": "should-not-leak"})
    result = session.interrupt(request)

    _require(result.outcome == framework.InterruptOutcome.NO_ACTIVE_TURN, "interrupt without active turn should report no_active_turn")
    _require(result.scope == framework.InterruptScope.ALL, "interrupt scope should follow request")
    _require(result.reason == framework.InterruptReason.USER_BARGE_IN, "interrupt reason should follow request")
    _require(not result.accepted, "no_active_turn interrupt should not be accepted")
    _require("should-not-leak" not in repr(result), "interrupt result should not leak secret-like metadata")
    _require(events[0].type == framework.RealtimeEventType.INTERRUPT_REQUESTED, "interrupt should emit requested event")
    _require(events[-1].type == framework.RealtimeEventType.INTERRUPT_UNSUPPORTED, "no_active_turn interrupt should emit unsupported event")
    _ok("RealtimeSession.interrupt returns no_active_turn safely")


def _assert_interrupt_not_implemented_with_turn_id(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)

    request = framework.InterruptRequest.user_barge_in(turn_id="turn-123")
    result = session.interrupt(request)

    _require(result.outcome == framework.InterruptOutcome.NOT_IMPLEMENTED, "explicit turn interrupt should report not_implemented")
    _require(result.turn_id == "turn-123", "interrupt result should preserve turn_id")
    _require(not result.provider_cancel_supported, "interrupt result should not claim provider cancel support")
    _require(not result.queue_flush_supported, "interrupt result should not claim queue flush support")
    _require(events[0].type == framework.RealtimeEventType.INTERRUPT_REQUESTED, "interrupt should emit requested")
    _require(events[-1].type == framework.RealtimeEventType.INTERRUPT_UNSUPPORTED, "not implemented interrupt should emit unsupported")
    _require(session.state == framework.RealtimeState.IDLE, "not implemented interrupt should return session to idle")
    _ok("RealtimeSession.interrupt does not overclaim hard cancel")


def _assert_cancel_current_turn(framework) -> None:
    session = framework.create_realtime_session()
    result = session.cancel_current_turn(public_metadata={"secret": "should-not-leak"})
    _require(result.outcome == framework.InterruptOutcome.NO_ACTIVE_TURN, "cancel_current_turn without active turn should report no_active_turn")
    _require(result.scope == framework.InterruptScope.CURRENT_TURN, "cancel_current_turn should use current_turn scope")
    _require("should-not-leak" not in repr(result), "cancel_current_turn result should not leak secret-like metadata")
    _ok("RealtimeSession.cancel_current_turn is typed and safe")


def _assert_flush_output(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)

    request = framework.OutputFlushRequest(public_metadata={"credential": "should-not-leak"})
    result = session.flush_output(request)

    _require(result.outcome == framework.OutputFlushOutcome.NOTHING_TO_FLUSH, "empty mock queue should report nothing_to_flush")
    _require(not result.flushed, "nothing_to_flush should not report flushed")
    _require("should-not-leak" not in repr(result), "flush result should not leak secret-like metadata")
    _require(events[0].type == framework.RealtimeEventType.OUTPUT_FLUSH_REQUESTED, "flush should emit requested event")
    _require(events[-1].type == framework.RealtimeEventType.OUTPUT_FLUSH_COMPLETED, "empty flush should emit completed event")
    _ok("RealtimeSession.flush_output returns typed empty-queue result")


def _assert_barge_in_policy_and_decision(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)

    rejected = session.decide_barge_in(public_metadata={"token": "should-not-leak"})
    _require(not rejected.accepted, "disabled barge-in should be rejected")
    _require(events[0].type == framework.RealtimeEventType.BARGE_IN_DETECTED, "barge-in should emit detected")
    _require(events[-1].type == framework.RealtimeEventType.BARGE_IN_REJECTED, "disabled barge-in should emit rejected")

    policy = framework.BargeInPolicy.hard_cancel()
    returned = session.set_barge_in_policy(policy)
    _require(returned.mode == framework.BargeInPolicyMode.HARD_CANCEL, "set_barge_in_policy should return policy")
    _require(session.barge_in_policy.mode == framework.BargeInPolicyMode.HARD_CANCEL, "session should store barge-in policy")

    accepted = session.decide_barge_in(turn_id="turn-abc", public_metadata={"secret": "should-not-leak"})
    _require(accepted.accepted, "hard cancel barge-in should be accepted as decision")
    _require(accepted.interrupt_request is not None, "accepted barge-in should include interrupt request")
    _require(accepted.should_stop_output, "hard cancel decision should stop output")
    _require(accepted.should_flush_queue, "hard cancel decision should flush queue")
    _require(accepted.should_cancel_current_turn, "hard cancel decision should cancel current turn")
    _require(accepted.public_metadata["secret"] == "<redacted>", "barge-in decision should redact secret-like metadata")
    _require("should-not-leak" not in repr(accepted), "barge-in decision should not leak secret-like metadata")
    _require(events[-1].type == framework.RealtimeEventType.BARGE_IN_ACCEPTED, "enabled barge-in should emit accepted")
    _ok("RealtimeSession barge-in policy and decision are public-safe")


def _assert_closed_results(framework) -> None:
    session = framework.create_realtime_session()
    session.close()

    interrupt_result = session.interrupt(framework.InterruptRequest.user_barge_in())
    _require(interrupt_result.outcome == framework.InterruptOutcome.ALREADY_CLOSED, "closed interrupt should report already_closed")

    flush_result = session.flush_output()
    _require(flush_result.outcome == framework.OutputFlushOutcome.CLOSED, "closed flush should report closed")
    _ok("RealtimeSession interrupt/flush closed behavior is typed")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_event_type_contract(framework)
    _assert_session_info_and_queue(framework)
    _assert_interrupt_no_active_turn(framework)
    _assert_interrupt_not_implemented_with_turn_id(framework)
    _assert_cancel_current_turn(framework)
    _assert_flush_output(framework)
    _assert_barge_in_policy_and_decision(framework)
    _assert_closed_results(framework)
    _ok("v5.2.0 realtime interrupt / output control wiring is mock-safe")


if __name__ == "__main__":
    main()
