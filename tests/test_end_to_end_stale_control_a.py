"""Provider-free FW-RT6-9d Control A atomic stale-delivery tests."""

from __future__ import annotations

from threading import Event, Thread
import unittest

from framework.identity import GenerationId
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    RealtimeGenerationGate,
    RealtimeStageCompletionEnvelope,
    StaleCompletionReason,
)


_DELIVERY_STAGES = (
    "text_generation_delta",
    "voice_input_transcript",
    "voice_output_artifact",
    "motion_completion",
)


def _envelope(
    *,
    turn_id: str,
    generation_id: GenerationId,
    stage: str,
    value: object = "public-safe-value",
) -> RealtimeStageCompletionEnvelope[object]:
    return RealtimeStageCompletionEnvelope(
        turn_id=turn_id,
        generation_id=generation_id,
        stage=stage,
        value=value,
    )


class EndToEndStaleControlATests(unittest.TestCase):
    def test_each_end_to_end_stage_can_apply_one_current_delivery(self) -> None:
        for stage in _DELIVERY_STAGES:
            with self.subTest(stage=stage):
                gate = RealtimeGenerationGate()
                generation_id = gate.start_generation("turn-a")
                delivered = []

                decision = gate.apply_completion(
                    _envelope(
                        turn_id="turn-a",
                        generation_id=generation_id,
                        stage=stage,
                        value=stage,
                    ),
                    deliver=delivered.append,
                )

                self.assertTrue(decision.accepted)
                self.assertEqual(delivered, [stage])
                self.assertEqual(gate.diagnostics["accepted_completion_count"], 1)

    def test_each_retired_stage_is_rejected_before_delivery(self) -> None:
        for stage in _DELIVERY_STAGES:
            with self.subTest(stage=stage):
                gate = RealtimeGenerationGate()
                generation_id = gate.start_generation("turn-a")
                gate.advance(GenerationAdvanceReason.INTERRUPT)
                delivered = []

                decision = gate.apply_completion(
                    _envelope(
                        turn_id="turn-a",
                        generation_id=generation_id,
                        stage=stage,
                    ),
                    deliver=delivered.append,
                )

                self.assertFalse(decision.accepted)
                self.assertEqual(delivered, [])
                self.assertIs(
                    decision.stale_reason,
                    StaleCompletionReason.RETIRED_GENERATION,
                )
                self.assertIs(
                    decision.retired_by,
                    GenerationAdvanceReason.INTERRUPT,
                )
                self.assertEqual(gate.diagnostics["stale_completion_count"], 1)

    def test_new_turn_rejects_old_callback_without_delivering_value(self) -> None:
        gate = RealtimeGenerationGate()
        old_generation = gate.start_generation("turn-old")
        current_generation = gate.start_generation("turn-current")
        delivered = []

        decision = gate.apply_completion(
            _envelope(
                turn_id="turn-old",
                generation_id=old_generation,
                stage="text_generation_delta",
            ),
            deliver=delivered.append,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(delivered, [])
        self.assertIs(decision.retired_by, GenerationAdvanceReason.NEW_TURN)
        self.assertEqual(decision.current_generation_id, current_generation)

    def test_close_retirement_rejects_old_callback(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        gate.advance(GenerationAdvanceReason.SESSION_CLOSED)
        delivered = []

        decision = gate.apply_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=generation_id,
                stage="voice_output_artifact",
            ),
            deliver=delivered.append,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(delivered, [])
        self.assertIs(decision.retired_by, GenerationAdvanceReason.SESSION_CLOSED)

    def test_reset_retirement_rejects_old_callback(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        gate.advance(GenerationAdvanceReason.RESET)
        delivered = []

        decision = gate.apply_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=generation_id,
                stage="motion_completion",
            ),
            deliver=delivered.append,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(delivered, [])
        self.assertIs(decision.retired_by, GenerationAdvanceReason.RESET)

    def test_unknown_generation_retains_reason_and_never_delivers(self) -> None:
        gate = RealtimeGenerationGate()
        current_generation = gate.start_generation("turn-a")
        delivered = []

        decision = gate.apply_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=GenerationId.new(),
                stage="voice_input_transcript",
            ),
            deliver=delivered.append,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(delivered, [])
        self.assertIs(decision.stale_reason, StaleCompletionReason.UNKNOWN_GENERATION)
        self.assertEqual(decision.current_generation_id, current_generation)

    def test_turn_mismatch_retains_reason_and_never_delivers(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        delivered = []

        decision = gate.apply_completion(
            _envelope(
                turn_id="turn-b",
                generation_id=generation_id,
                stage="motion_completion",
            ),
            deliver=delivered.append,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(delivered, [])
        self.assertIs(decision.stale_reason, StaleCompletionReason.TURN_MISMATCH)

    def test_delivery_lock_excludes_competing_generation_advance(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        delivery_entered = Event()
        release_delivery = Event()
        delivery_finished = Event()
        advance_finished = Event()
        order = []

        def deliver(value: object) -> None:
            delivery_entered.set()
            self.assertTrue(release_delivery.wait(timeout=2.0))
            order.append(value)

        def apply() -> None:
            gate.apply_completion(
                _envelope(
                    turn_id="turn-a",
                    generation_id=generation_id,
                    stage="text_generation_delta",
                    value="delivered",
                ),
                deliver=deliver,
            )
            delivery_finished.set()

        def advance() -> None:
            gate.advance(GenerationAdvanceReason.INTERRUPT)
            order.append("advanced")
            advance_finished.set()

        delivery_thread = Thread(target=apply, daemon=True)
        delivery_thread.start()
        self.assertTrue(delivery_entered.wait(timeout=2.0))
        advance_thread = Thread(target=advance, daemon=True)
        advance_thread.start()
        self.assertFalse(advance_finished.wait(timeout=0.05))

        release_delivery.set()
        self.assertTrue(delivery_finished.wait(timeout=2.0))
        self.assertTrue(advance_finished.wait(timeout=2.0))
        delivery_thread.join(timeout=2.0)
        advance_thread.join(timeout=2.0)

        self.assertEqual(order, ["delivered", "advanced"])

    def test_generation_advance_winning_first_suppresses_delivery(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        gate.advance(GenerationAdvanceReason.CANCEL)
        delivered = []

        decision = gate.apply_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=generation_id,
                stage="text_generation_delta",
            ),
            deliver=delivered.append,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(delivered, [])
        self.assertIs(decision.retired_by, GenerationAdvanceReason.CANCEL)

    def test_reentrant_advance_from_delivery_is_safe_and_ordered_after_apply(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        delivered = []

        def deliver(value: object) -> None:
            delivered.append(value)
            gate.advance(GenerationAdvanceReason.INTERRUPT)

        decision = gate.apply_completion(
            _envelope(
                turn_id="turn-a",
                generation_id=generation_id,
                stage="voice_input_transcript",
            ),
            deliver=deliver,
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(delivered, ["public-safe-value"])
        self.assertIsNone(gate.current_generation_id)
        self.assertEqual(gate.diagnostics["accepted_completion_count"], 1)
        self.assertEqual(gate.diagnostics["generation_advance_count"], 1)

    def test_delivery_failure_propagates_without_retry(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        calls = []

        def fail(value: object) -> None:
            calls.append(value)
            raise RuntimeError("synthetic delivery failure")

        with self.assertRaisesRegex(RuntimeError, "synthetic delivery failure"):
            gate.apply_completion(
                _envelope(
                    turn_id="turn-a",
                    generation_id=generation_id,
                    stage="voice_output_artifact",
                ),
                deliver=fail,
            )

        self.assertEqual(calls, ["public-safe-value"])
        self.assertEqual(gate.diagnostics["accepted_completion_count"], 1)

    def test_callable_validation_precedes_freshness_accounting(self) -> None:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")

        with self.assertRaises(TypeError):
            gate.apply_completion(
                _envelope(
                    turn_id="turn-a",
                    generation_id=generation_id,
                    stage="motion_completion",
                ),
                deliver=None,  # type: ignore[arg-type]
            )

        self.assertEqual(gate.diagnostics["accepted_completion_count"], 0)
        self.assertEqual(gate.diagnostics["stale_completion_count"], 0)

    def test_existing_diagnostics_keys_and_immutability_are_unchanged(self) -> None:
        diagnostics = RealtimeGenerationGate().diagnostics
        self.assertEqual(
            set(diagnostics),
            {
                "generation_start_count",
                "generation_advance_count",
                "accepted_completion_count",
                "stale_completion_count",
                "active_generation_count",
                "registry_size",
            },
        )
        with self.assertRaises(TypeError):
            diagnostics["stale_completion_count"] = 1


if __name__ == "__main__":
    unittest.main()
