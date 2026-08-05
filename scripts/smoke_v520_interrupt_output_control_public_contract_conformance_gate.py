"""v5.2.0 public interrupt / output-control contract conformance gate."""

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
    path = root / "docs" / "v520_interrupt_output_control_public_contract_conformance_gate.md"
    _require(path.exists(), "missing docs/v520_interrupt_output_control_public_contract_conformance_gate.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Interrupt / Output-Control Public Contract Conformance Gate",
        "InterruptScope",
        "InterruptReason",
        "InterruptOutcome",
        "InterruptRequest",
        "InterruptResult",
        "TTSQueueState",
        "OutputFlushOutcome",
        "OutputFlushRequest",
        "OutputFlushResult",
        "BargeInPolicyMode",
        "BargeInPolicy",
        "BargeInDecision",
        "RealtimeSession.get_tts_queue_state",
        "RealtimeSession.interrupt",
        "RealtimeSession.cancel_current_turn",
        "RealtimeSession.flush_output",
        "RealtimeSession.set_barge_in_policy",
        "RealtimeSession.decide_barge_in",
        "Public import rule",
        "Type rule",
        "Realtime session rule",
        "Event rule",
        "Host-app example rule",
        "Current limitation",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"interrupt/output-control conformance gate doc missing phrase: {phrase}")
    _ok("v5.2.0 interrupt/output-control public contract conformance gate doc is documented")


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
    _require(not hits, "import framework eagerly loaded interrupt/output provider modules: " + ", ".join(hits[:16]))
    _ok("framework public import stays interrupt/output-control provider safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "InterruptScope",
        "InterruptReason",
        "InterruptOutcome",
        "InterruptRequest",
        "InterruptResult",
        "TTSQueueState",
        "OutputFlushOutcome",
        "OutputFlushRequest",
        "OutputFlushResult",
        "BargeInPolicyMode",
        "BargeInPolicy",
        "BargeInDecision",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")
    _ok("framework exports all public interrupt/output-control symbols")


def _assert_realtime_factory_signature(framework) -> None:
    sig = inspect.signature(framework.create_realtime_session)
    for param in sig.parameters.values():
        _require(
            param.kind is inspect.Parameter.KEYWORD_ONLY,
            f"create_realtime_session parameter should remain keyword-only: {param.name}",
        )
    _ok("create_realtime_session remains keyword-only for output-control integration")


def _assert_enum_contracts(framework) -> None:
    interrupt_scopes = {value.value for value in framework.InterruptScope}
    _require(
        {"current_turn", "llm_stream", "tts_queue", "voice_output", "motion", "all"}.issubset(interrupt_scopes),
        "InterruptScope missing expected values",
    )

    interrupt_reasons = {value.value for value in framework.InterruptReason}
    _require(
        {
            "user_barge_in",
            "user_cancel",
            "new_turn_started",
            "session_closed",
            "timeout",
            "host_app_request",
            "provider_failure",
        }.issubset(interrupt_reasons),
        "InterruptReason missing expected values",
    )

    interrupt_outcomes = {value.value for value in framework.InterruptOutcome}
    _require(
        {"accepted", "unsupported", "no_active_turn", "already_closed", "not_implemented", "failed"}.issubset(
            interrupt_outcomes
        ),
        "InterruptOutcome missing expected values",
    )

    flush_outcomes = {value.value for value in framework.OutputFlushOutcome}
    _require(
        {"flushed", "nothing_to_flush", "unsupported", "not_implemented", "failed", "closed"}.issubset(flush_outcomes),
        "OutputFlushOutcome missing expected values",
    )

    policy_modes = {value.value for value in framework.BargeInPolicyMode}
    _require(
        {"disabled", "soft_interrupt", "flush_output", "hard_cancel", "turn_takeover"}.issubset(policy_modes),
        "BargeInPolicyMode missing expected values",
    )

    event_types = {value.value for value in framework.RealtimeEventType}
    _require(
        {
            "realtime.interrupt.requested",
            "realtime.interrupt.unsupported",
            "realtime.output.flush.requested",
            "realtime.output.flush.completed",
            "realtime.barge_in.detected",
            "realtime.barge_in.accepted",
            "realtime.barge_in.rejected",
        }.issubset(event_types),
        "RealtimeEventType missing interrupt/output-control events",
    )
    _ok("interrupt/output-control enum and event contracts conform")


def _assert_interrupt_types(framework) -> None:
    request = framework.InterruptRequest.user_barge_in(
        turn_id="turn-1",
        public_metadata={"api_key": "should-not-leak", "screen": "daily"},
    )
    _require(request.scope == framework.InterruptScope.ALL, "user_barge_in request scope mismatch")
    _require(type(request.turn_id) is str, "legacy interrupt turn_id should remain str")
    _require(request.reason == framework.InterruptReason.USER_BARGE_IN, "user_barge_in request reason mismatch")
    _require(request.flush_output, "user_barge_in should flush output")
    _require(request.cancel_tts_queue, "user_barge_in should cancel TTS queue")
    _require(request.cancel_llm_stream, "user_barge_in should cancel LLM stream")
    _require(request.stop_motion, "user_barge_in should stop motion")
    _require(request.public_metadata["api_key"] == "<redacted>", "InterruptRequest metadata should be redacted")
    _require("should-not-leak" not in repr(request), "InterruptRequest repr should not leak secret-like metadata")

    not_impl = framework.InterruptResult.not_implemented(request=request)
    _require(not_impl.outcome == framework.InterruptOutcome.NOT_IMPLEMENTED, "not_implemented outcome mismatch")
    _require(not not_impl.accepted, "not_implemented result should not be accepted")
    _require(not_impl.is_terminal, "not_implemented result should be terminal")
    _require(not not_impl.provider_cancel_supported, "not_implemented should not claim provider cancel")
    _require(not not_impl.queue_flush_supported, "not_implemented should not claim queue flush")

    closed = framework.InterruptResult.already_closed(request=request)
    _require(closed.outcome == framework.InterruptOutcome.ALREADY_CLOSED, "already_closed outcome mismatch")

    no_active = framework.InterruptResult.no_active_turn(request=request)
    _require(no_active.outcome == framework.InterruptOutcome.NO_ACTIVE_TURN, "no_active_turn outcome mismatch")
    serialized_turn_id = str(framework.TurnId.new())
    normalized = framework.InterruptRequest(turn_id=serialized_turn_id)
    _require(isinstance(normalized.turn_id, framework.TurnId), "serialized TurnId should normalize")
    try:
        framework.InterruptRequest(turn_id=str(framework.SessionId.new()))
    except ValueError:
        pass
    else:
        raise ContractFailure("SessionId must be rejected as interrupt turn_id")
    _ok("public interrupt request/result types conform")


def _assert_queue_flush_types(framework) -> None:
    queue = framework.TTSQueueState(
        queued_count=0,
        supports_flush=False,
        supports_provider_cancel=False,
        playback_stop_required=False,
        public_metadata={"token": "should-not-leak"},
    )
    _require(queue.queued_count == 0, "TTSQueueState queued_count mismatch")
    _require(not queue.supports_flush, "TTSQueueState should not overclaim flush support")
    _require(not queue.supports_provider_cancel, "TTSQueueState should not overclaim provider cancel")
    _require(queue.public_metadata["token"] == "<redacted>", "TTSQueueState metadata should be redacted")

    request = framework.OutputFlushRequest(public_metadata={"credential": "should-not-leak"})
    _require(request.scope == framework.InterruptScope.TTS_QUEUE, "OutputFlushRequest default scope mismatch")
    _require(request.stop_playback, "OutputFlushRequest should default to stop playback")
    _require(request.clear_queued_audio, "OutputFlushRequest should default to clear queued audio")
    _require(request.public_metadata["credential"] == "<redacted>", "OutputFlushRequest metadata should be redacted")
    _require("should-not-leak" not in repr(request), "OutputFlushRequest repr should not leak secret-like metadata")

    not_impl = framework.OutputFlushResult.not_implemented(request=request)
    _require(not_impl.outcome == framework.OutputFlushOutcome.NOT_IMPLEMENTED, "flush not_implemented outcome mismatch")
    _require(not not_impl.flushed, "not_implemented flush should not be flushed")

    nothing = framework.OutputFlushResult.nothing_to_flush(request=request)
    _require(nothing.outcome == framework.OutputFlushOutcome.NOTHING_TO_FLUSH, "nothing_to_flush outcome mismatch")

    closed = framework.OutputFlushResult.closed(request=request)
    _require(closed.outcome == framework.OutputFlushOutcome.CLOSED, "closed flush outcome mismatch")
    _ok("public TTS queue / output flush types conform")


def _assert_barge_in_types(framework) -> None:
    disabled = framework.BargeInPolicy.disabled()
    _require(disabled.mode == framework.BargeInPolicyMode.DISABLED, "disabled policy mismatch")

    soft = framework.BargeInPolicy.soft_interrupt()
    _require(soft.mode == framework.BargeInPolicyMode.SOFT_INTERRUPT, "soft policy mismatch")
    _require(soft.interrupt_scope == framework.InterruptScope.CURRENT_TURN, "soft policy scope mismatch")

    flush = framework.BargeInPolicy.flush_output()
    _require(flush.mode == framework.BargeInPolicyMode.FLUSH_OUTPUT, "flush policy mismatch")
    _require(flush.flush_output, "flush policy should request flush")

    hard = framework.BargeInPolicy.hard_cancel()
    _require(hard.mode == framework.BargeInPolicyMode.HARD_CANCEL, "hard cancel policy mismatch")
    _require(hard.flush_output, "hard cancel policy should request flush")
    _require(hard.cancel_current_turn, "hard cancel policy should request turn cancel")

    takeover = framework.BargeInPolicy.turn_takeover()
    _require(takeover.mode == framework.BargeInPolicyMode.TURN_TAKEOVER, "turn takeover policy mismatch")
    _require(takeover.allow_turn_takeover, "turn takeover policy should allow takeover")

    rejected = framework.BargeInDecision.rejected(policy=disabled)
    _require(not rejected.accepted, "disabled barge-in decision should be rejected")

    accepted = framework.BargeInDecision.accepted_for_policy(
        hard,
        turn_id="turn-1",
        public_metadata={"secret": "should-not-leak"},
    )
    _require(accepted.accepted, "hard cancel policy decision should be accepted")
    _require(accepted.interrupt_request is not None, "accepted decision should include InterruptRequest")
    _require(accepted.should_stop_output, "hard cancel decision should stop output")
    _require(accepted.should_flush_queue, "hard cancel decision should flush queue")
    _require(accepted.should_cancel_current_turn, "hard cancel decision should cancel current turn")
    _require(accepted.public_metadata["secret"] == "<redacted>", "BargeInDecision metadata should be redacted")
    _require("should-not-leak" not in repr(accepted), "BargeInDecision repr should not leak secret-like metadata")
    _ok("public barge-in policy/decision types conform")


def _assert_realtime_session_output_control(framework) -> None:
    session = framework.create_realtime_session(public_metadata={"password": "should-not-leak"})
    _require(hasattr(session, "get_tts_queue_state"), "RealtimeSession missing get_tts_queue_state")
    _require(hasattr(session, "interrupt"), "RealtimeSession missing interrupt")
    _require(hasattr(session, "cancel_current_turn"), "RealtimeSession missing cancel_current_turn")
    _require(hasattr(session, "flush_output"), "RealtimeSession missing flush_output")
    _require(hasattr(session, "set_barge_in_policy"), "RealtimeSession missing set_barge_in_policy")
    _require(hasattr(session, "decide_barge_in"), "RealtimeSession missing decide_barge_in")
    _require(hasattr(session, "barge_in_policy"), "RealtimeSession missing barge_in_policy")

    info = session.info
    _require(info.supports_interrupt, "RealtimeSessionInfo should expose public interrupt control")
    _require(info.supports_output_flush, "RealtimeSessionInfo should expose public output flush control")
    _require(info.supports_barge_in_policy, "RealtimeSessionInfo should expose public barge-in policy control")
    _require(not info.hard_cancel_supported, "RealtimeSessionInfo should not overclaim real hard cancel")
    _require(not info.tts_queue_flush_supported, "RealtimeSessionInfo should not overclaim real queue flush")
    _require(info.public_metadata["password"] == "<redacted>", "RealtimeSessionInfo metadata should be redacted")

    queue = session.get_tts_queue_state()
    _require(queue.queued_count == 0, "mock queue should be empty")
    _require(not queue.supports_flush, "mock queue should not claim real flush support")
    _require(not queue.supports_provider_cancel, "mock queue should not claim provider cancel support")
    _ok("RealtimeSession exposes honest public output-control surface")


def _assert_realtime_session_interrupt_and_flush(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)

    no_active = session.interrupt(framework.InterruptRequest.user_barge_in(public_metadata={"token": "should-not-leak"}))
    _require(no_active.outcome == framework.InterruptOutcome.NO_ACTIVE_TURN, "interrupt without active turn should be no_active_turn")
    _require(events[0].type == framework.RealtimeEventType.INTERRUPT_REQUESTED, "interrupt should emit requested event")
    _require(events[-1].type == framework.RealtimeEventType.INTERRUPT_UNSUPPORTED, "no-active interrupt should emit unsupported event")
    _require("should-not-leak" not in repr(no_active), "interrupt result should not leak secret-like metadata")

    explicit = session.interrupt(framework.InterruptRequest.user_barge_in(turn_id="turn-1"))
    _require(explicit.outcome == framework.InterruptOutcome.NOT_IMPLEMENTED, "explicit turn interrupt should be not_implemented")
    _require(not explicit.provider_cancel_supported, "explicit interrupt should not claim provider cancel")
    _require(not explicit.queue_flush_supported, "explicit interrupt should not claim queue flush")
    _require(session.state == framework.RealtimeState.IDLE, "session should return to idle after not_implemented interrupt")

    cancel = session.cancel_current_turn()
    _require(cancel.outcome == framework.InterruptOutcome.NO_ACTIVE_TURN, "cancel_current_turn without active turn should be no_active_turn")
    _require(cancel.scope == framework.InterruptScope.CURRENT_TURN, "cancel_current_turn scope mismatch")

    flush = session.flush_output(framework.OutputFlushRequest(public_metadata={"api_key": "should-not-leak"}))
    _require(flush.outcome == framework.OutputFlushOutcome.NOTHING_TO_FLUSH, "empty mock flush should be nothing_to_flush")
    _require(not flush.flushed, "empty mock flush should not report flushed")
    _require(events[-1].type == framework.RealtimeEventType.OUTPUT_FLUSH_COMPLETED, "empty flush should emit completed event")
    _require("should-not-leak" not in repr(flush), "flush result should not leak secret-like metadata")
    _ok("RealtimeSession interrupt/cancel/flush behavior conforms")


def _assert_realtime_session_barge_in_and_closed(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)

    rejected = session.decide_barge_in(turn_id="disabled-turn", public_metadata={"secret": "should-not-leak"})
    _require(not rejected.accepted, "default disabled barge-in should reject")
    _require(events[0].type == framework.RealtimeEventType.BARGE_IN_DETECTED, "barge-in should emit detected")
    _require(events[-1].type == framework.RealtimeEventType.BARGE_IN_REJECTED, "disabled barge-in should emit rejected")

    policy = framework.BargeInPolicy.hard_cancel()
    returned = session.set_barge_in_policy(policy)
    _require(returned.mode == framework.BargeInPolicyMode.HARD_CANCEL, "set_barge_in_policy return mismatch")
    _require(session.barge_in_policy.mode == framework.BargeInPolicyMode.HARD_CANCEL, "stored barge-in policy mismatch")

    accepted = session.decide_barge_in(turn_id="active-turn", public_metadata={"credential": "should-not-leak"})
    _require(accepted.accepted, "hard-cancel barge-in policy should accept")
    _require(accepted.should_stop_output, "accepted decision should stop output")
    _require(accepted.should_flush_queue, "accepted decision should flush queue")
    _require(accepted.should_cancel_current_turn, "accepted decision should cancel current turn")
    _require(accepted.public_metadata["credential"] == "<redacted>", "accepted decision metadata should be redacted")
    _require(events[-1].type == framework.RealtimeEventType.BARGE_IN_ACCEPTED, "enabled barge-in should emit accepted")

    session.close()
    closed_interrupt = session.interrupt(framework.InterruptRequest.user_barge_in())
    _require(closed_interrupt.outcome == framework.InterruptOutcome.ALREADY_CLOSED, "closed interrupt should be already_closed")
    closed_flush = session.flush_output()
    _require(closed_flush.outcome == framework.OutputFlushOutcome.CLOSED, "closed flush should be closed")
    _ok("RealtimeSession barge-in and closed output-control behavior conforms")


def _assert_host_app_examples(root: Path) -> None:
    examples = [
        root / "examples" / "app_realtime_interrupt_handling.py",
        root / "examples" / "app_realtime_output_flush_handling.py",
        root / "examples" / "app_realtime_barge_in_policy.py",
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

    _ok("interrupt/output-control host-app examples conform to public-only rule")


def _assert_readme(root: Path) -> None:
    path = root / "README.md"
    _require(path.exists(), "missing README.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_links = [
        "v520_cancel_tts_queue_barge_in_inventory.md",
        "v520_interrupt_output_control_types.md",
        "v520_realtime_interrupt_output_control_wiring.md",
        "v520_interrupt_output_control_host_app_examples.md",
        "v520_interrupt_output_control_public_contract_conformance_gate.md",
    ]
    for link in required_links:
        _require(link in text, f"README missing v5.2.0 interrupt/output-control link: {link}")
    _ok("README links public interrupt/output-control contract docs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _import_framework_safely(root)
    _assert_public_exports(framework)
    _assert_realtime_factory_signature(framework)
    _assert_enum_contracts(framework)
    _assert_interrupt_types(framework)
    _assert_queue_flush_types(framework)
    _assert_barge_in_types(framework)
    _assert_realtime_session_output_control(framework)
    _assert_realtime_session_interrupt_and_flush(framework)
    _assert_realtime_session_barge_in_and_closed(framework)
    _assert_host_app_examples(root)
    _assert_readme(root)
    _ok("v5.2.0 public interrupt / output-control contract conformance gate passed")


if __name__ == "__main__":
    main()
