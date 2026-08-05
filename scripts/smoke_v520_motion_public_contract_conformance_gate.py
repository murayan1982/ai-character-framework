"""v5.2.0 public motion contract conformance gate."""

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
    path = root / "docs" / "v520_motion_public_contract_conformance_gate.md"
    _require(path.exists(), "missing docs/v520_motion_public_contract_conformance_gate.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Motion Public Contract Conformance Gate",
        "MotionAdapterStatus",
        "MotionState",
        "MotionEventType",
        "MotionErrorCode",
        "MotionIntent",
        "MotionOutcome",
        "MotionCapability",
        "MotionRequest",
        "MotionResult",
        "create_motion_session",
        "MotionSession",
        "MotionSessionInfo",
        "Public import rule",
        "Type rule",
        "Session rule",
        "Host-app example rule",
        "Current limitation",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"motion conformance gate doc missing phrase: {phrase}")
    _ok("v5.2.0 motion public contract conformance gate doc is documented")


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
        "live2d",
    ]
    hits = sorted(name for name in loaded if any(fragment in name.lower() for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded motion provider modules: " + ", ".join(hits[:16]))
    _ok("framework public import stays motion/VTS provider safe")
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
        "create_motion_session",
        "MotionSession",
        "MotionSessionInfo",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")
    _ok("framework exports all public motion conformance symbols")


def _assert_factory_signature(framework) -> None:
    sig = inspect.signature(framework.create_motion_session)
    _require(sig.parameters, "create_motion_session should expose explicit parameters")
    for param in sig.parameters.values():
        _require(
            param.kind is inspect.Parameter.KEYWORD_ONLY,
            f"create_motion_session parameter should be keyword-only: {param.name}",
        )
    expected = {
        "project_root",
        "adapter",
        "real_adapter_enabled",
        "allow_provider_execution",
        "public_metadata",
    }
    _require(expected.issubset(set(sig.parameters)), "create_motion_session missing expected public parameters")
    _ok("create_motion_session signature is explicit and keyword-only")


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
        {
            "idle",
            "preparing",
            "speaking",
            "expressing",
            "gesturing",
            "interrupted",
            "failed",
            "closed",
            "unavailable",
        }.issubset(states),
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

    errors = {value.value for value in framework.MotionErrorCode}
    _require(
        {
            "none",
            "unavailable",
            "unsupported",
            "not_configured",
            "token_missing",
            "provider_execution_not_allowed",
            "runtime_not_installed",
            "model_not_selected",
            "not_implemented",
            "interrupted",
            "session_closed",
            "provider_error",
        }.issubset(errors),
        "MotionErrorCode missing expected values",
    )

    intents = {value.value for value in framework.MotionIntent}
    _require(
        {
            "expression",
            "emotion",
            "speaking_state",
            "idle_motion",
            "gesture",
            "look_at",
            "stop_motion",
            "reset_expression",
        }.issubset(intents),
        "MotionIntent missing expected values",
    )

    outcomes = {value.value for value in framework.MotionOutcome}
    _require(
        {
            "completed",
            "unsupported",
            "unavailable",
            "not_configured",
            "not_implemented",
            "interrupted",
            "failed",
            "closed",
        }.issubset(outcomes),
        "MotionOutcome missing expected values",
    )
    _ok("motion enum contracts conform")


def _assert_capability_request_result_types(framework) -> None:
    disabled = framework.MotionCapability.disabled(adapter="vts")
    _require(disabled.adapter == "vts", "disabled capability should preserve adapter")
    _require(disabled.adapter_status == framework.MotionAdapterStatus.DISABLED, "disabled capability status mismatch")
    _require(not disabled.supports_real_adapter, "disabled capability should not claim real adapter")

    mock = framework.MotionCapability.mock_available()
    _require(mock.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "mock capability status mismatch")
    _require(mock.supports_expression, "mock capability should support expression")
    _require(mock.supports_emotion, "mock capability should support emotion")
    _require(mock.supports_speaking_state, "mock capability should support speaking state")
    _require(mock.supports_stop_motion, "mock capability should support stop motion")
    _require(not mock.supports_real_adapter, "mock capability should not claim real adapter")

    expression = framework.MotionRequest.expression_change(
        "smile",
        intensity=0.6,
        duration_ms=500,
        character_id="cheerful_sora",
        public_metadata={"api_key": "should-not-leak"},
    )
    _require(expression.intent == framework.MotionIntent.EXPRESSION, "expression request intent mismatch")
    _require(expression.expression == "smile", "expression request expression mismatch")
    _require(expression.public_metadata["api_key"] == "<redacted>", "MotionRequest metadata should be redacted")
    _require("should-not-leak" not in repr(expression), "MotionRequest repr should not leak secret-like metadata")

    emotion = framework.MotionRequest.emotion_update("happy")
    _require(emotion.intent == framework.MotionIntent.EMOTION, "emotion request intent mismatch")
    speaking = framework.MotionRequest.speaking_state(True)
    _require(speaking.intent == framework.MotionIntent.SPEAKING_STATE, "speaking request intent mismatch")
    stop = framework.MotionRequest.stop_motion()
    _require(stop.intent == framework.MotionIntent.STOP_MOTION, "stop request intent mismatch")

    completed = framework.MotionResult.completed(request=expression, session_id="motion-session")
    _require(type(completed.session_id) is str, "legacy MotionResult session_id should remain str")
    typed_session_text = str(framework.SessionId.new())
    typed_completed = framework.MotionResult.completed(
        request=expression,
        session_id=typed_session_text,
    )
    _require(
        isinstance(typed_completed.session_id, framework.SessionId),
        "serialized SessionId should normalize on MotionResult",
    )
    try:
        framework.MotionResult.completed(
            request=expression,
            session_id=str(framework.TurnId.new()),
        )
    except ValueError:
        pass
    else:
        raise ContractFailure("wrong-kind TurnId was accepted as motion session_id")
    _require(completed.outcome == framework.MotionOutcome.COMPLETED, "completed result outcome mismatch")
    _require(completed.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "completed result adapter status mismatch")
    _require(completed.is_completed, "completed result should be completed")
    _require(completed.is_terminal, "completed result should be terminal")
    _require(completed.request_id == expression.request_id, "completed result should preserve request id")

    unavailable = framework.MotionResult.unavailable(
        request=expression,
        adapter_status=framework.MotionAdapterStatus.TOKEN_MISSING,
        public_error_code=framework.MotionErrorCode.TOKEN_MISSING,
        public_metadata={"secret": "should-not-leak"},
    )
    _require(unavailable.outcome == framework.MotionOutcome.UNAVAILABLE, "unavailable result outcome mismatch")
    _require(unavailable.adapter_status == framework.MotionAdapterStatus.TOKEN_MISSING, "unavailable status mismatch")
    _require(unavailable.public_error_code == framework.MotionErrorCode.TOKEN_MISSING, "unavailable error code mismatch")
    _require(unavailable.public_metadata["secret"] == "<redacted>", "MotionResult metadata should be redacted")
    _require("should-not-leak" not in repr(unavailable), "MotionResult repr should not leak secret-like metadata")

    not_impl = framework.MotionResult.not_implemented(request=expression)
    _require(not_impl.outcome == framework.MotionOutcome.NOT_IMPLEMENTED, "not_implemented result outcome mismatch")
    _require(not_impl.adapter_status == framework.MotionAdapterStatus.NOT_IMPLEMENTED, "not_implemented status mismatch")
    _require(not_impl.public_error_code == framework.MotionErrorCode.NOT_IMPLEMENTED, "not_implemented error code mismatch")

    closed = framework.MotionResult.closed(request=expression, session_id="motion-session")
    _require(closed.outcome == framework.MotionOutcome.CLOSED, "closed result outcome mismatch")
    _require(closed.public_error_code == framework.MotionErrorCode.SESSION_CLOSED, "closed result error code mismatch")
    _ok("motion capability/request/result types conform")


def _assert_motion_session_contract(framework) -> None:
    events = []
    session = framework.create_motion_session(public_metadata={"token": "should-not-leak"})
    session.on_event(events.append)

    _require(isinstance(session.info, framework.MotionSessionInfo), "session.info should be MotionSessionInfo")
    _require(
        isinstance(session.info.session_id, framework.SessionId),
        "Framework-generated motion session_id should be SessionId",
    )
    _require(session.info.session_type == "motion", "MotionSessionInfo session_type mismatch")
    _require(session.info.adapter == "mock", "default motion adapter should be mock")
    _require(session.info.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "default adapter status mismatch")
    _require(session.info.capability.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "info capability status mismatch")
    _require(session.info.supports_expression, "session should support expression in mock mode")
    _require(session.info.supports_speaking_state, "session should support speaking state in mock mode")
    _require(not session.info.real_adapter_enabled, "session should not enable real adapter by default")
    _require(not session.info.real_adapter_supported, "session should not claim real adapter support")
    _require(session.info.public_metadata["token"] == "<redacted>", "MotionSessionInfo metadata should be redacted")
    _require(not session.is_closed, "new MotionSession should be open")
    _require(session.state == framework.MotionState.IDLE, "new MotionSession should be idle")

    created = session.emit_created()
    _require(created["type"] == "motion.session.created", "emit_created event type mismatch")

    capability = session.preflight()
    _require(capability.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "preflight status mismatch")
    _require(events[-1]["type"] == "motion.adapter.preflight.completed", "preflight should emit event")

    request = framework.MotionRequest.expression_change("smile", public_metadata={"password": "should-not-leak"})
    result = session.apply_motion(request)
    _require(result.outcome == framework.MotionOutcome.COMPLETED, "mock apply_motion should complete")
    _require(result.adapter_status == framework.MotionAdapterStatus.MOCK_AVAILABLE, "mock apply_motion status mismatch")
    _require(result.request_id == request.request_id, "mock apply_motion should preserve request id")
    _require(result.session_id == session.info.session_id, "mock apply_motion should include session id")
    _require(
        isinstance(result.session_id, framework.SessionId),
        "mock MotionResult session_id should preserve SessionId",
    )
    _require(result.public_metadata["mock_motion"], "mock apply_motion should mark mock motion")
    _require(session.state == framework.MotionState.IDLE, "session should return to idle after mock motion")
    _require("should-not-leak" not in repr(result), "MotionResult should not leak secret-like metadata")

    event_types = [event["type"] for event in events]
    _require("motion.session.created" in event_types, "motion session should emit created")
    _require("motion.adapter.preflight.completed" in event_types, "motion session should emit preflight")
    _require("motion.requested" in event_types, "motion session should emit requested")
    _require("motion.started" in event_types, "motion session should emit started")
    _require("motion.completed" in event_types, "motion session should emit completed")
    _require(
        all(event["session_id"] == str(session.info.session_id) for event in events),
        "events should include JSON-safe session_id",
    )
    _require(
        all(type(event["session_id"]) is str for event in events),
        "motion callback session_id should be plain JSON string",
    )
    _ok("MotionSession mock public contract conforms")


def _assert_motion_session_guard_and_closed(framework) -> None:
    guarded = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=False,
        public_metadata={"secret": "should-not-leak"},
    )
    guard_result = guarded.apply_motion(framework.MotionRequest.expression_change("smile"))
    _require(guarded.info.adapter == "vts", "guarded session should preserve adapter")
    _require(guarded.info.real_adapter_enabled, "guarded session should show real adapter enabled flag")
    _require(not guarded.info.real_adapter_supported, "guarded session should not claim real adapter support")
    _require(
        guard_result.adapter_status == framework.MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
        "guarded result adapter status mismatch",
    )
    _require(
        guard_result.public_error_code == framework.MotionErrorCode.PROVIDER_EXECUTION_NOT_ALLOWED,
        "guarded result error code mismatch",
    )
    _require("should-not-leak" not in repr(guarded.info), "guarded info should not leak secret-like metadata")

    real_not_impl = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=True,
    )
    not_impl_result = real_not_impl.apply_motion(framework.MotionRequest.speaking_state(True))
    _require(not_impl_result.outcome == framework.MotionOutcome.NOT_IMPLEMENTED, "real adapter should be not_implemented")
    _require(not_impl_result.adapter_status == framework.MotionAdapterStatus.NOT_IMPLEMENTED, "real adapter status mismatch")

    unsupported = framework.create_motion_session(adapter="unknown")
    unsupported_result = unsupported.apply_motion(framework.MotionRequest.stop_motion())
    _require(unsupported_result.outcome == framework.MotionOutcome.UNAVAILABLE, "unsupported adapter should be unavailable")
    _require(unsupported_result.adapter_status == framework.MotionAdapterStatus.UNSUPPORTED_ADAPTER, "unsupported status mismatch")
    _require(unsupported_result.public_error_code == framework.MotionErrorCode.UNSUPPORTED, "unsupported error code mismatch")

    session = framework.create_motion_session()
    session.close()
    session.dispose()
    _require(session.is_closed, "MotionSession should be closed after close/dispose")
    _require(session.state == framework.MotionState.CLOSED, "closed MotionSession state mismatch")
    closed_result = session.apply_motion(framework.MotionRequest.expression_change("smile"))
    _require(closed_result.outcome == framework.MotionOutcome.CLOSED, "closed session apply_motion should return closed")
    _require(closed_result.public_error_code == framework.MotionErrorCode.SESSION_CLOSED, "closed session error code mismatch")

    with framework.create_motion_session() as managed:
        _require(not managed.is_closed, "managed MotionSession should be open inside context")
    _require(managed.is_closed, "managed MotionSession should close on context exit")
    _ok("MotionSession guard/not-implemented/unsupported/closed behavior conforms")


def _assert_host_app_examples(root: Path) -> None:
    examples = [
        root / "examples" / "app_motion_session_expression_flow.py",
        root / "examples" / "app_motion_adapter_preflight.py",
        root / "examples" / "app_motion_closed_session_behavior.py",
        root / "examples" / "app_motion_real_adapter_guard.py",
    ]
    forbidden_phrases = [
        "from live2d",
        "import live2d",
        "from vts",
        "import vts",
        "from plugins",
        "import websocket",
        "import websockets",
        "sys.path",
        "chdir(",
        "TOKEN =",
        "VTS_TOKEN =",
        "MODEL_PATH =",
    ]

    for path in examples:
        _require(path.exists(), f"missing host-app example: {path.relative_to(root)}")
        text = path.read_text(encoding="utf-8", errors="replace")
        _require("import framework" in text, f"{path.name} should use public framework import")
        for phrase in forbidden_phrases:
            _require(phrase not in text, f"{path.name} contains forbidden phrase: {phrase}")

    _ok("motion host-app examples conform to public-only rule")


def _assert_readme(root: Path) -> None:
    path = root / "README.md"
    _require(path.exists(), "missing README.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_links = [
        "v520_motion_live2d_vts_adapter_inventory.md",
        "v520_motion_adapter_types.md",
        "v520_motion_session_skeleton.md",
        "v520_motion_host_app_examples.md",
        "v520_motion_public_contract_conformance_gate.md",
    ]
    for link in required_links:
        _require(link in text, f"README missing v5.2.0 motion link: {link}")
    _ok("README links public motion contract docs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _import_framework_safely(root)
    _assert_public_exports(framework)
    _assert_factory_signature(framework)
    _assert_enum_contracts(framework)
    _assert_capability_request_result_types(framework)
    _assert_motion_session_contract(framework)
    _assert_motion_session_guard_and_closed(framework)
    _assert_host_app_examples(root)
    _assert_readme(root)
    _ok("v5.2.0 public motion contract conformance gate passed")


if __name__ == "__main__":
    main()
