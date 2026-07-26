"""v5.2.0 public interrupt / output control type smoke."""

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
    path = root / "docs" / "v520_interrupt_output_control_types.md"
    _require(path.exists(), "missing docs/v520_interrupt_output_control_types.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Public Interrupt / Output Control Types",
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
        "not_implemented",
        "nothing_to_flush",
        "turn_takeover",
        "Safety rules",
        "Import safety",
        "RealtimeSession",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"interrupt/output control type doc missing phrase: {phrase}")
    _ok("v5.2.0 public interrupt / output control type doc is documented")


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
    _ok("public interrupt/output-control import stays provider/internal safe")
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
    _ok("framework exports public interrupt/output-control types")


def _assert_interrupt_contract(framework) -> None:
    request = framework.InterruptRequest.user_barge_in(
        turn_id="turn-1",
        public_metadata={"purpose": "smoke", "api_key": "should-not-leak"},
    )
    _require(request.scope == framework.InterruptScope.ALL, "user_barge_in scope mismatch")
    _require(request.reason == framework.InterruptReason.USER_BARGE_IN, "user_barge_in reason mismatch")
    _require(request.flush_output, "user_barge_in should request flush_output")
    _require(request.cancel_tts_queue, "user_barge_in should request cancel_tts_queue")
    _require(request.cancel_llm_stream, "user_barge_in should request cancel_llm_stream")
    _require(request.stop_motion, "user_barge_in should request stop_motion")
    _require(request.public_metadata["api_key"] == "<redacted>", "InterruptRequest should redact secret-like metadata")
    _require("should-not-leak" not in repr(request), "InterruptRequest repr should not leak secret-like metadata")

    result = framework.InterruptResult.not_implemented(request=request)
    _require(result.outcome == framework.InterruptOutcome.NOT_IMPLEMENTED, "not_implemented outcome mismatch")
    _require(result.scope == framework.InterruptScope.ALL, "not_implemented scope should follow request")
    _require(result.reason == framework.InterruptReason.USER_BARGE_IN, "not_implemented reason should follow request")
    _require(not result.accepted, "not_implemented interrupt should not be accepted")
    _require(result.is_terminal, "not_implemented interrupt should be terminal")

    closed = framework.InterruptResult.already_closed(request=request)
    _require(closed.outcome == framework.InterruptOutcome.ALREADY_CLOSED, "already_closed outcome mismatch")

    no_active = framework.InterruptResult.no_active_turn(request=request)
    _require(no_active.outcome == framework.InterruptOutcome.NO_ACTIVE_TURN, "no_active_turn outcome mismatch")
    _ok("InterruptRequest/InterruptResult contract is provider-neutral and secret-safe")


def _assert_tts_queue_and_flush_contract(framework) -> None:
    queue = framework.TTSQueueState(
        queued_count=2,
        current_item_id="item-1",
        is_playing=True,
        supports_flush=False,
        supports_provider_cancel=False,
        playback_stop_required=True,
        public_metadata={"token": "should-not-leak"},
    )
    _require(queue.queued_count == 2, "TTSQueueState queued_count mismatch")
    _require(queue.current_item_id == "item-1", "TTSQueueState current_item_id mismatch")
    _require(queue.public_metadata["token"] == "<redacted>", "TTSQueueState should redact secret-like metadata")
    _require("should-not-leak" not in repr(queue), "TTSQueueState repr should not leak secret-like metadata")

    request = framework.OutputFlushRequest(
        turn_id="turn-1",
        public_metadata={"credential": "should-not-leak"},
    )
    _require(request.scope == framework.InterruptScope.TTS_QUEUE, "OutputFlushRequest default scope mismatch")
    _require(request.stop_playback, "OutputFlushRequest should stop playback by default")
    _require(request.clear_queued_audio, "OutputFlushRequest should clear queued audio by default")
    _require(request.public_metadata["credential"] == "<redacted>", "OutputFlushRequest metadata should redact secret-like keys")

    not_impl = framework.OutputFlushResult.not_implemented(request=request)
    _require(not_impl.outcome == framework.OutputFlushOutcome.NOT_IMPLEMENTED, "flush not_implemented outcome mismatch")
    _require(not not_impl.flushed, "not_implemented flush should not be flushed")

    nothing = framework.OutputFlushResult.nothing_to_flush(request=request)
    _require(nothing.outcome == framework.OutputFlushOutcome.NOTHING_TO_FLUSH, "nothing_to_flush outcome mismatch")

    closed = framework.OutputFlushResult.closed(request=request)
    _require(closed.outcome == framework.OutputFlushOutcome.CLOSED, "closed flush outcome mismatch")
    _ok("TTSQueueState/OutputFlush contract is provider-neutral and secret-safe")


def _assert_barge_in_contract(framework) -> None:
    disabled = framework.BargeInPolicy.disabled()
    _require(disabled.mode == framework.BargeInPolicyMode.DISABLED, "disabled barge-in policy mismatch")

    soft = framework.BargeInPolicy.soft_interrupt()
    _require(soft.mode == framework.BargeInPolicyMode.SOFT_INTERRUPT, "soft interrupt policy mismatch")
    _require(soft.interrupt_scope == framework.InterruptScope.CURRENT_TURN, "soft interrupt scope mismatch")

    flush = framework.BargeInPolicy.flush_output()
    _require(flush.mode == framework.BargeInPolicyMode.FLUSH_OUTPUT, "flush output policy mismatch")
    _require(flush.flush_output, "flush output policy should flush output")

    hard = framework.BargeInPolicy.hard_cancel()
    _require(hard.mode == framework.BargeInPolicyMode.HARD_CANCEL, "hard cancel policy mismatch")
    _require(hard.cancel_current_turn, "hard cancel policy should cancel current turn")
    _require(hard.flush_output, "hard cancel policy should flush output")

    takeover = framework.BargeInPolicy.turn_takeover()
    _require(takeover.mode == framework.BargeInPolicyMode.TURN_TAKEOVER, "turn takeover policy mismatch")
    _require(takeover.allow_turn_takeover, "turn takeover policy should allow turn takeover")

    accepted = framework.BargeInDecision.accepted_for_policy(
        hard,
        turn_id="turn-1",
        public_metadata={"secret": "should-not-leak"},
    )
    _require(accepted.accepted, "hard cancel barge-in decision should be accepted")
    _require(accepted.interrupt_request is not None, "accepted decision should include interrupt request")
    _require(accepted.should_stop_output, "accepted hard cancel should stop output")
    _require(accepted.should_flush_queue, "accepted hard cancel should flush queue")
    _require(accepted.should_cancel_current_turn, "accepted hard cancel should cancel current turn")
    _require(accepted.public_metadata["secret"] == "<redacted>", "BargeInDecision should redact secret-like metadata")
    _require("should-not-leak" not in repr(accepted), "BargeInDecision repr should not leak secret-like metadata")

    rejected = framework.BargeInDecision.rejected(policy=disabled)
    _require(not rejected.accepted, "disabled barge-in decision should be rejected")
    _ok("BargeInPolicy/BargeInDecision contract is provider-neutral and secret-safe")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_interrupt_contract(framework)
    _assert_tts_queue_and_flush_contract(framework)
    _assert_barge_in_contract(framework)
    _ok("v5.2.0 public interrupt / output control types are mock-safe")


if __name__ == "__main__":
    main()
