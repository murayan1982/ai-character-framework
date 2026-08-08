"""Provider-free tests for FW-RT6-8c Control A typed motion control."""

from __future__ import annotations

from dataclasses import fields
import unittest

import framework
from framework.identity import GenerationId, SessionId, TurnId
from framework.motion_control import MotionControlOutcome, MotionControlResult
from framework.output_control import InterruptOutcome, InterruptResult
from framework.realtime_capabilities import (
    RealtimeMotionCapability,
    RuntimeCapabilityState,
)


def _identity() -> tuple[SessionId, TurnId, GenerationId]:
    return SessionId.new(), TurnId.new(), GenerationId.new()


class MotionControlControlATests(unittest.TestCase):
    def test_explicit_package_and_outcome_vocabulary_are_exact(self) -> None:
        import framework.motion_control as control

        self.assertEqual(
            tuple(control.__all__),
            ("MotionControlOutcome", "MotionControlResult"),
        )
        self.assertEqual(
            tuple(item.name for item in MotionControlOutcome),
            (
                "REQUESTED",
                "COMPLETED",
                "NOT_ACTIVE",
                "ALREADY_TERMINAL",
                "UNSUPPORTED",
                "TIMED_OUT",
                "ALREADY_CLOSED",
                "FAILED",
            ),
        )

    def test_requested_cancel_is_correlated_and_public_safe(self) -> None:
        session_id, turn_id, generation_id = _identity()
        result = MotionControlResult(
            outcome=MotionControlOutcome.REQUESTED,
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
            request_id="motion-request",
            cancel_requested=True,
            cancel_accepted=True,
            future_delivery_suppressed=True,
            safe_message="Motion cancellation was requested.",
            public_metadata={
                "boundary": "motion_control",
                "token": "PRIVATE_TOKEN_VALUE",
            },
        )

        self.assertEqual(result.session_id, session_id)
        self.assertEqual(result.turn_id, turn_id)
        self.assertEqual(result.generation_id, generation_id)
        self.assertTrue(result.effective)
        self.assertTrue(result.is_terminal)
        self.assertNotIn("PRIVATE_TOKEN_VALUE", repr(result))

    def test_completed_cancel_requires_truthful_completion(self) -> None:
        session_id, turn_id, generation_id = _identity()
        result = MotionControlResult(
            outcome="completed",
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
            request_id="motion-request",
            cancel_requested=True,
            cancel_accepted=True,
            cancel_completed=True,
            future_delivery_suppressed=True,
        )
        self.assertIs(result.outcome, MotionControlOutcome.COMPLETED)
        self.assertTrue(result.cancel_completed)

    def test_completed_stop_motion_is_independent_from_request_cancel(self) -> None:
        session_id, turn_id, generation_id = _identity()
        result = MotionControlResult(
            outcome=MotionControlOutcome.COMPLETED,
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
            request_id="stop-request",
            stop_motion_requested=True,
            stop_motion_supported=True,
            stop_motion_applied=True,
        )
        self.assertTrue(result.stop_motion_applied)
        self.assertFalse(result.cancel_requested)

    def test_unsupported_stop_motion_claims_no_effect(self) -> None:
        session_id, _, _ = _identity()
        result = MotionControlResult(
            outcome=MotionControlOutcome.UNSUPPORTED,
            session_id=session_id,
            stop_motion_requested=True,
            stop_motion_supported=False,
            safe_message="Stop motion is unsupported.",
        )
        self.assertFalse(result.effective)
        self.assertFalse(result.stop_motion_applied)

    def test_non_effect_outcome_rejects_cancel_or_stop_success(self) -> None:
        session_id, _, _ = _identity()
        with self.assertRaisesRegex(ValueError, "must not claim control effects"):
            MotionControlResult(
                outcome=MotionControlOutcome.UNSUPPORTED,
                session_id=session_id,
                cancel_requested=True,
                cancel_accepted=True,
            )
        with self.assertRaisesRegex(ValueError, "requested and supported"):
            MotionControlResult(
                outcome=MotionControlOutcome.NOT_ACTIVE,
                session_id=session_id,
                stop_motion_applied=True,
            )

    def test_active_outcomes_require_full_correlation(self) -> None:
        session_id, turn_id, generation_id = _identity()
        with self.assertRaisesRegex(ValueError, "require turn, generation"):
            MotionControlResult(
                outcome=MotionControlOutcome.FAILED,
                session_id=session_id,
                turn_id=turn_id,
                request_id="motion-request",
            )
        with self.assertRaisesRegex(ValueError, "generation_id requires turn_id"):
            MotionControlResult(
                outcome=MotionControlOutcome.NOT_ACTIVE,
                session_id=session_id,
                generation_id=generation_id,
            )

    def test_control_flags_require_actual_booleans(self) -> None:
        session_id, _, _ = _identity()
        with self.assertRaisesRegex(TypeError, "cancel_requested must be a boolean"):
            MotionControlResult(
                outcome=MotionControlOutcome.NOT_ACTIVE,
                session_id=session_id,
                cancel_requested=1,  # type: ignore[arg-type]
            )

    def test_interrupt_result_preserves_legacy_prefix_and_defaults(self) -> None:
        names = tuple(item.name for item in fields(InterruptResult))
        self.assertEqual(
            names[:9],
            (
                "outcome",
                "scope",
                "reason",
                "turn_id",
                "safe_message",
                "retryable",
                "provider_cancel_supported",
                "queue_flush_supported",
                "public_metadata",
            ),
        )
        self.assertEqual(names[9:], ("motion_result",))
        self.assertIsNone(InterruptResult.not_implemented().motion_result)

    def test_interrupt_result_accepts_only_correlated_motion_result(self) -> None:
        session_id, turn_id, generation_id = _identity()
        motion_result = MotionControlResult(
            outcome=MotionControlOutcome.REQUESTED,
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
            request_id="motion-request",
            cancel_requested=True,
            cancel_accepted=True,
            future_delivery_suppressed=True,
        )
        result = InterruptResult(
            outcome=InterruptOutcome.NOT_IMPLEMENTED,
            turn_id=turn_id,
            motion_result=motion_result,
        )
        self.assertIs(result.motion_result, motion_result)
        with self.assertRaisesRegex(ValueError, "turn_id must match"):
            InterruptResult(
                outcome=InterruptOutcome.NOT_IMPLEMENTED,
                turn_id=TurnId.new(),
                motion_result=motion_result,
            )
        with self.assertRaisesRegex(TypeError, "MotionControlResult"):
            InterruptResult(
                outcome=InterruptOutcome.NOT_IMPLEMENTED,
                motion_result=object(),  # type: ignore[arg-type]
            )

    def test_motion_capability_adds_truthful_stop_motion_flag(self) -> None:
        names = tuple(item.name for item in fields(RealtimeMotionCapability))
        self.assertEqual(
            names[:5],
            (
                "runtime",
                "request_cancel_supported",
                "completion_event_supported",
                "provider_neutral_intent_supported",
                "public_metadata",
            ),
        )
        self.assertEqual(names[5:], ("stop_motion_supported",))
        default = RealtimeMotionCapability()
        self.assertFalse(default.stop_motion_supported)
        self.assertFalse(default.as_dict()["stop_motion_supported"])
        supported = RealtimeMotionCapability(
            runtime=RuntimeCapabilityState(),
            stop_motion_supported=True,
        )
        self.assertTrue(supported.as_dict()["stop_motion_supported"])

    def test_root_versions_and_runtime_methods_remain_unchanged(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertNotIn("MotionControlOutcome", framework.__all__)
        self.assertNotIn("MotionControlResult", framework.__all__)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        self.assertFalse(hasattr(framework.MotionSession, "cancel_motion"))
        self.assertFalse(hasattr(framework.RealtimeSession, "cancel_motion"))


if __name__ == "__main__":
    unittest.main()
