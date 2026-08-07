from __future__ import annotations

import unittest

import framework
from framework import (
    RealtimeErrorCode,
    RealtimeEventType,
    RealtimePhase,
    RealtimeState,
    RealtimeTurn,
    TurnOutcome,
)


class RealtimeTurnLifecycleAcceptanceTests(unittest.TestCase):
    def test_run_turn_completed_result_correlates_session_turn_generation(self) -> None:
        session = framework.create_realtime_session()
        turn = RealtimeTurn(input_text="identity")

        result = session.run_turn(turn)

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(result.session_id, session.info.session_id)
        self.assertEqual(result.turn_id, turn.turn_id)
        self.assertIsNotNone(result.generation_id)

    def test_run_turn_emits_one_started_and_one_terminal_event(self) -> None:
        session = framework.create_realtime_session()

        result = session.run_turn(input_text="events")
        events = tuple(
            event for event in session.event_history
            if event.turn_id == result.turn_id
        )

        self.assertEqual(
            sum(event.type is RealtimeEventType.TURN_STARTED for event in events),
            1,
        )
        self.assertEqual(
            sum(event.type is RealtimeEventType.TURN_COMPLETED for event in events),
            1,
        )
        terminal = next(
            event for event in events
            if event.type is RealtimeEventType.TURN_COMPLETED
        )
        self.assertEqual(terminal.session_id, result.session_id)
        self.assertEqual(terminal.generation_id, result.generation_id)

    def test_normal_turn_owns_one_generation_and_one_terminal_commit(self) -> None:
        session = framework.create_realtime_session()

        result = session.run_turn(input_text="one generation")

        self.assertIsNotNone(result.generation_id)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        self.assertEqual(session.generation_diagnostics["generation_advance_count"], 1)
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)
        self.assertEqual(session.terminal_results, (result,))

    def test_normal_completion_clears_active_context_and_returns_idle(self) -> None:
        session = framework.create_realtime_session()

        session.run_turn(input_text="cleanup")

        self.assertIsNone(session._active_turn_context)
        self.assertIsNone(session._active_turn_id)
        self.assertIsNone(session._active_generation_id)
        self.assertIsNone(session._generation_gate.current_turn_id)
        self.assertIsNone(session._generation_gate.current_generation_id)
        self.assertIs(session.state, RealtimeState.IDLE)
        self.assertIs(session.phase, RealtimePhase.IDLE)

    def test_session_is_reusable_for_next_run_turn(self) -> None:
        session = framework.create_realtime_session()

        first = session.run_turn(input_text="first")
        second = session.run_turn(input_text="second")

        self.assertIs(first.outcome, TurnOutcome.COMPLETED)
        self.assertIs(second.outcome, TurnOutcome.COMPLETED)
        self.assertNotEqual(first.turn_id, second.turn_id)
        self.assertNotEqual(first.generation_id, second.generation_id)
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 2)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 2)
        self.assertIs(session.state, RealtimeState.IDLE)
        self.assertIs(session.phase, RealtimePhase.IDLE)

    def test_explicit_start_then_run_turn_uses_same_generation_without_second_start(self) -> None:
        session = framework.create_realtime_session()
        turn = RealtimeTurn(input_text="explicit then execute")

        start = session.start_turn(turn)
        result = session.run_turn(turn)

        self.assertTrue(start.accepted)
        self.assertEqual(result.generation_id, start.generation_id)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        self.assertEqual(
            sum(
                event.type is RealtimeEventType.TURN_STARTED
                for event in session.event_history
                if event.turn_id == turn.turn_id
            ),
            1,
        )
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)

    def test_active_different_run_turn_rejects_without_replacing_generation(self) -> None:
        session = framework.create_realtime_session()
        active = session.start_turn(RealtimeTurn(input_text="active"))
        self.assertTrue(active.accepted)
        before_state = session.state
        before_phase = session.phase
        before_generation = session._generation_gate.current_generation_id
        before_advance = session.generation_diagnostics["generation_advance_count"]

        rejected = session.run_turn(RealtimeTurn(input_text="new"))

        self.assertIs(rejected.outcome, TurnOutcome.REJECTED)
        self.assertIs(rejected.public_error_code, RealtimeErrorCode.REJECTED)
        self.assertEqual(rejected.public_metadata["reason"], "active_turn_exists")
        self.assertIsNone(rejected.generation_id)
        self.assertIs(session.state, before_state)
        self.assertIs(session.phase, before_phase)
        self.assertEqual(
            session._generation_gate.current_generation_id,
            before_generation,
        )
        self.assertEqual(
            session.generation_diagnostics["generation_advance_count"],
            before_advance,
        )

    def test_repeated_completed_run_turn_returns_original_terminal(self) -> None:
        session = framework.create_realtime_session()
        turn = RealtimeTurn(input_text="duplicate")

        first = session.run_turn(turn)
        before_events = len(session.event_history)
        second = session.run_turn(turn)

        self.assertIs(second, first)
        self.assertEqual(len(session.event_history), before_events)
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)
        self.assertEqual(session.terminal_diagnostics["duplicate_terminal_count"], 1)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)

    def test_real_runtime_rejection_still_has_session_identity_and_no_generation(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)

        result = session.run_turn(input_text="no mock fallback")

        self.assertIs(result.outcome, TurnOutcome.REJECTED)
        self.assertEqual(result.session_id, session.info.session_id)
        self.assertIsNone(result.generation_id)
        self.assertFalse(result.public_metadata["mock_runtime"])
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 0)

    def test_foreign_session_run_turn_is_typed_rejection_without_generation(self) -> None:
        session = framework.create_realtime_session()
        foreign = framework.create_realtime_session()
        turn = RealtimeTurn(
            input_text="foreign",
            session_id=foreign.info.session_id,
        )

        result = session.run_turn(turn)

        self.assertIs(result.outcome, TurnOutcome.REJECTED)
        self.assertIs(result.public_error_code, RealtimeErrorCode.INVALID_REQUEST)
        self.assertEqual(result.session_id, session.info.session_id)
        self.assertEqual(result.turn_id, turn.turn_id)
        self.assertIsNone(result.generation_id)
        self.assertEqual(session.generation_diagnostics["generation_start_count"], 0)
        self.assertIs(session.state, RealtimeState.IDLE)
        self.assertIs(session.phase, RealtimePhase.IDLE)

    def test_closed_run_turn_returns_session_bound_closed_result(self) -> None:
        session = framework.create_realtime_session()
        session.close()
        turn = RealtimeTurn(input_text="closed")

        result = session.run_turn(turn)

        self.assertIs(result.outcome, TurnOutcome.CLOSED)
        self.assertIs(result.public_error_code, RealtimeErrorCode.SESSION_CLOSED)
        self.assertEqual(result.session_id, session.info.session_id)
        self.assertEqual(result.turn_id, turn.turn_id)
        self.assertIsNone(result.generation_id)

    def test_normal_phase_progression_and_terminal_are_validated(self) -> None:
        session = framework.create_realtime_session()

        result = session.run_turn(input_text="phase")
        events = tuple(
            event for event in session.event_history
            if event.turn_id == result.turn_id
        )
        by_type = {event.type: event for event in events}

        self.assertIs(by_type[RealtimeEventType.TURN_STARTED].phase, RealtimePhase.LISTENING)
        self.assertIs(by_type[RealtimeEventType.LISTENING_COMPLETED].phase, RealtimePhase.TRANSCRIBING)
        self.assertIs(by_type[RealtimeEventType.RESPONSE_STARTED].phase, RealtimePhase.THINKING)
        self.assertIs(by_type[RealtimeEventType.SYNTHESIS_STARTED].phase, RealtimePhase.SPEAKING)
        self.assertTrue(by_type[RealtimeEventType.TURN_COMPLETED].terminal)
        self.assertIs(session.phase, RealtimePhase.IDLE)


if __name__ == "__main__":
    unittest.main()
