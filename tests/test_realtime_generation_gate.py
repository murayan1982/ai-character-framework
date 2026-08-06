"""Provider-free unit tests for generation and stale-completion admission."""

from __future__ import annotations

import unittest

from framework.identity import GenerationId
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    RealtimeGenerationGate,
    RealtimeStageCompletionEnvelope,
    StaleCompletionReason,
)


def _envelope(
    *,
    turn_id: str,
    generation_id: GenerationId,
    stage: str = "text_generation",
    value: str = "value",
) -> RealtimeStageCompletionEnvelope[str]:
    return RealtimeStageCompletionEnvelope(
        turn_id=turn_id,
        generation_id=generation_id,
        stage=stage,
        value=value,
    )


class RealtimeGenerationGateTests(unittest.TestCase):
    def test_current_generation_completion_is_admitted(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")

        decision = gate.admit_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=generation_id,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertIsNone(decision.stale_reason)
        self.assertIsNone(decision.retired_by)
        self.assertEqual(decision.current_generation_id, generation_id)
        self.assertEqual(gate.current_generation_id, generation_id)
        self.assertEqual(gate.current_turn_id, "turn-a")
        self.assertEqual(gate.diagnostics["accepted_completion_count"], 1)

    def test_new_turn_retires_previous_generation(self) -> None:
        gate = RealtimeGenerationGate()
        retired_generation = gate.start_generation("turn-a")
        current_generation = gate.start_generation("turn-b")

        decision = gate.admit_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=retired_generation,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertIs(
            decision.stale_reason,
            StaleCompletionReason.RETIRED_GENERATION,
        )
        self.assertIs(
            decision.retired_by,
            GenerationAdvanceReason.NEW_TURN,
        )
        self.assertEqual(
            decision.current_generation_id,
            current_generation,
        )

        diagnostics = gate.diagnostics
        self.assertEqual(diagnostics["generation_start_count"], 2)
        self.assertEqual(diagnostics["generation_advance_count"], 1)
        self.assertEqual(diagnostics["stale_completion_count"], 1)

    def test_explicit_advance_retains_retirement_reason(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")

        retired = gate.advance(GenerationAdvanceReason.CANCEL)
        repeated = gate.advance(GenerationAdvanceReason.RESET)
        decision = gate.admit_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=generation_id,
            )
        )

        self.assertEqual(retired, generation_id)
        self.assertIsNone(repeated)
        self.assertIsNone(gate.current_generation_id)
        self.assertIs(
            decision.stale_reason,
            StaleCompletionReason.RETIRED_GENERATION,
        )
        self.assertIs(
            decision.retired_by,
            GenerationAdvanceReason.CANCEL,
        )

    def test_unknown_generation_is_rejected(self) -> None:
        gate = RealtimeGenerationGate()
        current_generation = gate.start_generation("turn-a")
        unknown_generation = GenerationId.new()

        decision = gate.admit_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=unknown_generation,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertIs(
            decision.stale_reason,
            StaleCompletionReason.UNKNOWN_GENERATION,
        )
        self.assertIsNone(decision.retired_by)
        self.assertEqual(
            decision.current_generation_id,
            current_generation,
        )

    def test_turn_mismatch_is_rejected(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")

        decision = gate.admit_completion(
            _envelope(
                turn_id="turn-b",
                generation_id=generation_id,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertIs(
            decision.stale_reason,
            StaleCompletionReason.TURN_MISMATCH,
        )
        self.assertEqual(
            decision.current_generation_id,
            generation_id,
        )

    def test_envelope_validation_and_diagnostics_are_immutable(self) -> None:
        generation_id = GenerationId.new()
        envelope = _envelope(
            turn_id="turn-a",
            generation_id=generation_id,
            stage="  voice_output  ",
        )

        self.assertEqual(envelope.stage, "voice_output")
        with self.assertRaises(ValueError):
            _envelope(
                turn_id="turn-a",
                generation_id=generation_id,
                stage="   ",
            )

        diagnostics = RealtimeGenerationGate().diagnostics
        with self.assertRaises(TypeError):
            diagnostics["generation_start_count"] = 1


if __name__ == "__main__":
    unittest.main()
