"""Provider-free tests for FW-RT6-4a Control C runtime guard adoption."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

import framework
from framework.lifecycle import RecoveryAction, TurnOutcome
from framework.realtime import RealtimeErrorCode, RealtimeEventType, RealtimeState, RealtimeTurn
from framework.realtime_capabilities import RuntimeCapabilityState, TextGenerationCapability
from framework.realtime_session_config import (
    RealtimeSessionConfig,
    RealtimeSessionConstructionStatus,
)
from framework.realtime_stage import RealtimeStageKind


def _real_text_capability() -> TextGenerationCapability:
    return TextGenerationCapability(
        runtime=RuntimeCapabilityState(
            configured=True,
            runtime_available=True,
            guarded=False,
            fake_runtime=False,
            real_runtime=True,
            unavailable_reason=None,
            public_metadata={"provider_execution_performed": False},
        ),
        streaming_supported=True,
        cooperative_cancel_supported=True,
        provider_hard_cancel_supported=False,
    )


class _TextStage:
    stage_kind = RealtimeStageKind.TEXT_GENERATION

    def __init__(self, *, preflight_error: Exception | None = None) -> None:
        self.preflight_error = preflight_error
        self.calls: list[str] = []

    def preflight(self) -> TextGenerationCapability:
        self.calls.append("preflight")
        if self.preflight_error is not None:
            raise self.preflight_error
        return _real_text_capability()

    def capability(self) -> TextGenerationCapability:
        self.calls.append("capability")
        raise AssertionError("capability refresh must not run in FW-RT6-4a")

    def start(self, *, context: object, request: object) -> object:
        self.calls.append("start")
        raise AssertionError("real stage execution must not run in FW-RT6-4a")

    def cancel(self, *, context: object) -> bool:
        self.calls.append("cancel")
        raise AssertionError("stage cancellation must not run in FW-RT6-4a")

    def close(self) -> None:
        self.calls.append("close")


class RealtimeSessionConstructionRuntimeGuardTests(unittest.TestCase):
    def test_construction_result_is_public_read_only_and_correlated(self) -> None:
        session = framework.create_realtime_session()

        self.assertIs(session.construction_result, session._construction_result)
        self.assertEqual(session.construction_result.session_id, session.info.session_id)
        self.assertIs(
            session.construction_result.status,
            RealtimeSessionConstructionStatus.MOCK_READY,
        )
        with self.assertRaises((AttributeError, FrozenInstanceError)):
            session.construction_result.status = "preflight_failed"  # type: ignore[misc]

    def test_default_mock_run_turn_remains_completed(self) -> None:
        session = framework.create_realtime_session()

        result = session.run_turn(input_text="mock remains accepted")

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertIs(result.public_error_code, RealtimeErrorCode.NONE)
        self.assertTrue(result.public_metadata["mock_runtime"])
        self.assertIs(session.state, RealtimeState.IDLE)
        self.assertFalse(session.construction_result.real_runtime_requested)

    def test_real_request_missing_text_stage_is_configuration_rejection(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)

        result = session.run_turn(input_text="must not use mock fallback")

        self.assertIs(
            session.construction_result.status,
            RealtimeSessionConstructionStatus.CONFIGURATION_INCOMPLETE,
        )
        self.assertIs(result.outcome, TurnOutcome.REJECTED)
        self.assertIs(result.public_error_code, RealtimeErrorCode.CONFIGURATION_MISSING)
        self.assertIs(result.recovery_action, RecoveryAction.REUSE_SESSION)
        self.assertFalse(result.public_metadata["mock_runtime"])
        self.assertEqual(
            result.public_metadata["reason"],
            "real_runtime_configuration_missing",
        )
        self.assertIs(session.state, RealtimeState.IDLE)

    def test_real_request_preflight_failure_is_unavailable_rejection(self) -> None:
        stage = _TextStage(preflight_error=RuntimeError("private provider detail"))
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                text_generation_stage=stage,
            )
        )

        result = session.run_turn(input_text="preflight failed")

        self.assertIs(
            session.construction_result.status,
            RealtimeSessionConstructionStatus.PREFLIGHT_FAILED,
        )
        self.assertIs(result.outcome, TurnOutcome.REJECTED)
        self.assertIs(result.public_error_code, RealtimeErrorCode.UNAVAILABLE)
        self.assertTrue(result.retryable)
        self.assertNotIn("private provider detail", result.safe_message)
        self.assertEqual(stage.calls, ["preflight"])

    def test_real_configuration_ready_rejects_unimplemented_orchestration(self) -> None:
        stage = _TextStage()
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                text_generation_stage=stage,
            )
        )

        result = session.run_turn(input_text="real configuration only")

        self.assertIs(
            session.construction_result.status,
            RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY,
        )
        self.assertFalse(session.construction_result.runtime_executable)
        self.assertIs(result.outcome, TurnOutcome.REJECTED)
        self.assertIs(result.public_error_code, RealtimeErrorCode.UNAVAILABLE)
        self.assertEqual(
            result.public_metadata["reason"],
            "real_runtime_orchestration_not_available",
        )
        self.assertEqual(stage.calls, ["preflight"])

    def test_real_rejection_emits_only_terminal_rejection_not_mock_lifecycle(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)

        result = session.run_turn(input_text="no mock lifecycle")
        history = session.event_history

        self.assertEqual(len(history), 1)
        event = history[0]
        self.assertIs(event.type, RealtimeEventType.TURN_REJECTED)
        self.assertIs(event.public_error_code, result.public_error_code)
        self.assertEqual(event.safe_message, result.safe_message)
        self.assertFalse(event.public_metadata["mock_runtime"])
        self.assertNotIn(RealtimeEventType.TURN_STARTED, tuple(item.type for item in history))
        self.assertNotIn(RealtimeEventType.SYNTHESIS_COMPLETED, tuple(item.type for item in history))

    def test_real_rejection_commits_exactly_one_terminal_result(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)
        turn = RealtimeTurn(input_text="same turn")

        first = session.run_turn(turn)
        second = session.run_turn(turn)

        self.assertIs(first, second)
        self.assertEqual(session.terminal_results, (first,))
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)
        self.assertEqual(session.terminal_diagnostics["duplicate_terminal_count"], 1)
        self.assertEqual(len(session.event_history), 1)

    def test_real_rejection_does_not_start_generation_or_stage(self) -> None:
        stage = _TextStage()
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                text_generation_stage=stage,
            )
        )
        before = dict(session.generation_diagnostics)

        session.run_turn(input_text="no generation")

        after = dict(session.generation_diagnostics)
        self.assertEqual(before, after)
        self.assertEqual(stage.calls, ["preflight"])

    def test_real_rejection_is_session_reusable_for_later_rejection(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)

        first = session.run_turn(input_text="first")
        second = session.run_turn(input_text="second")

        self.assertIs(first.outcome, TurnOutcome.REJECTED)
        self.assertIs(second.outcome, TurnOutcome.REJECTED)
        self.assertNotEqual(first.turn_id, second.turn_id)
        self.assertEqual(len(session.terminal_results), 2)
        self.assertIs(session.state, RealtimeState.IDLE)

    def test_real_rejection_preserves_public_safe_metadata(self) -> None:
        session = framework.create_realtime_session(
            real_runtime_enabled=True,
            public_metadata={"host": "test-host"},
        )

        result = session.run_turn(
            input_text="metadata",
            public_metadata={"request": "ignored-for-rejection"},
        )

        self.assertEqual(result.public_metadata["boundary"], "realtime")
        self.assertTrue(result.public_metadata["real_runtime_requested"])
        self.assertFalse(result.public_metadata["real_runtime_enabled"])
        self.assertFalse(result.public_metadata["provider_execution_performed"])
        self.assertEqual(
            result.public_metadata["construction_status"],
            RealtimeSessionConstructionStatus.CONFIGURATION_INCOMPLETE.value,
        )


if __name__ == "__main__":
    unittest.main()
