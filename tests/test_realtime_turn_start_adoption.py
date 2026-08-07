from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest

import framework
from framework import (
    GenerationId,
    RealtimeErrorCode,
    RealtimeEventType,
    RealtimePhase,
    RealtimeState,
    RealtimeTurn,
    RealtimeTurnStartResult,
    SessionId,
    TurnOutcome,
)


class RealtimeTurnStartAdoptionTests(unittest.TestCase):
    def test_explicit_start_accepts_and_correlates_identity(self) -> None:
        session = framework.create_realtime_session()

        result = session.start_turn(input_text="hello")

        self.assertIsInstance(result, RealtimeTurnStartResult)
        self.assertTrue(result.accepted)
        self.assertEqual(result.session_id, session.info.session_id)
        self.assertIsNotNone(result.generation_id)
        self.assertIs(result.phase, RealtimePhase.LISTENING)
        self.assertIsNone(result.terminal_result)
        self.assertIs(session.state, RealtimeState.LISTENING)
        self.assertIs(session.phase, RealtimePhase.LISTENING)

        events = session.event_history
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertIs(event.type, RealtimeEventType.TURN_STARTED)
        self.assertEqual(event.session_id, result.session_id)
        self.assertEqual(event.turn_id, result.turn_id)
        self.assertEqual(event.generation_id, result.generation_id)
        session.close()

    def test_explicit_start_allocates_exactly_one_generation(self) -> None:
        session = framework.create_realtime_session()

        result = session.start_turn(input_text="hello")

        diagnostics = session.generation_diagnostics
        self.assertTrue(result.accepted)
        self.assertEqual(diagnostics["generation_start_count"], 1)
        self.assertEqual(diagnostics["generation_advance_count"], 0)
        self.assertEqual(diagnostics["active_generation_count"], 1)
        session.close()

    def test_same_active_turn_start_is_idempotent(self) -> None:
        session = framework.create_realtime_session()
        turn = RealtimeTurn(session_id=session.info.session_id)

        first = session.start_turn(turn)
        before_event_count = len(session.event_history)
        second = session.start_turn(turn)

        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(second.generation_id, first.generation_id)
        self.assertTrue(second.public_metadata["idempotent"])
        self.assertEqual(len(session.event_history), before_event_count)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        self.assertEqual(session.generation_diagnostics["generation_advance_count"], 0)
        session.close()

    def test_new_turn_while_active_is_typed_rejection(self) -> None:
        session = framework.create_realtime_session()
        active = session.start_turn(input_text="first")
        before_state = session.state
        before_phase = session.phase

        rejected = session.start_turn(input_text="second")

        self.assertFalse(rejected.accepted)
        self.assertIsNone(rejected.generation_id)
        self.assertIsNotNone(rejected.terminal_result)
        terminal = rejected.terminal_result
        assert terminal is not None
        self.assertIs(terminal.outcome, TurnOutcome.REJECTED)
        self.assertIs(terminal.public_error_code, RealtimeErrorCode.REJECTED)
        self.assertEqual(terminal.session_id, session.info.session_id)
        self.assertIsNone(terminal.generation_id)
        self.assertEqual(terminal.public_metadata["reason"], "active_turn_exists")
        self.assertIs(session.state, before_state)
        self.assertIs(session.phase, before_phase)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        self.assertEqual(session.generation_diagnostics["generation_advance_count"], 0)
        self.assertEqual(session.generation_diagnostics["active_generation_count"], 1)
        self.assertEqual(active.generation_id, session._generation_gate.current_generation_id)
        session.close()

    def test_active_rejection_emits_one_state_neutral_terminal_event(self) -> None:
        session = framework.create_realtime_session()
        active = session.start_turn(input_text="first")
        rejected = session.start_turn(input_text="second")

        rejection_events = [
            event
            for event in session.event_history
            if event.turn_id == rejected.turn_id
        ]
        self.assertEqual(len(rejection_events), 1)
        event = rejection_events[0]
        self.assertIs(event.type, RealtimeEventType.TURN_REJECTED)
        self.assertIs(event.state, RealtimeState.LISTENING)
        self.assertIs(event.previous_state, RealtimeState.LISTENING)
        self.assertIs(event.phase, RealtimePhase.LISTENING)
        self.assertIsNone(event.generation_id)
        self.assertEqual(event.public_error_code, RealtimeErrorCode.REJECTED)
        self.assertEqual(session._generation_gate.current_generation_id, active.generation_id)
        session.close()

    def test_duplicate_rejected_start_returns_original_without_second_event(self) -> None:
        session = framework.create_realtime_session()
        session.start_turn(input_text="first")
        requested = RealtimeTurn(session_id=session.info.session_id)

        first = session.start_turn(requested)
        first_terminal = first.terminal_result
        before_event_count = len(session.event_history)
        second = session.start_turn(requested)

        self.assertFalse(second.accepted)
        self.assertIs(second.terminal_result, first_terminal)
        self.assertEqual(len(session.event_history), before_event_count)
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)
        session.close()

    def test_active_rejection_does_not_retire_previous_generation(self) -> None:
        session = framework.create_realtime_session()
        active = session.start_turn(input_text="first")

        session.start_turn(input_text="second")

        self.assertEqual(session._generation_gate.current_generation_id, active.generation_id)
        self.assertEqual(session.generation_diagnostics["generation_advance_count"], 0)
        session.close()

    def test_two_concurrent_explicit_starts_produce_one_accept_and_one_reject(self) -> None:
        session = framework.create_realtime_session()
        barrier = Barrier(2)

        def start(value: str) -> RealtimeTurnStartResult:
            barrier.wait(timeout=5)
            return session.start_turn(input_text=value)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(start, ("a", "b")))

        accepted = [result for result in results if result.accepted]
        rejected = [result for result in results if not result.accepted]
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        self.assertEqual(session.generation_diagnostics["generation_advance_count"], 0)
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)
        session.close()

    def test_turn_from_different_session_is_rejected_without_generation(self) -> None:
        session = framework.create_realtime_session()
        foreign = RealtimeTurn(session_id=SessionId.new())

        result = session.start_turn(foreign)

        self.assertFalse(result.accepted)
        terminal = result.terminal_result
        assert terminal is not None
        self.assertIs(terminal.public_error_code, RealtimeErrorCode.INVALID_REQUEST)
        self.assertEqual(terminal.public_metadata["reason"], "turn_session_mismatch")
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 0)
        self.assertIs(session.state, RealtimeState.IDLE)
        self.assertIs(session.phase, RealtimePhase.IDLE)
        session.close()

    def test_closed_session_start_is_typed_without_post_close_event(self) -> None:
        session = framework.create_realtime_session()
        session.close()
        before_events = session.event_history

        result = session.start_turn(input_text="closed")

        self.assertFalse(result.accepted)
        terminal = result.terminal_result
        assert terminal is not None
        self.assertIs(terminal.outcome, TurnOutcome.REJECTED)
        self.assertIs(terminal.public_error_code, RealtimeErrorCode.SESSION_CLOSED)
        self.assertEqual(terminal.session_id, session.info.session_id)
        self.assertEqual(session.event_history, before_events)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 0)

    def test_real_runtime_missing_configuration_start_preserves_no_fallback(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)

        result = session.start_turn(input_text="real")

        self.assertFalse(result.accepted)
        terminal = result.terminal_result
        assert terminal is not None
        self.assertIs(terminal.outcome, TurnOutcome.REJECTED)
        self.assertIs(
            terminal.public_error_code,
            RealtimeErrorCode.CONFIGURATION_MISSING,
        )
        self.assertEqual(terminal.session_id, session.info.session_id)
        self.assertIsNone(terminal.generation_id)
        self.assertFalse(terminal.public_metadata["mock_runtime"])
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 0)
        self.assertIs(session.state, RealtimeState.IDLE)
        self.assertIs(session.phase, RealtimePhase.IDLE)
        session.close()

    def test_close_clears_explicit_active_generation_and_context(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="first")
        self.assertTrue(started.accepted)

        session.close()

        self.assertTrue(session.is_closed)
        self.assertEqual(session.generation_diagnostics["active_generation_count"], 0)
        self.assertEqual(session.generation_diagnostics["generation_advance_count"], 1)
        self.assertIsNone(session._active_turn_context)
        self.assertIsNone(session._active_turn_id)
        self.assertIsNone(session._active_generation_id)

    def test_run_turn_adopts_explicit_start_contract_in_control_c(self) -> None:
        session = framework.create_realtime_session()

        result = session.run_turn(input_text="unified")

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(result.session_id, session.info.session_id)
        self.assertIsNotNone(result.generation_id)
        self.assertIs(session.state, RealtimeState.IDLE)
        self.assertIs(session.phase, RealtimePhase.IDLE)
        session.close()

    def test_root_public_surface_preserves_control_a_125_name_prefix(self) -> None:
        self.assertGreaterEqual(len(framework.__all__), 125)
        self.assertEqual(framework.__all__[124], "RealtimeTurnStartResult")


if __name__ == "__main__":
    unittest.main()
