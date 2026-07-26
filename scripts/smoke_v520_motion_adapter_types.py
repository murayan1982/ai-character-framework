"""v5.2.0 public motion adapter type smoke."""

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
    path = root / "docs" / "v520_motion_adapter_types.md"
    _require(path.exists(), "missing docs/v520_motion_adapter_types.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Public Motion Adapter Types",
        "MotionAdapterStatus",
        "MotionState",
        "MotionEventType",
        "MotionErrorCode",
        "MotionIntent",
        "MotionOutcome",
        "MotionCapability",
        "MotionRequest",
        "MotionResult",
        "token_missing",
        "provider_execution_not_allowed",
        "motion.session.created",
        "expression",
        "emotion",
        "speaking_state",
        "stop_motion",
        "supports_real_adapter",
        "Safety rules",
        "Import safety",
        "create_motion_session",
        "MotionSession",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"motion adapter type doc missing phrase: {phrase}")
    _ok("v5.2.0 public motion adapter type doc is documented")


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
        "vtube",
        "vts",
        "live2d",
    ]
    hits = sorted(name for name in loaded if any(fragment in name.lower() for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded motion/VTS/provider modules: " + ", ".join(hits[:16]))
    _ok("public motion adapter type import stays provider/internal safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "MotionAdapterStatus",
        "MotionState",
        "MotionEventType",
        "MotionErrorCode",
        "MotionIntent",
        "MotionOutcome",
        "MotionCapability",
        "MotionRequest",
        "MotionResult",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")
    _ok("framework exports public motion adapter types")


def _assert_enum_contracts(framework) -> None:
    statuses = {value.value for value in framework.MotionAdapterStatus}
    _require(
        {
            "disabled",
            "mock_available",
            "not_configured",
            "token_missing",
            "provider_execution_not_allowed",
            "runtime_not_installed",
            "model_not_selected",
            "not_implemented",
            "unsupported_adapter",
            "closed",
        }.issubset(statuses),
        "MotionAdapterStatus missing expected values",
    )

    states = {value.value for value in framework.MotionState}
    _require(
        {"idle", "preparing", "speaking", "expressing", "gesturing", "interrupted", "failed", "closed", "unavailable"}.issubset(states),
        "MotionState missing expected values",
    )

    events = {value.value for value in framework.MotionEventType}
    _require(
        {
            "motion.session.created",
            "motion.adapter.preflight.completed",
            "motion.requested",
            "motion.started",
            "motion.completed",
            "motion.interrupted",
            "motion.failed",
            "motion.unsupported",
            "motion.session.closed",
        }.issubset(events),
        "MotionEventType missing expected values",
    )

    intents = {value.value for value in framework.MotionIntent}
    _require(
        {"expression", "emotion", "speaking_state", "idle_motion", "gesture", "look_at", "stop_motion", "reset_expression"}.issubset(intents),
        "MotionIntent missing expected values",
    )

    outcomes = {value.value for value in framework.MotionOutcome}
    _require(
        {"completed", "unsupported", "unavailable", "not_configured", "not_implemented", "interrupted", "failed", "closed"}.issubset(outcomes),
        "MotionOutcome missing expected values",
    )
    _ok("motion adapter enum contracts conform")


def _assert_capability_contract(framework) -> None:
    disabled = framework.MotionCapability.disabled(adapter="vts")
    _require(disabled.adapter == "vts", "disabled capability should preserve adapter")
    _require(disabled.adapter_status == framework.MotionAdapterStatus.DISABLED, "disabled capability status mismatch")
    _require(disabled.supports_motion_session, "motion session boundary should be supported")
    _require(disabled.supports_mock_motion, "mock motion boundary should be supported")
    _require(not disabled.supports_real_adapter, "disabled capability should not claim real adapter")

    mock = framework.MotionCapability.mock_available()
    _require(mock.adapter == "mock", "mock capability adapter mismatch")
    _require(mock.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "mock capability status mismatch")
    _require(mock.supports_expression, "mock capability should support expression")
    _require(mock.supports_emotion, "mock capability should support emotion")
    _require(mock.supports_speaking_state, "mock capability should support speaking state")
    _require(mock.supports_stop_motion, "mock capability should support stop motion")
    _require(not mock.supports_real_adapter, "mock capability should not claim real adapter")
    _ok("MotionCapability contract is provider-neutral and honest")


def _assert_request_contract(framework) -> None:
    expression = framework.MotionRequest.expression_change(
        "smile",
        intensity=0.75,
        duration_ms=1200,
        character_id="sora",
        public_metadata={"api_key": "should-not-leak"},
    )
    _require(expression.intent == framework.MotionIntent.EXPRESSION, "expression request intent mismatch")
    _require(expression.expression == "smile", "expression request should preserve expression")
    _require(expression.intensity == 0.75, "expression request should preserve intensity")
    _require(expression.duration_ms == 1200, "expression request should preserve duration")
    _require(expression.public_metadata["api_key"] == "<redacted>", "MotionRequest should redact secret-like metadata")
    _require("should-not-leak" not in repr(expression), "MotionRequest repr should not leak secret-like metadata")

    emotion = framework.MotionRequest.emotion_update("happy", intensity=0.5)
    _require(emotion.intent == framework.MotionIntent.EMOTION, "emotion request intent mismatch")
    _require(emotion.emotion == "happy", "emotion request should preserve emotion")

    speaking = framework.MotionRequest.speaking_state(True)
    _require(speaking.intent == framework.MotionIntent.SPEAKING_STATE, "speaking request intent mismatch")
    _require(speaking.speaking is True, "speaking request should preserve state")

    stop = framework.MotionRequest.stop_motion()
    _require(stop.intent == framework.MotionIntent.STOP_MOTION, "stop motion request intent mismatch")
    _ok("MotionRequest contract is provider-neutral and secret-safe")


def _assert_result_contract(framework) -> None:
    request = framework.MotionRequest.expression_change("smile", public_metadata={"token": "should-not-leak"})

    completed = framework.MotionResult.completed(request=request, session_id="motion-session")
    _require(completed.outcome == framework.MotionOutcome.COMPLETED, "completed motion outcome mismatch")
    _require(completed.state == framework.MotionState.IDLE, "completed motion state mismatch")
    _require(completed.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "completed adapter status mismatch")
    _require(completed.is_completed, "completed motion result should be completed")
    _require(completed.is_terminal, "completed motion result should be terminal")
    _require(completed.request_id == request.request_id, "completed motion result should preserve request_id")

    unavailable = framework.MotionResult.unavailable(
        request=request,
        adapter_status=framework.MotionAdapterStatus.TOKEN_MISSING,
        public_error_code=framework.MotionErrorCode.TOKEN_MISSING,
        public_metadata={"secret": "should-not-leak"},
    )
    _require(unavailable.outcome == framework.MotionOutcome.UNAVAILABLE, "unavailable motion outcome mismatch")
    _require(unavailable.adapter_status == framework.MotionAdapterStatus.TOKEN_MISSING, "unavailable adapter status mismatch")
    _require(unavailable.public_error_code == framework.MotionErrorCode.TOKEN_MISSING, "unavailable error code mismatch")
    _require(unavailable.public_metadata["secret"] == "<redacted>", "MotionResult should redact secret-like metadata")
    _require("should-not-leak" not in repr(unavailable), "MotionResult repr should not leak secret-like metadata")

    not_impl = framework.MotionResult.not_implemented(request=request)
    _require(not_impl.outcome == framework.MotionOutcome.NOT_IMPLEMENTED, "not implemented outcome mismatch")
    _require(not_impl.adapter_status == framework.MotionAdapterStatus.NOT_IMPLEMENTED, "not implemented adapter status mismatch")
    _require(not_impl.public_error_code == framework.MotionErrorCode.NOT_IMPLEMENTED, "not implemented error code mismatch")

    closed = framework.MotionResult.closed(request=request, session_id="motion-session")
    _require(closed.outcome == framework.MotionOutcome.CLOSED, "closed motion outcome mismatch")
    _require(closed.state == framework.MotionState.CLOSED, "closed motion state mismatch")
    _require(closed.public_error_code == framework.MotionErrorCode.SESSION_CLOSED, "closed motion error code mismatch")
    _ok("MotionResult contract is provider-neutral and secret-safe")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_enum_contracts(framework)
    _assert_capability_contract(framework)
    _assert_request_contract(framework)
    _assert_result_contract(framework)
    _ok("v5.2.0 public motion adapter types are mock-safe")


if __name__ == "__main__":
    main()
