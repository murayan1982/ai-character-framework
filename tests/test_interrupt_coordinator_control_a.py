"""Provider-free tests for FW-RT6-9a Control A interrupt coordination."""

from __future__ import annotations

from dataclasses import fields
from inspect import signature
import unittest

import framework
from framework.identity import GenerationId, SessionId, TurnId
from framework.interrupt_coordination import (
    InterruptAggregateOutcome,
    InterruptAggregateResult,
    InterruptSubsystem,
    InterruptSubsystemOutcome,
    InterruptSubsystemResult,
)
from framework.output_control import InterruptOutcome, InterruptRequest, InterruptResult


def _identity() -> tuple[SessionId, TurnId, GenerationId]:
    return SessionId.new(), TurnId.new(), GenerationId.new()


def _completed(
    subsystem: InterruptSubsystem,
    *,
    session_id: SessionId,
    turn_id: TurnId,
    generation_id: GenerationId | None = None,
) -> InterruptSubsystemResult:
    return InterruptSubsystemResult(
        subsystem=subsystem,
        outcome=InterruptSubsystemOutcome.COMPLETED,
        session_id=session_id,
        turn_id=turn_id,
        generation_id=generation_id,
        target_reached=True,
        cooperative_cancel_requested=True,
        cooperative_cancel_accepted=True,
        cooperative_cancel_completed=True,
        future_delivery_suppressed=True,
    )


class InterruptCoordinatorControlATests(unittest.TestCase):
    def test_explicit_exports_and_vocabularies_are_exact(self) -> None:
        import framework.interrupt_coordination as coordination

        self.assertEqual(
            tuple(coordination.__all__),
            (
                "InterruptAggregateOutcome",
                "InterruptAggregateResult",
                "InterruptSubsystem",
                "InterruptSubsystemOutcome",
                "InterruptSubsystemResult",
            ),
        )
        self.assertEqual(
            tuple(item.name for item in InterruptSubsystem),
            (
                "TEXT_GENERATION",
                "TTS_GENERATION",
                "TTS_QUEUE",
                "AUDIO_ARTIFACT",
                "MOTION",
            ),
        )
        self.assertEqual(
            tuple(item.name for item in InterruptSubsystemOutcome),
            (
                "COMPLETED",
                "REQUESTED",
                "NOT_ACTIVE",
                "ALREADY_TERMINAL",
                "UNSUPPORTED",
                "TIMED_OUT",
                "ALREADY_CLOSED",
                "FAILED",
            ),
        )
        self.assertEqual(
            tuple(item.name for item in InterruptAggregateOutcome),
            (
                "COMPLETED",
                "PARTIAL",
                "REQUESTED",
                "NO_ACTIVE_TURN",
                "ALREADY_TERMINAL",
                "UNSUPPORTED",
                "TIMED_OUT",
                "ALREADY_CLOSED",
                "FAILED",
            ),
        )

    def test_interrupt_request_adds_only_trailing_optional_timeout(self) -> None:
        names = tuple(item.name for item in fields(InterruptRequest))
        self.assertEqual(
            names[:-1],
            (
                "scope",
                "reason",
                "turn_id",
                "flush_output",
                "cancel_tts_queue",
                "cancel_llm_stream",
                "stop_motion",
                "public_metadata",
            ),
        )
        self.assertEqual(names[-1], "timeout_seconds")
        self.assertIsNone(InterruptRequest().timeout_seconds)
        self.assertEqual(
            InterruptRequest.user_barge_in(timeout_seconds=0.25).timeout_seconds,
            0.25,
        )

    def test_interrupt_request_timeout_must_be_positive_and_finite(self) -> None:
        for invalid in (0, -1, float("inf"), float("nan")):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite and greater"):
                    InterruptRequest(timeout_seconds=invalid)
        with self.assertRaisesRegex(TypeError, "number or None"):
            InterruptRequest(timeout_seconds=True)

    def test_completed_subsystem_is_correlated_and_public_safe(self) -> None:
        session_id, turn_id, generation_id = _identity()
        result = InterruptSubsystemResult(
            subsystem="text_generation",
            outcome="completed",
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
            target_reached=True,
            cooperative_cancel_requested=True,
            cooperative_cancel_accepted=True,
            cooperative_cancel_completed=True,
            future_delivery_suppressed=True,
            safe_message="Text generation stopped.",
            public_metadata={"token": "PRIVATE_TOKEN_VALUE"},
        )
        self.assertIs(result.subsystem, InterruptSubsystem.TEXT_GENERATION)
        self.assertIs(result.outcome, InterruptSubsystemOutcome.COMPLETED)
        self.assertTrue(result.effective)
        self.assertTrue(result.is_terminal)
        self.assertNotIn("PRIVATE_TOKEN_VALUE", repr(result))

    def test_requested_and_timed_out_require_incomplete_accepted_cancel(self) -> None:
        session_id, turn_id, generation_id = _identity()
        for outcome in (
            InterruptSubsystemOutcome.REQUESTED,
            InterruptSubsystemOutcome.TIMED_OUT,
        ):
            result = InterruptSubsystemResult(
                subsystem=InterruptSubsystem.TTS_GENERATION,
                outcome=outcome,
                session_id=session_id,
                turn_id=turn_id,
                generation_id=generation_id,
                target_reached=True,
                cooperative_cancel_requested=True,
                cooperative_cancel_accepted=True,
            )
            self.assertEqual(
                result.is_terminal,
                outcome is InterruptSubsystemOutcome.TIMED_OUT,
            )
        with self.assertRaisesRegex(ValueError, "accepted but incomplete"):
            InterruptSubsystemResult(
                subsystem=InterruptSubsystem.TTS_GENERATION,
                outcome=InterruptSubsystemOutcome.REQUESTED,
                session_id=session_id,
                turn_id=turn_id,
                target_reached=True,
                cooperative_cancel_requested=True,
            )

    def test_provider_hard_cancel_is_not_inferred(self) -> None:
        session_id, turn_id, _ = _identity()
        with self.assertRaisesRegex(ValueError, "advertised support"):
            InterruptSubsystemResult(
                subsystem=InterruptSubsystem.MOTION,
                outcome=InterruptSubsystemOutcome.COMPLETED,
                session_id=session_id,
                turn_id=turn_id,
                target_reached=True,
                provider_hard_cancel_applied=True,
            )

    def test_unsupported_result_cannot_overclaim_effects(self) -> None:
        session_id, turn_id, _ = _identity()
        result = InterruptSubsystemResult(
            subsystem=InterruptSubsystem.TTS_QUEUE,
            outcome=InterruptSubsystemOutcome.UNSUPPORTED,
            session_id=session_id,
            turn_id=turn_id,
            target_reached=True,
            cooperative_cancel_requested=True,
        )
        self.assertFalse(result.effective)
        with self.assertRaisesRegex(ValueError, "must not claim"):
            InterruptSubsystemResult(
                subsystem=InterruptSubsystem.TTS_QUEUE,
                outcome=InterruptSubsystemOutcome.UNSUPPORTED,
                session_id=session_id,
                turn_id=turn_id,
                target_reached=True,
                future_delivery_suppressed=True,
            )

    def test_closed_result_cannot_claim_subsystem_reach(self) -> None:
        session_id, turn_id, _ = _identity()
        with self.assertRaisesRegex(ValueError, "must not claim target reach"):
            InterruptSubsystemResult(
                subsystem=InterruptSubsystem.AUDIO_ARTIFACT,
                outcome=InterruptSubsystemOutcome.ALREADY_CLOSED,
                session_id=session_id,
                turn_id=turn_id,
                target_reached=True,
            )

    def test_aggregate_completed_is_derived_from_all_results(self) -> None:
        session_id, turn_id, generation_id = _identity()
        aggregate = InterruptAggregateResult.from_results(
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=(
                _completed(
                    InterruptSubsystem.TEXT_GENERATION,
                    session_id=session_id,
                    turn_id=turn_id,
                    generation_id=generation_id,
                ),
                _completed(
                    InterruptSubsystem.MOTION,
                    session_id=session_id,
                    turn_id=turn_id,
                ),
            ),
            timeout_seconds=0.5,
        )
        self.assertIs(aggregate.outcome, InterruptAggregateOutcome.COMPLETED)
        self.assertEqual(aggregate.completed_count, 2)
        self.assertEqual(aggregate.timed_out_count, 0)
        self.assertTrue(aggregate.is_terminal)

    def test_mixed_results_derive_partial_without_overclaim(self) -> None:
        session_id, turn_id, _ = _identity()
        aggregate = InterruptAggregateResult.from_results(
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=(
                _completed(
                    InterruptSubsystem.TEXT_GENERATION,
                    session_id=session_id,
                    turn_id=turn_id,
                ),
                InterruptSubsystemResult(
                    subsystem=InterruptSubsystem.TTS_QUEUE,
                    outcome=InterruptSubsystemOutcome.UNSUPPORTED,
                    session_id=session_id,
                    turn_id=turn_id,
                    target_reached=True,
                ),
            ),
        )
        self.assertIs(aggregate.outcome, InterruptAggregateOutcome.PARTIAL)
        self.assertTrue(aggregate.partial)

    def test_partial_aggregate_is_terminal_only_when_each_result_is_terminal(self) -> None:
        session_id, turn_id, _ = _identity()
        requested = InterruptSubsystemResult(
            subsystem=InterruptSubsystem.TEXT_GENERATION,
            outcome=InterruptSubsystemOutcome.REQUESTED,
            session_id=session_id,
            turn_id=turn_id,
            target_reached=True,
            cooperative_cancel_requested=True,
            cooperative_cancel_accepted=True,
        )
        unsupported = InterruptSubsystemResult(
            subsystem=InterruptSubsystem.TTS_QUEUE,
            outcome=InterruptSubsystemOutcome.UNSUPPORTED,
            session_id=session_id,
            turn_id=turn_id,
            target_reached=True,
        )
        aggregate = InterruptAggregateResult.from_results(
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=(requested, unsupported),
        )
        self.assertIs(aggregate.outcome, InterruptAggregateOutcome.PARTIAL)
        self.assertFalse(aggregate.is_terminal)

    def test_uniform_no_active_results_derive_no_active_turn(self) -> None:
        session_id, turn_id, _ = _identity()
        aggregate = InterruptAggregateResult.from_results(
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=(
                InterruptSubsystemResult(
                    subsystem=InterruptSubsystem.TEXT_GENERATION,
                    outcome=InterruptSubsystemOutcome.NOT_ACTIVE,
                    session_id=session_id,
                    turn_id=turn_id,
                    target_reached=True,
                ),
                InterruptSubsystemResult(
                    subsystem=InterruptSubsystem.MOTION,
                    outcome=InterruptSubsystemOutcome.NOT_ACTIVE,
                    session_id=session_id,
                    turn_id=turn_id,
                    target_reached=True,
                ),
            ),
        )
        self.assertIs(
            aggregate.outcome,
            InterruptAggregateOutcome.NO_ACTIVE_TURN,
        )

    def test_direct_aggregate_outcome_overclaim_is_rejected(self) -> None:
        session_id, turn_id, _ = _identity()
        unsupported = InterruptSubsystemResult(
            subsystem=InterruptSubsystem.TTS_QUEUE,
            outcome=InterruptSubsystemOutcome.UNSUPPORTED,
            session_id=session_id,
            turn_id=turn_id,
            target_reached=True,
        )
        with self.assertRaisesRegex(ValueError, "must be derived as unsupported"):
            InterruptAggregateResult(
                outcome=InterruptAggregateOutcome.COMPLETED,
                session_id=session_id,
                turn_id=turn_id,
                subsystem_results=(unsupported,),
            )

    def test_aggregate_rejects_duplicate_or_mismatched_subsystems(self) -> None:
        session_id, turn_id, _ = _identity()
        completed = _completed(
            InterruptSubsystem.AUDIO_ARTIFACT,
            session_id=session_id,
            turn_id=turn_id,
        )
        with self.assertRaisesRegex(ValueError, "unique subsystems"):
            InterruptAggregateResult.from_results(
                session_id=session_id,
                turn_id=turn_id,
                subsystem_results=(completed, completed),
            )
        with self.assertRaisesRegex(ValueError, "session_id must match"):
            InterruptAggregateResult.from_results(
                session_id=SessionId.new(),
                turn_id=turn_id,
                subsystem_results=(completed,),
            )

    def test_interrupt_result_projection_preserves_accepted_field_prefix(self) -> None:
        session_id, turn_id, _ = _identity()
        aggregate = InterruptAggregateResult.from_results(
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=(
                InterruptSubsystemResult(
                    subsystem=InterruptSubsystem.MOTION,
                    outcome=InterruptSubsystemOutcome.NOT_ACTIVE,
                    session_id=session_id,
                    turn_id=turn_id,
                    target_reached=True,
                ),
            ),
        )
        result = InterruptResult(
            outcome=InterruptOutcome.NO_ACTIVE_TURN,
            turn_id=turn_id,
            coordination_result=aggregate,
        )
        self.assertIs(result.coordination_result, aggregate)
        self.assertEqual(
            tuple(item.name for item in fields(InterruptResult))[9:],
            ("motion_result",),
        )
        parameters = tuple(signature(InterruptResult).parameters)
        self.assertEqual(parameters[-2:], ("motion_result", "coordination_result"))
        self.assertIsNone(InterruptResult.not_implemented().coordination_result)

    def test_interrupt_result_rejects_bad_or_mismatched_aggregate(self) -> None:
        session_id, turn_id, _ = _identity()
        aggregate = InterruptAggregateResult.from_results(
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=(
                InterruptSubsystemResult(
                    subsystem=InterruptSubsystem.MOTION,
                    outcome=InterruptSubsystemOutcome.NOT_ACTIVE,
                    session_id=session_id,
                    turn_id=turn_id,
                    target_reached=True,
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "turn_id must match"):
            InterruptResult(
                outcome=InterruptOutcome.NO_ACTIVE_TURN,
                turn_id=TurnId.new(),
                coordination_result=aggregate,
            )
        with self.assertRaisesRegex(TypeError, "InterruptAggregateResult"):
            InterruptResult(
                outcome=InterruptOutcome.NO_ACTIVE_TURN,
                coordination_result=object(),  # type: ignore[arg-type]
            )

    def test_root_versions_and_runtime_remain_unchanged(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        for name in (
            "InterruptAggregateOutcome",
            "InterruptAggregateResult",
            "InterruptSubsystem",
            "InterruptSubsystemOutcome",
            "InterruptSubsystemResult",
        ):
            self.assertNotIn(name, framework.__all__)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        self.assertFalse(hasattr(framework.RealtimeSession, "interrupt_coordinator"))


if __name__ == "__main__":
    unittest.main()
