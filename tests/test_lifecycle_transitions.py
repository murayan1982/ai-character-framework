"""Fast provider-free tests for lifecycle transition rules."""

from __future__ import annotations

import unittest

from framework.lifecycle import (
    LifecycleTransitionError,
    LifecycleTransitionErrorCode,
    RealtimePhase,
    TurnOutcome,
    validate_phase_transition,
    validate_terminal_transition,
)


class PhaseTransitionTests(unittest.TestCase):
    def test_idempotent_phase_transition(self) -> None:
        self.assertIs(
            validate_phase_transition(
                RealtimePhase.THINKING,
                RealtimePhase.THINKING,
            ),
            RealtimePhase.THINKING,
        )

    def test_allowed_phase_chain(self) -> None:
        phase = RealtimePhase.IDLE
        for target in (
            RealtimePhase.LISTENING,
            RealtimePhase.TRANSCRIBING,
            RealtimePhase.THINKING,
            RealtimePhase.SPEAKING,
            RealtimePhase.MOTION,
            RealtimePhase.IDLE,
        ):
            phase = validate_phase_transition(phase, target)
        self.assertIs(phase, RealtimePhase.IDLE)

    def test_invalid_phase_transition_is_typed_and_safe(self) -> None:
        with self.assertRaises(LifecycleTransitionError) as captured:
            validate_phase_transition(
                RealtimePhase.IDLE,
                RealtimePhase.RECOVERING,
            )

        error = captured.exception
        self.assertIs(
            error.code,
            LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION,
        )
        self.assertIs(error.from_phase, RealtimePhase.IDLE)
        self.assertIs(error.to_phase, RealtimePhase.RECOVERING)
        self.assertEqual(str(error), error.safe_message)
        self.assertNotIn("provider", str(error).lower())

    def test_string_inputs_are_normalized(self) -> None:
        self.assertIs(
            validate_phase_transition("idle", "listening"),
            RealtimePhase.LISTENING,
        )
        self.assertIs(
            validate_terminal_transition(None, "interrupted"),
            TurnOutcome.INTERRUPTED,
        )


class TerminalTransitionTests(unittest.TestCase):
    def test_first_terminal_is_admitted(self) -> None:
        self.assertIs(
            validate_terminal_transition(None, TurnOutcome.COMPLETED),
            TurnOutcome.COMPLETED,
        )

    def test_duplicate_terminal_is_classified(self) -> None:
        with self.assertRaises(LifecycleTransitionError) as captured:
            validate_terminal_transition(
                TurnOutcome.CANCELLED,
                TurnOutcome.CANCELLED,
            )

        error = captured.exception
        self.assertIs(
            error.code,
            LifecycleTransitionErrorCode.DUPLICATE_TERMINAL,
        )
        self.assertIs(error.existing_outcome, TurnOutcome.CANCELLED)
        self.assertIs(error.attempted_outcome, TurnOutcome.CANCELLED)

    def test_terminal_regression_is_classified(self) -> None:
        with self.assertRaises(LifecycleTransitionError) as captured:
            validate_terminal_transition(
                TurnOutcome.COMPLETED,
                TurnOutcome.FAILED,
            )

        error = captured.exception
        self.assertIs(
            error.code,
            LifecycleTransitionErrorCode.TERMINAL_REGRESSION,
        )
        self.assertIs(error.existing_outcome, TurnOutcome.COMPLETED)
        self.assertIs(error.attempted_outcome, TurnOutcome.FAILED)

if __name__ == "__main__":
    unittest.main()
