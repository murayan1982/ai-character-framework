"""Provider-free tests for FW-RT6-9c Control B runtime adoption."""

from __future__ import annotations

from dataclasses import fields
from threading import Event, Lock, Thread
import inspect
import sys
import unittest

import framework
from framework.barge_in_control import build_barge_in_control_plan
from framework.output_control import (
    BargeInDecision,
    BargeInPolicy,
    BargeInPolicyMode,
    InterruptOutcome,
    InterruptReason,
    InterruptResult,
)
from framework.realtime_capabilities import (
    RealtimeCapabilitySnapshot,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind


def _runtime() -> RuntimeCapabilityState:
    return RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=False,
        fake_runtime=False,
        real_runtime=True,
        unavailable_reason=None,
        public_metadata={"provider_execution_performed": False},
    )


class _CancelableTextStage:
    stage_kind = RealtimeStageKind.TEXT_GENERATION

    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self._lock = Lock()
        self.cancel_count = 0
        self.close_count = 0
        self._capability = TextGenerationCapability(
            runtime=_runtime(),
            streaming_supported=True,
            cooperative_cancel_supported=True,
            provider_hard_cancel_supported=False,
        )

    def preflight(self):
        return self._capability

    def capability(self):
        return self._capability

    def start(self, *, context, request):
        del context, request
        self.started.set()
        if not self.release.wait(timeout=3.0):
            raise RuntimeError("barge-in test stage was not released")
        return object()

    def cancel(self, *, context):
        del context
        with self._lock:
            self.cancel_count += 1
        self.release.set()
        return True

    def close(self) -> None:
        with self._lock:
            self.close_count += 1
        self.release.set()


class _CaptureSession(framework.RealtimeSession):
    def __init__(self) -> None:
        super().__init__()
        self.delegated_request = None
        self.advance_reason = None

    def _ordered_interrupt(self, request, *, advance_reason):
        self.delegated_request = request
        self.advance_reason = advance_reason
        return InterruptResult.no_active_turn(request=request)


def _start_active_stage(session, stage: _CancelableTextStage):
    started = session.start_turn(input_text="barge-in runtime adoption")
    if not started.accepted or started.generation_id is None:
        raise AssertionError("barge-in test turn was not admitted")
    context = RealtimeStageContext(
        session_id=started.session_id,
        turn_id=started.turn_id,
        generation_id=started.generation_id,
    )
    thread = Thread(
        target=lambda: session._execute_interruptible_stage(
            stage_kind="text_generation",
            context=context,
            request=object(),
        ),
        daemon=True,
    )
    thread.start()
    if not stage.started.wait(timeout=3.0):
        raise AssertionError("barge-in test stage did not start")
    return started, thread


def _plan(session, policy: BargeInPolicy, *, turn_id=None):
    decision = BargeInDecision.accepted_for_policy(policy, turn_id=turn_id)
    return build_barge_in_control_plan(
        decision,
        capabilities=session.capabilities,
    )


class BargeInControlBTests(unittest.TestCase):
    def test_flush_policy_factory_and_boolean_field_do_not_collide(self) -> None:
        self.assertIs(BargeInPolicy().flush_output, False)
        self.assertIs(BargeInPolicy.disabled().flush_output, False)
        self.assertIs(BargeInPolicy.soft_interrupt().flush_output, False)
        self.assertIs(BargeInPolicy.flush_output().flush_output, True)
        self.assertIs(fields(BargeInPolicy)[2].default, False)

    def test_execute_requires_one_control_plan(self) -> None:
        session = framework.create_realtime_session()
        with self.assertRaisesRegex(TypeError, "BargeInControlPlan"):
            session.execute_barge_in(  # type: ignore[arg-type]
                BargeInDecision.rejected()
            )

    def test_decision_remains_separate_from_interrupt_execution(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="decision only")
        session.set_barge_in_policy(BargeInPolicy.soft_interrupt())
        decision = session.decide_barge_in(turn_id=started.turn_id)

        self.assertTrue(decision.accepted)
        self.assertFalse(decision.should_flush_queue)
        self.assertEqual(session.terminal_results, ())
        event_types = [event.type for event in session.event_history]
        self.assertNotIn(framework.RealtimeEventType.INTERRUPT_REQUESTED, event_types)
        self.assertNotIn(framework.RealtimeEventType.TURN_INTERRUPTED, event_types)

    def test_exact_plan_request_is_delegated_without_reinterpretation(self) -> None:
        session = _CaptureSession()
        plan = _plan(session, BargeInPolicy.soft_interrupt(), turn_id="turn-plan")
        expected = plan.coordinator_request
        result = session.execute_barge_in(plan)

        self.assertIsNotNone(expected)
        self.assertIs(session.delegated_request, expected)
        self.assertEqual(session.advance_reason, "interrupt")
        self.assertIs(result.reason, InterruptReason.USER_BARGE_IN)

    def test_soft_plan_reaches_existing_ordered_interrupt_owner(self) -> None:
        stage = _CancelableTextStage()
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, stage_thread = _start_active_stage(session, stage)
        session.set_barge_in_policy(BargeInPolicy.soft_interrupt())
        decision = session.decide_barge_in(turn_id=started.turn_id)
        plan = build_barge_in_control_plan(
            decision,
            capabilities=session.capabilities,
        )

        result = session.execute_barge_in(plan)
        stage_thread.join(timeout=3.0)

        self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
        self.assertEqual(stage.cancel_count, 1)
        self.assertEqual(session.terminal_results[0].outcome.value, "interrupted")
        event_types = [event.type for event in session.event_history]
        ordered = (
            framework.RealtimeEventType.BARGE_IN_DETECTED,
            framework.RealtimeEventType.BARGE_IN_ACCEPTED,
            framework.RealtimeEventType.INTERRUPT_REQUESTED,
            framework.RealtimeEventType.INTERRUPT_ACCEPTED,
            framework.RealtimeEventType.INTERRUPT_COMPLETED,
            framework.RealtimeEventType.TURN_INTERRUPTED,
        )
        positions = tuple(event_types.index(event_type) for event_type in ordered)
        self.assertEqual(positions, tuple(sorted(positions)))

    def test_hard_cancel_downgrade_executes_only_supported_soft_request(self) -> None:
        stage = _CancelableTextStage()
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, stage_thread = _start_active_stage(session, stage)
        plan = _plan(
            session,
            BargeInPolicy.hard_cancel(),
            turn_id=started.turn_id,
        )
        request = plan.coordinator_request

        self.assertIs(plan.requested_mode, BargeInPolicyMode.HARD_CANCEL)
        self.assertIs(plan.effective_mode, BargeInPolicyMode.SOFT_INTERRUPT)
        self.assertTrue(plan.capability_downgraded)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertFalse(request.cancel_llm_stream)
        self.assertFalse(request.cancel_tts_queue)
        self.assertFalse(request.flush_output)

        result = session.execute_barge_in(plan)
        stage_thread.join(timeout=3.0)
        self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
        self.assertFalse(result.provider_cancel_supported)
        self.assertEqual(stage.cancel_count, 1)

    def test_unsupported_flush_plan_has_no_interrupt_or_flush_effect(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="unsupported flush")
        plan = _plan(
            session,
            BargeInPolicy.flush_output(),
            turn_id=started.turn_id,
        )
        before = tuple(session.event_history)
        result = session.execute_barge_in(plan)

        self.assertFalse(plan.execute_interrupt)
        self.assertIsNone(plan.coordinator_request)
        self.assertIs(result.outcome, InterruptOutcome.UNSUPPORTED)
        self.assertEqual(tuple(session.event_history), before)
        self.assertEqual(session.terminal_results, ())
        self.assertFalse(result.public_metadata["delegated_to_interrupt_coordinator"])

    def test_rejected_plan_is_typed_nonexecuting_result(self) -> None:
        session = framework.create_realtime_session()
        plan = build_barge_in_control_plan(
            BargeInDecision.rejected(),
            capabilities=session.capabilities,
        )
        result = session.execute_barge_in(plan)

        self.assertIs(result.outcome, InterruptOutcome.UNSUPPORTED)
        self.assertIs(result.reason, InterruptReason.USER_BARGE_IN)
        self.assertEqual(session.event_history, ())

    def test_plan_capabilities_must_match_executing_session(self) -> None:
        session = framework.create_realtime_session()
        plan = build_barge_in_control_plan(
            BargeInDecision.accepted_for_policy(BargeInPolicy.hard_cancel()),
            capabilities=RealtimeCapabilitySnapshot(
                session_id=session.capabilities.session_id,
                hard_cancel_supported=True,
                tts_queue_flush_supported=True,
            ),
        )
        with self.assertRaisesRegex(ValueError, "executing session"):
            session.execute_barge_in(plan)

    def test_duplicate_execution_replays_exact_owner_result_once(self) -> None:
        stage = _CancelableTextStage()
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, stage_thread = _start_active_stage(session, stage)
        plan = _plan(
            session,
            BargeInPolicy.soft_interrupt(),
            turn_id=started.turn_id,
        )

        first = session.execute_barge_in(plan)
        stage_thread.join(timeout=3.0)
        second = session.execute_barge_in(plan)

        self.assertIs(second, first)
        self.assertEqual(stage.cancel_count, 1)
        event_types = [event.type for event in session.event_history]
        self.assertEqual(
            event_types.count(framework.RealtimeEventType.INTERRUPT_REQUESTED),
            1,
        )
        self.assertEqual(
            event_types.count(framework.RealtimeEventType.TURN_INTERRUPTED),
            1,
        )

    def test_closed_session_returns_closed_without_execution(self) -> None:
        session = framework.create_realtime_session()
        plan = _plan(session, BargeInPolicy.soft_interrupt(), turn_id="turn-closed")
        session.close()
        result = session.execute_barge_in(plan)
        self.assertIs(result.outcome, InterruptOutcome.ALREADY_CLOSED)

    def test_public_surface_versions_and_provider_safety_remain_unchanged(self) -> None:
        self.assertIn("plan", inspect.signature(framework.RealtimeSession.execute_barge_in).parameters)
        self.assertNotIn("execute_barge_in", framework.__all__)
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
            self.assertNotIn(module_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
