"""Provider-free tests for FW-RT6-10a Control A recovery planning."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import sys
import unittest

import framework
from framework.identity import GenerationId
from framework.lifecycle import RecoveryAction
from framework.recovery_control import (
    RecoveryControlDisposition,
    RecoveryControlPlan,
    RecoveryResetErrorCode,
    RecoveryResetOutcome,
    RecoveryResetResult,
    RecoveryResetScope,
    build_recovery_control_plan,
)


class RecoveryControlATests(unittest.TestCase):
    def test_explicit_package_exports_are_exact_and_root_surface_is_unchanged(self) -> None:
        import framework.recovery_control as control

        self.assertEqual(
            tuple(control.__all__),
            (
                "RecoveryResetScope",
                "RecoveryControlDisposition",
                "RecoveryResetOutcome",
                "RecoveryResetErrorCode",
                "RecoveryControlPlan",
                "RecoveryResetResult",
                "build_recovery_control_plan",
            ),
        )
        self.assertNotIn("RecoveryControlPlan", framework.__all__)
        self.assertEqual(len(framework.__all__), 127)

    def test_none_and_reuse_session_require_no_reset(self) -> None:
        for action in (RecoveryAction.NONE, RecoveryAction.REUSE_SESSION):
            plan = build_recovery_control_plan(action)
            self.assertIs(plan.disposition, RecoveryControlDisposition.REUSE_SESSION)
            self.assertIsNone(plan.reset_scope)
            self.assertFalse(plan.execute_reset)
            self.assertFalse(plan.generation_advance_required)
            self.assertFalse(plan.reconnect_required)
            self.assertFalse(plan.close_required)

    def test_turn_reset_has_explicit_scope_and_generation_requirement(self) -> None:
        plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)

        self.assertIs(plan.disposition, RecoveryControlDisposition.RESET_TURN)
        self.assertIs(plan.reset_scope, RecoveryResetScope.TURN_ONLY)
        self.assertTrue(plan.execute_reset)
        self.assertTrue(plan.generation_advance_required)
        self.assertFalse(plan.reconnect_required)
        self.assertFalse(plan.close_required)

    def test_session_reset_has_explicit_scope_and_generation_requirement(self) -> None:
        plan = build_recovery_control_plan(RecoveryAction.RESET_SESSION)

        self.assertIs(plan.disposition, RecoveryControlDisposition.RESET_SESSION)
        self.assertIs(plan.reset_scope, RecoveryResetScope.SESSION)
        self.assertTrue(plan.execute_reset)
        self.assertTrue(plan.generation_advance_required)
        self.assertFalse(plan.reconnect_required)
        self.assertFalse(plan.close_required)

    def test_reconnect_action_is_required_without_false_reset_execution(self) -> None:
        plan = build_recovery_control_plan(RecoveryAction.RECONNECT)

        self.assertIs(
            plan.disposition,
            RecoveryControlDisposition.RECONNECT_REQUIRED,
        )
        self.assertTrue(plan.reconnect_required)
        self.assertFalse(plan.execute_reset)
        self.assertIsNone(plan.reset_scope)

    def test_close_action_is_required_without_false_reset_execution(self) -> None:
        plan = build_recovery_control_plan(RecoveryAction.CLOSE_SESSION)

        self.assertIs(plan.disposition, RecoveryControlDisposition.CLOSE_REQUIRED)
        self.assertTrue(plan.close_required)
        self.assertFalse(plan.permanently_failed)
        self.assertFalse(plan.execute_reset)

    def test_permanent_failure_requires_close_and_cannot_claim_reset(self) -> None:
        plan = build_recovery_control_plan(RecoveryAction.PERMANENT_FAILURE)

        self.assertIs(
            plan.disposition,
            RecoveryControlDisposition.PERMANENTLY_FAILED,
        )
        self.assertTrue(plan.close_required)
        self.assertTrue(plan.permanently_failed)
        self.assertFalse(plan.execute_reset)
        self.assertFalse(plan.reconnect_required)

    def test_reset_plans_document_exact_provider_context_loss(self) -> None:
        turn = build_recovery_control_plan(RecoveryAction.RESET_TURN)
        session = build_recovery_control_plan(RecoveryAction.RESET_SESSION)

        self.assertEqual(
            turn.provider_context_loss,
            ("active_turn_provider_context", "in_flight_stage_context"),
        )
        self.assertEqual(
            session.provider_context_loss,
            (
                "active_turn_provider_context",
                "provider_conversation_context",
                "provider_session_context",
                "in_flight_stage_context",
            ),
        )

    def test_plan_rejects_inconsistent_scope_or_effect_claims(self) -> None:
        with self.assertRaisesRegex(ValueError, "do not match"):
            RecoveryControlPlan(
                requested_action=RecoveryAction.RESET_TURN,
                disposition=RecoveryControlDisposition.RESET_TURN,
                reset_scope=RecoveryResetScope.SESSION,
                execute_reset=True,
                generation_advance_required=True,
                reconnect_required=False,
                close_required=False,
                permanently_failed=False,
                provider_context_loss=(
                    "active_turn_provider_context",
                    "in_flight_stage_context",
                ),
            )

    def test_non_reset_plans_produce_typed_non_executing_results(self) -> None:
        expected = {
            RecoveryAction.REUSE_SESSION: RecoveryResetOutcome.NOT_REQUIRED,
            RecoveryAction.RECONNECT: RecoveryResetOutcome.RECONNECT_REQUIRED,
            RecoveryAction.CLOSE_SESSION: RecoveryResetOutcome.CLOSE_REQUIRED,
            RecoveryAction.PERMANENT_FAILURE: (
                RecoveryResetOutcome.PERMANENTLY_FAILED
            ),
        }
        for action, outcome in expected.items():
            result = RecoveryResetResult.for_non_reset_plan(
                build_recovery_control_plan(action)
            )
            self.assertIs(result.outcome, outcome)
            self.assertIs(result.error_code, RecoveryResetErrorCode.NONE)
            self.assertFalse(result.generation_advanced)

    def test_applied_result_requires_one_distinct_replacement_generation(self) -> None:
        plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)
        previous = GenerationId.new()
        current = GenerationId.new()

        result = RecoveryResetResult.applied(
            plan,
            previous_generation_id=previous,
            current_generation_id=current,
        )

        self.assertIs(result.outcome, RecoveryResetOutcome.APPLIED)
        self.assertTrue(result.generation_advanced)
        self.assertEqual(result.previous_generation_id, previous)
        self.assertEqual(result.current_generation_id, current)
        with self.assertRaisesRegex(ValueError, "distinct generations"):
            RecoveryResetResult.applied(
                plan,
                previous_generation_id=previous,
                current_generation_id=previous,
            )

    def test_reset_failure_is_typed_safe_and_does_not_claim_generation_advance(self) -> None:
        plan = build_recovery_control_plan(RecoveryAction.RESET_SESSION)
        result = RecoveryResetResult.failed(
            plan,
            error_code=RecoveryResetErrorCode.PROVIDER_RESET_FAILED,
            safe_message="Realtime provider context could not be reset safely.",
            retryable=True,
        )

        self.assertIs(result.outcome, RecoveryResetOutcome.FAILED)
        self.assertIs(
            result.error_code,
            RecoveryResetErrorCode.PROVIDER_RESET_FAILED,
        )
        self.assertFalse(result.generation_advanced)
        self.assertTrue(result.retryable)
        self.assertNotIn("exception", result.safe_message.lower())

    def test_plan_is_immutable_public_safe_and_runtime_adoption_is_deferred(self) -> None:
        plan = build_recovery_control_plan(
            RecoveryAction.RESET_SESSION,
            public_metadata={"secret": "should-not-leak"},
        )

        self.assertEqual(plan.public_metadata["secret"], "<redacted>")
        self.assertNotIn("should-not-leak", repr(plan))
        self.assertFalse(plan.decision_is_execution)
        self.assertTrue(plan.side_effect_free)
        with self.assertRaises(FrozenInstanceError):
            plan.execute_reset = False  # type: ignore[misc]

        self.assertFalse(hasattr(framework.RealtimeSession, "reset"))
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
            self.assertNotIn(module_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
