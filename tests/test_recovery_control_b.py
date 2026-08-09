"""Provider-free tests for FW-RT6-10a Control B reset execution."""

from __future__ import annotations

from inspect import signature
import sys
from threading import Event, Thread
import unittest

import framework
from framework.lifecycle import RecoveryAction
from framework.realtime import (
    RealtimeEventType,
    RealtimeState,
    RealtimeTurn,
    RealtimeTurnResult,
)
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    RealtimeStageCompletionEnvelope,
)
from framework.recovery_control import (
    RecoveryResetErrorCode,
    RecoveryResetOutcome,
    RecoveryResetScope,
    build_recovery_control_plan,
)


class RecoveryControlBTests(unittest.TestCase):
    def _session_and_turn(self):
        session = framework.create_realtime_session()
        turn = RealtimeTurn(session_id=session.info.session_id, input_text="hello")
        started = session.start_turn(turn)
        self.assertTrue(started.accepted)
        self.assertIsNotNone(started.generation_id)
        return session, turn, started.generation_id

    def test_reset_requires_exact_control_plan(self) -> None:
        session = framework.create_realtime_session()
        with self.assertRaisesRegex(TypeError, "RecoveryControlPlan"):
            session.reset(object())  # type: ignore[arg-type]

    def test_non_reset_dispositions_are_typed_and_side_effect_free(self) -> None:
        session, _turn, generation_id = self._session_and_turn()
        before = dict(session.generation_diagnostics)
        expected = {
            RecoveryAction.REUSE_SESSION: RecoveryResetOutcome.NOT_REQUIRED,
            RecoveryAction.RECONNECT: RecoveryResetOutcome.RECONNECT_REQUIRED,
            RecoveryAction.CLOSE_SESSION: RecoveryResetOutcome.CLOSE_REQUIRED,
            RecoveryAction.PERMANENT_FAILURE: (
                RecoveryResetOutcome.PERMANENTLY_FAILED
            ),
        }

        for action, outcome in expected.items():
            plan = build_recovery_control_plan(action)
            result = session.reset(plan)
            self.assertIs(result.plan, plan)
            self.assertIs(result.outcome, outcome)
            self.assertFalse(result.generation_advanced)
            self.assertIsNone(result.previous_generation_id)
            self.assertIsNone(result.current_generation_id)

        self.assertEqual(dict(session.generation_diagnostics), before)
        self.assertEqual(session._generation_gate.current_generation_id, generation_id)

    def test_turn_reset_rebinds_exact_active_turn_to_one_new_generation(self) -> None:
        session, turn, previous = self._session_and_turn()
        session_id = session.info.session_id
        plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)

        result = session.reset(plan)

        self.assertIs(result.plan, plan)
        self.assertIs(result.outcome, RecoveryResetOutcome.APPLIED)
        self.assertIs(result.plan.reset_scope, RecoveryResetScope.TURN_ONLY)
        self.assertEqual(result.previous_generation_id, previous)
        self.assertNotEqual(result.current_generation_id, previous)
        self.assertTrue(result.generation_advanced)
        self.assertEqual(session.info.session_id, session_id)
        self.assertFalse(session.is_closed)
        replay = session.start_turn(turn)
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.generation_id, result.current_generation_id)

    def test_session_reset_uses_same_owner_and_retains_explicit_scope(self) -> None:
        session, turn, previous = self._session_and_turn()
        gate = session._generation_gate
        plan = build_recovery_control_plan(RecoveryAction.RESET_SESSION)

        result = session.reset(plan)

        self.assertIs(session._generation_gate, gate)
        self.assertIs(result.plan.reset_scope, RecoveryResetScope.SESSION)
        self.assertEqual(result.previous_generation_id, previous)
        self.assertEqual(
            session.start_turn(turn).generation_id,
            result.current_generation_id,
        )

    def test_reset_retires_old_completion_and_accepts_replacement(self) -> None:
        session, turn, previous = self._session_and_turn()
        plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)
        result = session.reset(plan)
        delivered: list[str] = []

        stale = session._apply_stage_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=turn.turn_id,
                generation_id=previous,
                stage="recovery_old_completion",
                value="old",
            ),
            deliver=delivered.append,
        )
        current = session._apply_stage_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=turn.turn_id,
                generation_id=result.current_generation_id,
                stage="recovery_current_completion",
                value="current",
            ),
            deliver=delivered.append,
        )

        self.assertFalse(stale.accepted)
        self.assertIs(stale.retired_by, GenerationAdvanceReason.RESET)
        self.assertTrue(current.accepted)
        self.assertEqual(delivered, ["current"])

    def test_reset_updates_existing_generation_diagnostics_without_new_keys(self) -> None:
        session, _turn, _previous = self._session_and_turn()
        keys = {
            "generation_start_count",
            "generation_advance_count",
            "accepted_completion_count",
            "stale_completion_count",
            "active_generation_count",
            "registry_size",
        }
        before = dict(session.generation_diagnostics)

        session.reset(build_recovery_control_plan(RecoveryAction.RESET_TURN))
        after = dict(session.generation_diagnostics)

        self.assertEqual(set(after), keys)
        self.assertEqual(after["generation_start_count"], before["generation_start_count"] + 1)
        self.assertEqual(after["generation_advance_count"], before["generation_advance_count"] + 1)
        self.assertEqual(after["active_generation_count"], 1)

    def test_terminal_reset_reserves_replacement_for_next_turn(self) -> None:
        session = framework.create_realtime_session()
        terminal = session.run_turn(input_text="done")
        plan = build_recovery_control_plan(RecoveryAction.RESET_SESSION)

        result = session.reset(plan)

        self.assertIs(result.outcome, RecoveryResetOutcome.APPLIED)
        self.assertEqual(result.previous_generation_id, terminal.generation_id)
        self.assertEqual(
            session._generation_gate.pending_generation_id,
            result.current_generation_id,
        )
        next_turn = session.start_turn(input_text="next")
        self.assertTrue(next_turn.accepted)
        self.assertEqual(next_turn.generation_id, result.current_generation_id)
        self.assertIsNone(session._generation_gate.pending_generation_id)

    def test_interrupted_terminal_recovery_action_executes_on_next_turn_boundary(self) -> None:
        session, turn, previous = self._session_and_turn()
        terminal = session._commit_terminal_result(
            RealtimeTurnResult.interrupted(
                turn_id=turn.turn_id,
                session_id=session.info.session_id,
                generation_id=previous,
            ),
            event_type=RealtimeEventType.TURN_INTERRUPTED,
            new_state=RealtimeState.INTERRUPTED,
            reason="test_interrupt_terminal",
        )
        session._clear_active_turn_context()
        self.assertIs(terminal.recovery_action, RecoveryAction.RESET_TURN)
        self.assertEqual(terminal.generation_id, previous)

        plan = build_recovery_control_plan(terminal.recovery_action)
        reset_result = session.reset(plan)
        next_turn = session.start_turn(input_text="after-interrupt")

        self.assertIs(reset_result.outcome, RecoveryResetOutcome.APPLIED)
        self.assertEqual(reset_result.previous_generation_id, previous)
        self.assertEqual(
            next_turn.generation_id,
            reset_result.current_generation_id,
        )

    def test_reset_without_any_previous_generation_is_typed_failure(self) -> None:
        session = framework.create_realtime_session()
        plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)

        result = session.reset(plan)

        self.assertIs(result.outcome, RecoveryResetOutcome.FAILED)
        self.assertIs(
            result.error_code,
            RecoveryResetErrorCode.GENERATION_MISMATCH,
        )
        self.assertFalse(result.generation_advanced)
        self.assertIsNone(result.previous_generation_id)
        self.assertIsNone(result.current_generation_id)

    def test_closed_session_reset_is_typed_failure(self) -> None:
        session, _turn, _generation = self._session_and_turn()
        session.close()
        plan = build_recovery_control_plan(RecoveryAction.RESET_SESSION)

        result = session.reset(plan)

        self.assertIs(result.outcome, RecoveryResetOutcome.FAILED)
        self.assertIs(result.error_code, RecoveryResetErrorCode.SESSION_CLOSED)
        self.assertFalse(result.retryable)
        self.assertFalse(result.generation_advanced)

    def test_active_stage_control_returns_retryable_typed_failure(self) -> None:
        session, _turn, previous = self._session_and_turn()
        before = dict(session.generation_diagnostics)
        session._active_interrupt_stage_work["text_generation"] = object()
        try:
            result = session.reset(
                build_recovery_control_plan(RecoveryAction.RESET_TURN)
            )
        finally:
            session._active_interrupt_stage_work.clear()

        self.assertIs(result.outcome, RecoveryResetOutcome.FAILED)
        self.assertIs(result.error_code, RecoveryResetErrorCode.ACTIVE_OPERATION)
        self.assertTrue(result.retryable)
        self.assertEqual(session._generation_gate.current_generation_id, previous)
        self.assertEqual(dict(session.generation_diagnostics), before)

    def test_completion_and_reset_are_linearized_by_session_operation_lock(self) -> None:
        session, turn, previous = self._session_and_turn()
        delivery_entered = Event()
        release_delivery = Event()
        decisions: list[object] = []
        reset_results: list[object] = []

        def deliver(_value: str) -> None:
            delivery_entered.set()
            self.assertTrue(release_delivery.wait(timeout=2.0))

        completion = Thread(
            target=lambda: decisions.append(
                session._apply_stage_completion(
                    RealtimeStageCompletionEnvelope(
                        turn_id=turn.turn_id,
                        generation_id=previous,
                        stage="recovery_race_completion",
                        value="current-before-reset",
                    ),
                    deliver=deliver,
                )
            )
        )
        completion.start()
        self.assertTrue(delivery_entered.wait(timeout=2.0))
        resetter = Thread(
            target=lambda: reset_results.append(
                session.reset(
                    build_recovery_control_plan(RecoveryAction.RESET_TURN)
                )
            )
        )
        resetter.start()
        self.assertTrue(resetter.is_alive())
        release_delivery.set()
        completion.join(timeout=2.0)
        resetter.join(timeout=2.0)

        self.assertFalse(completion.is_alive())
        self.assertFalse(resetter.is_alive())
        self.assertTrue(decisions[0].accepted)
        self.assertIs(reset_results[0].outcome, RecoveryResetOutcome.APPLIED)

    def test_reset_emits_no_new_event_and_preserves_public_contracts(self) -> None:
        session, _turn, _previous = self._session_and_turn()
        before = tuple(session.event_history)

        session.reset(build_recovery_control_plan(RecoveryAction.RESET_TURN))

        self.assertEqual(tuple(session.event_history), before)
        self.assertNotIn("RESET", RealtimeEventType.__members__)
        self.assertEqual(len(framework.__all__), 127)
        self.assertNotIn("RecoveryControlPlan", framework.__all__)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        self.assertNotIn("reset", signature(framework.create_realtime_session).parameters)

    def test_reset_import_and_execution_remain_provider_free(self) -> None:
        session, _turn, _previous = self._session_and_turn()
        session.reset(build_recovery_control_plan(RecoveryAction.RESET_SESSION))

        for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
            self.assertNotIn(module_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
