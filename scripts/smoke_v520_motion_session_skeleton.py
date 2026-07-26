"""v5.2.0 public motion session skeleton smoke."""

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
    path = root / "docs" / "v520_motion_session_skeleton.md"
    _require(path.exists(), "missing docs/v520_motion_session_skeleton.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Public Motion Session Skeleton",
        "create_motion_session",
        "MotionSession",
        "MotionSessionInfo",
        "apply_motion",
        "preflight",
        "emit_created",
        "close()",
        "dispose()",
        "context manager support",
        "motion.session.created",
        "motion.adapter.preflight.completed",
        "motion.requested",
        "motion.completed",
        "adapter_status=mock_available",
        "Import safety",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"motion session skeleton doc missing phrase: {phrase}")
    _ok("v5.2.0 public motion session skeleton doc is documented")


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
    _ok("public motion session import stays provider/internal safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "create_motion_session",
        "MotionSession",
        "MotionSessionInfo",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")

    sig = inspect.signature(framework.create_motion_session)
    _require(sig.parameters, "create_motion_session should expose explicit parameters")
    _require(all(param.kind is inspect.Parameter.KEYWORD_ONLY for param in sig.parameters.values()), "create_motion_session should be keyword-only")
    _ok("framework exports public motion session symbols")


def _assert_session_info_and_preflight(framework) -> None:
    session = framework.create_motion_session(public_metadata={"token": "should-not-leak"})
    _require(isinstance(session.info, framework.MotionSessionInfo), "session.info should be MotionSessionInfo")
    _require(session.info.session_type == "motion", "MotionSessionInfo session_type mismatch")
    _require(session.info.adapter == "mock", "default motion adapter should be mock")
    _require(session.info.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "default adapter status should be mock_available")
    _require(session.info.capability.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "info capability status mismatch")
    _require(session.info.supports_expression, "mock motion should support expression")
    _require(session.info.supports_speaking_state, "mock motion should support speaking state")
    _require(not session.info.real_adapter_enabled, "mock motion should not enable real adapter")
    _require(not session.info.real_adapter_supported, "mock motion should not claim real adapter support")
    _require(session.info.public_metadata["token"] == "<redacted>", "MotionSessionInfo should redact secret-like metadata")
    _require("should-not-leak" not in repr(session.info), "MotionSessionInfo repr should not leak secret-like metadata")

    events = []
    session.on_event(events.append)
    capability = session.preflight()
    _require(capability.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "preflight capability mismatch")
    _require(events[-1]["type"] == "motion.adapter.preflight.completed", "preflight should emit completed event")
    _ok("MotionSessionInfo and preflight are provider-neutral and secret-safe")


def _assert_mock_apply_motion(framework) -> None:
    events = []
    session = framework.create_motion_session()
    session.on_event(events.append)

    created = session.emit_created()
    _require(created["type"] == "motion.session.created", "emit_created event type mismatch")

    request = framework.MotionRequest.expression_change(
        "smile",
        intensity=0.5,
        public_metadata={"api_key": "should-not-leak"},
    )
    result = session.apply_motion(request)

    _require(result.outcome == framework.MotionOutcome.COMPLETED, "mock apply_motion should complete")
    _require(result.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "mock result adapter status mismatch")
    _require(result.request_id == request.request_id, "mock result should preserve request id")
    _require(result.session_id == session.info.session_id, "mock result should include session id")
    _require(result.public_metadata["mock_motion"], "mock result should mark mock_motion")
    _require(session.state == framework.MotionState.IDLE, "mock session should return to idle")
    _require("should-not-leak" not in repr(result), "mock motion result should not leak secret-like metadata")

    event_types = [event["type"] for event in events]
    _require(
        event_types == [
            "motion.session.created",
            "motion.requested",
            "motion.started",
            "motion.completed",
        ],
        "mock motion event order mismatch",
    )
    _require(all(event["session_id"] == session.info.session_id for event in events), "events should include session_id")
    _ok("MotionSession.apply_motion completes mock requests safely")


def _assert_real_adapter_not_implemented(framework) -> None:
    events = []
    session = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=True,
        public_metadata={"secret": "should-not-leak"},
    )
    session.on_event(events.append)

    request = framework.MotionRequest.speaking_state(True)
    result = session.apply_motion(request)

    _require(session.info.adapter == "vts", "real adapter session should preserve adapter")
    _require(not session.info.real_adapter_supported, "real adapter should not be supported yet")
    _require(result.outcome == framework.MotionOutcome.NOT_IMPLEMENTED, "real adapter should report not_implemented")
    _require(result.adapter_status == framework.MotionAdapterStatus.NOT_IMPLEMENTED, "real adapter status should be not_implemented")
    _require(result.public_error_code == framework.MotionErrorCode.NOT_IMPLEMENTED, "real adapter error code mismatch")
    _require(events[-1]["type"] == "motion.unsupported", "real adapter not implemented should emit unsupported")
    _require("should-not-leak" not in repr(session.info), "real adapter info should not leak secret-like metadata")
    _ok("MotionSession real adapter path does not overclaim readiness")


def _assert_provider_execution_guard(framework) -> None:
    session = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=False,
    )
    result = session.apply_motion(framework.MotionRequest.expression_change("smile"))
    _require(result.outcome == framework.MotionOutcome.UNAVAILABLE, "provider guard should return unavailable")
    _require(
        result.adapter_status == framework.MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
        "provider guard adapter status mismatch",
    )
    _require(
        result.public_error_code == framework.MotionErrorCode.PROVIDER_EXECUTION_NOT_ALLOWED,
        "provider guard error code mismatch",
    )
    _ok("MotionSession respects provider execution guard")


def _assert_unsupported_and_closed(framework) -> None:
    unsupported = framework.create_motion_session(adapter="unknown")
    result = unsupported.apply_motion(framework.MotionRequest.stop_motion())
    _require(result.outcome == framework.MotionOutcome.UNAVAILABLE, "unsupported adapter should return unavailable")
    _require(result.adapter_status == framework.MotionAdapterStatus.UNSUPPORTED_ADAPTER, "unsupported adapter status mismatch")
    _require(result.public_error_code == framework.MotionErrorCode.UNSUPPORTED, "unsupported adapter error code mismatch")

    events = []
    session = framework.create_motion_session()
    session.on_event(events.append)
    session.close()
    session.dispose()
    _require(session.is_closed, "MotionSession should be closed after close/dispose")
    _require(session.state == framework.MotionState.CLOSED, "MotionSession state should be closed after close")
    _require(events[-1]["type"] == "motion.session.closed", "close should emit motion.session.closed")

    closed = session.apply_motion(framework.MotionRequest.expression_change("smile"))
    _require(closed.outcome == framework.MotionOutcome.CLOSED, "closed session apply_motion should return closed")
    _require(closed.public_error_code == framework.MotionErrorCode.SESSION_CLOSED, "closed session error code mismatch")
    _ok("MotionSession unsupported and closed behavior is provider-neutral")


def _assert_context_manager(framework) -> None:
    with framework.create_motion_session() as session:
        _require(not session.is_closed, "MotionSession should be open inside context")
    _require(session.is_closed, "MotionSession context manager should close on exit")
    _require(session.state == framework.MotionState.CLOSED, "MotionSession context manager should set closed state")
    _ok("MotionSession context manager closes on exit")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_session_info_and_preflight(framework)
    _assert_mock_apply_motion(framework)
    _assert_real_adapter_not_implemented(framework)
    _assert_provider_execution_guard(framework)
    _assert_unsupported_and_closed(framework)
    _assert_context_manager(framework)
    _ok("v5.2.0 public motion session skeleton is mock-safe")


if __name__ == "__main__":
    main()
