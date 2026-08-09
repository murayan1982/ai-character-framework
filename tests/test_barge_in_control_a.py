"""Provider-free tests for FW-RT6-9c Control A barge-in planning."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import sys
import unittest

import framework
from framework.barge_in_control import (
    BargeInControlPlan,
    build_barge_in_control_plan,
)
from framework.identity import SessionId
from framework.output_control import (
    BargeInDecision,
    BargeInPolicy,
    BargeInPolicyMode,
    InterruptReason,
    InterruptScope,
)
from framework.realtime_capabilities import RealtimeCapabilitySnapshot


def _capabilities(
    *,
    hard_cancel: bool = False,
    queue_flush: bool = False,
) -> RealtimeCapabilitySnapshot:
    return RealtimeCapabilitySnapshot(
        session_id=SessionId.new(),
        hard_cancel_supported=hard_cancel,
        tts_queue_flush_supported=queue_flush,
    )


def _decision(policy: BargeInPolicy) -> BargeInDecision:
    return BargeInDecision.accepted_for_policy(
        policy,
        turn_id="turn-barge-in",
        public_metadata={"secret": "should-not-leak"},
    )


class BargeInControlATests(unittest.TestCase):
    def test_explicit_package_exports_are_exact_and_root_stays_lazy(self) -> None:
        import framework.barge_in_control as control

        self.assertEqual(
            tuple(control.__all__),
            ("BargeInControlPlan", "build_barge_in_control_plan"),
        )
        self.assertNotIn("BargeInControlPlan", framework.__all__)
        self.assertEqual(len(framework.__all__), 127)

    def test_rejected_decision_builds_a_non_executing_plan(self) -> None:
        decision = BargeInDecision.rejected(policy=BargeInPolicy.disabled())
        plan = build_barge_in_control_plan(
            decision,
            capabilities=_capabilities(),
        )
        self.assertIs(plan.requested_mode, BargeInPolicyMode.DISABLED)
        self.assertIs(plan.effective_mode, BargeInPolicyMode.DISABLED)
        self.assertFalse(plan.execute_interrupt)
        self.assertIsNone(plan.coordinator_request)
        self.assertFalse(plan.decision_is_execution)
        self.assertTrue(plan.side_effect_free)

    def test_soft_interrupt_plan_is_capability_independent(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.soft_interrupt()),
            capabilities=_capabilities(),
        )
        request = plan.coordinator_request
        self.assertTrue(plan.execute_interrupt)
        self.assertIs(plan.effective_mode, BargeInPolicyMode.SOFT_INTERRUPT)
        self.assertFalse(plan.capability_downgraded)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertIs(request.scope, InterruptScope.CURRENT_TURN)
        self.assertIs(request.reason, InterruptReason.USER_BARGE_IN)
        self.assertFalse(request.flush_output)
        self.assertFalse(request.cancel_tts_queue)
        self.assertFalse(request.cancel_llm_stream)

    def test_supported_flush_builds_queue_only_control(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.flush_output()),
            capabilities=_capabilities(queue_flush=True),
        )
        request = plan.coordinator_request
        self.assertIs(plan.effective_mode, BargeInPolicyMode.FLUSH_OUTPUT)
        self.assertTrue(plan.queue_flush_requested)
        self.assertTrue(plan.queue_flush_supported)
        self.assertTrue(plan.queue_flush_planned)
        self.assertFalse(plan.capability_downgraded)
        assert request is not None
        self.assertIs(request.scope, InterruptScope.TTS_QUEUE)
        self.assertTrue(request.flush_output)
        self.assertFalse(request.cancel_tts_queue)
        self.assertFalse(request.cancel_llm_stream)
        self.assertFalse(request.stop_motion)

    def test_unsupported_flush_downgrades_without_claiming_execution(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.flush_output()),
            capabilities=_capabilities(queue_flush=False),
        )
        self.assertTrue(plan.capability_downgraded)
        self.assertIs(plan.effective_mode, BargeInPolicyMode.DISABLED)
        self.assertFalse(plan.execute_interrupt)
        self.assertFalse(plan.queue_flush_planned)
        self.assertIsNone(plan.coordinator_request)

    def test_supported_hard_cancel_retains_requested_mode(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.hard_cancel()),
            capabilities=_capabilities(hard_cancel=True, queue_flush=True),
        )
        request = plan.coordinator_request
        self.assertIs(plan.effective_mode, BargeInPolicyMode.HARD_CANCEL)
        self.assertTrue(plan.provider_hard_cancel_requested)
        self.assertTrue(plan.provider_hard_cancel_supported)
        self.assertTrue(plan.provider_hard_cancel_planned)
        self.assertTrue(plan.queue_flush_planned)
        self.assertFalse(plan.capability_downgraded)
        assert request is not None
        self.assertTrue(request.cancel_llm_stream)
        self.assertTrue(request.cancel_tts_queue)
        self.assertTrue(request.flush_output)
        self.assertTrue(request.stop_motion)

    def test_unsupported_hard_cancel_truthfully_downgrades_to_soft(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.hard_cancel()),
            capabilities=_capabilities(),
        )
        request = plan.coordinator_request
        self.assertIs(plan.requested_mode, BargeInPolicyMode.HARD_CANCEL)
        self.assertIs(plan.effective_mode, BargeInPolicyMode.SOFT_INTERRUPT)
        self.assertTrue(plan.provider_hard_cancel_requested)
        self.assertFalse(plan.provider_hard_cancel_supported)
        self.assertFalse(plan.provider_hard_cancel_planned)
        self.assertTrue(plan.capability_downgraded)
        assert request is not None
        self.assertIs(request.scope, InterruptScope.CURRENT_TURN)
        self.assertFalse(request.cancel_llm_stream)
        self.assertFalse(request.cancel_tts_queue)
        self.assertFalse(request.flush_output)

    def test_partial_hard_cancel_plan_keeps_only_supported_flush(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.hard_cancel()),
            capabilities=_capabilities(queue_flush=True),
        )
        request = plan.coordinator_request
        self.assertIs(plan.effective_mode, BargeInPolicyMode.SOFT_INTERRUPT)
        self.assertFalse(plan.provider_hard_cancel_planned)
        self.assertTrue(plan.queue_flush_planned)
        self.assertTrue(plan.capability_downgraded)
        assert request is not None
        self.assertFalse(request.cancel_llm_stream)
        self.assertTrue(request.cancel_tts_queue)
        self.assertTrue(request.flush_output)

    def test_turn_takeover_intent_is_preserved_across_downgrade(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.turn_takeover()),
            capabilities=_capabilities(),
        )
        self.assertTrue(plan.turn_takeover_requested)
        self.assertIs(plan.requested_mode, BargeInPolicyMode.TURN_TAKEOVER)
        self.assertIs(plan.effective_mode, BargeInPolicyMode.SOFT_INTERRUPT)
        self.assertTrue(plan.capability_downgraded)

    def test_plan_rejects_inconsistent_effect_and_capability_claims(self) -> None:
        decision = _decision(BargeInPolicy.hard_cancel())
        with self.assertRaisesRegex(ValueError, "overclaims capability"):
            BargeInControlPlan(
                decision=decision,
                requested_mode=BargeInPolicyMode.HARD_CANCEL,
                effective_mode=BargeInPolicyMode.SOFT_INTERRUPT,
                coordinator_request=decision.interrupt_request,
                execute_interrupt=True,
                provider_hard_cancel_requested=True,
                provider_hard_cancel_supported=False,
                provider_hard_cancel_planned=True,
                queue_flush_requested=True,
                queue_flush_supported=False,
                queue_flush_planned=False,
                turn_takeover_requested=False,
                capability_downgraded=True,
            )
        with self.assertRaisesRegex(ValueError, "microphone detection"):
            BargeInControlPlan(
                decision=BargeInDecision.rejected(),
                requested_mode=BargeInPolicyMode.DISABLED,
                effective_mode=BargeInPolicyMode.DISABLED,
                coordinator_request=None,
                execute_interrupt=False,
                provider_hard_cancel_requested=False,
                provider_hard_cancel_supported=False,
                provider_hard_cancel_planned=False,
                queue_flush_requested=False,
                queue_flush_supported=False,
                queue_flush_planned=False,
                turn_takeover_requested=False,
                capability_downgraded=False,
                microphone_detection_required=True,
            )

    def test_plan_is_immutable_and_metadata_is_public_safe(self) -> None:
        plan = build_barge_in_control_plan(
            _decision(BargeInPolicy.hard_cancel()),
            capabilities=_capabilities(),
        )
        self.assertEqual(
            plan.coordinator_request.public_metadata["secret"],  # type: ignore[union-attr]
            "<redacted>",
        )
        self.assertNotIn("should-not-leak", repr(plan))
        self.assertFalse(plan.microphone_detection_required)
        with self.assertRaises(FrozenInstanceError):
            plan.execute_interrupt = False  # type: ignore[misc]

    def test_control_a_does_not_adopt_runtime_or_import_provider_modules(self) -> None:
        from framework.realtime_session import RealtimeSession

        self.assertFalse(hasattr(RealtimeSession, "execute_barge_in"))
        for module_name in (
            "pyvts",
            "websockets",
            "pyaudio",
            "sounddevice",
        ):
            self.assertNotIn(module_name, sys.modules)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")


if __name__ == "__main__":
    unittest.main()
