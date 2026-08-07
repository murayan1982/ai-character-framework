from __future__ import annotations

import unittest

import framework
from framework import (
    GenerationId,
    RealtimePhase,
    RealtimeTurnResult,
    RealtimeTurnStartResult,
    SessionId,
    TurnId,
    TurnOutcome,
)


class RealtimeTurnStartModelTests(unittest.TestCase):
    def test_turn_result_identity_fields_are_additive_and_normalized(self) -> None:
        session_id = SessionId.new()
        generation_id = GenerationId.new()
        result = RealtimeTurnResult.completed(
            turn_id=TurnId.new(),
            session_id=str(session_id),
            generation_id=str(generation_id),
        )
        self.assertEqual(result.session_id, session_id)
        self.assertEqual(result.generation_id, generation_id)

    def test_turn_result_generation_requires_session(self) -> None:
        with self.assertRaisesRegex(ValueError, "generation_id requires session_id"):
            RealtimeTurnResult.completed(
                turn_id=TurnId.new(),
                generation_id=GenerationId.new(),
            )

    def test_rejected_result_can_bind_session_without_generation(self) -> None:
        session_id = SessionId.new()
        result = RealtimeTurnResult.rejected(
            turn_id=TurnId.new(),
            session_id=session_id,
        )
        self.assertEqual(result.session_id, session_id)
        self.assertIsNone(result.generation_id)
        self.assertIs(result.outcome, TurnOutcome.REJECTED)

    def test_accepted_start_requires_generation(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires generation_id"):
            RealtimeTurnStartResult(
                accepted=True,
                session_id=SessionId.new(),
                turn_id=TurnId.new(),
                generation_id=None,
                phase=RealtimePhase.LISTENING,
            )

    def test_accepted_start_rejects_terminal_result(self) -> None:
        session_id = SessionId.new()
        turn_id = TurnId.new()
        terminal = RealtimeTurnResult.rejected(
            turn_id=turn_id,
            session_id=session_id,
        )
        with self.assertRaisesRegex(ValueError, "cannot contain terminal_result"):
            RealtimeTurnStartResult(
                accepted=True,
                session_id=session_id,
                turn_id=turn_id,
                generation_id=GenerationId.new(),
                phase=RealtimePhase.LISTENING,
                terminal_result=terminal,
            )

    def test_accepted_start_normalizes_identity_and_metadata(self) -> None:
        session_id = SessionId.new()
        turn_id = TurnId.new()
        generation_id = GenerationId.new()
        result = RealtimeTurnStartResult(
            accepted=True,
            session_id=str(session_id),
            turn_id=str(turn_id),
            generation_id=str(generation_id),
            phase="listening",
            public_metadata={"boundary": "realtime_turn_start"},
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.session_id, session_id)
        self.assertEqual(result.turn_id, turn_id)
        self.assertEqual(result.generation_id, generation_id)
        self.assertIs(result.phase, RealtimePhase.LISTENING)
        with self.assertRaises(TypeError):
            result.public_metadata["x"] = 1

    def test_rejected_start_requires_terminal_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires terminal_result"):
            RealtimeTurnStartResult(
                accepted=False,
                session_id=SessionId.new(),
                turn_id=TurnId.new(),
                generation_id=None,
                phase=RealtimePhase.LISTENING,
            )

    def test_rejected_start_forbids_generation(self) -> None:
        session_id = SessionId.new()
        turn_id = TurnId.new()
        terminal = RealtimeTurnResult.rejected(
            turn_id=turn_id,
            session_id=session_id,
        )
        with self.assertRaisesRegex(ValueError, "cannot allocate generation_id"):
            RealtimeTurnStartResult(
                accepted=False,
                session_id=session_id,
                turn_id=turn_id,
                generation_id=GenerationId.new(),
                phase=RealtimePhase.LISTENING,
                terminal_result=terminal,
            )

    def test_rejected_start_requires_correlated_rejected_terminal(self) -> None:
        session_id = SessionId.new()
        turn_id = TurnId.new()
        wrong = RealtimeTurnResult.completed(
            turn_id=turn_id,
            session_id=session_id,
        )
        with self.assertRaisesRegex(ValueError, "rejected terminal outcome"):
            RealtimeTurnStartResult(
                accepted=False,
                session_id=session_id,
                turn_id=turn_id,
                generation_id=None,
                phase=RealtimePhase.LISTENING,
                terminal_result=wrong,
            )

    def test_root_public_suffix_is_additive(self) -> None:
        self.assertGreaterEqual(len(framework.__all__), 125)
        self.assertEqual(framework.__all__[124], "RealtimeTurnStartResult")
        self.assertIs(framework.RealtimeTurnStartResult, RealtimeTurnStartResult)


if __name__ == "__main__":
    unittest.main()
