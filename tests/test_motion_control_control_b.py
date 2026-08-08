"""Provider-free tests for FW-RT6-8c Control B runtime motion reach."""

from __future__ import annotations

import inspect
from threading import Event, Lock, Thread
import time
import unittest

import framework
from framework.motion import (
    MotionIntent,
    MotionOutcome,
    MotionRequest,
    MotionResult,
)
from framework.motion_control import MotionControlOutcome
from framework.motion_lifecycle import MotionLifecycleSignal
from framework.output_control import (
    InterruptOutcome,
    InterruptRequest,
    InterruptScope,
)
from framework.realtime_capabilities import (
    RealtimeMotionCapability,
    RuntimeCapabilityState,
)
from framework.realtime_stage import (
    RealtimeStageContext,
    RealtimeStageKind,
    RealtimeStageResultEnvelope,
)


def _ready_motion_capability(
    *,
    cancel_supported: bool = True,
    stop_supported: bool = False,
) -> RealtimeMotionCapability:
    return RealtimeMotionCapability(
        runtime=RuntimeCapabilityState(
            configured=True,
            runtime_available=True,
            guarded=False,
            fake_runtime=False,
            real_runtime=True,
            unavailable_reason=None,
            public_metadata={"provider_execution_performed": False},
        ),
        request_cancel_supported=cancel_supported,
        completion_event_supported=True,
        provider_neutral_intent_supported=True,
        stop_motion_supported=stop_supported,
    )


class _ControllableMotionStage:
    stage_kind = RealtimeStageKind.MOTION

    def __init__(
        self,
        *,
        cancel_supported: bool = True,
        cancel_accepted: bool = True,
        stop_supported: bool = False,
        stop_completed: bool = True,
        block_cancel: bool = False,
    ) -> None:
        self._capability = _ready_motion_capability(
            cancel_supported=cancel_supported,
            stop_supported=stop_supported,
        )
        self.cancel_accepted = cancel_accepted
        self.stop_completed = stop_completed
        self.block_cancel = block_cancel
        self.active_started = Event()
        self.release_active = Event()
        self.cancel_entered = Event()
        self.release_cancel = Event()
        self._counts_lock = Lock()
        self.start_calls: list[tuple[RealtimeStageContext, MotionRequest]] = []
        self.cancel_count = 0
        self.stop_count = 0
        self.close_count = 0

    def preflight(self) -> RealtimeMotionCapability:
        return self._capability

    def capability(self) -> RealtimeMotionCapability:
        return self._capability

    def start(
        self,
        *,
        context: RealtimeStageContext,
        request: MotionRequest,
    ) -> RealtimeStageResultEnvelope[MotionResult]:
        with self._counts_lock:
            self.start_calls.append((context, request))
            if request.intent is MotionIntent.STOP_MOTION:
                self.stop_count += 1

        if request.intent is MotionIntent.STOP_MOTION:
            result = (
                MotionResult.completed(request=request, session_id=context.session_id)
                if self.stop_completed
                else MotionResult.unavailable(
                    request=request,
                    session_id=context.session_id,
                    safe_message="Stop motion failed safely.",
                )
            )
        else:
            self.active_started.set()
            if not self.release_active.wait(timeout=3.0):
                raise RuntimeError("test motion stage was not released")
            result = MotionResult.completed(
                request=request,
                session_id=context.session_id,
            )

        return RealtimeStageResultEnvelope(
            stage_kind=self.stage_kind,
            context=context,
            result=result,
        )

    def cancel(self, *, context: RealtimeStageContext) -> bool:
        del context
        with self._counts_lock:
            self.cancel_count += 1
        self.cancel_entered.set()
        if self.block_cancel and not self.release_cancel.wait(timeout=3.0):
            raise RuntimeError("test cancellation was not released")
        if self.cancel_accepted:
            self.release_active.set()
        return self.cancel_accepted

    def close(self) -> None:
        with self._counts_lock:
            self.close_count += 1
        self.release_active.set()
        self.release_cancel.set()


def _listening_motion(notification):
    if notification.signal is MotionLifecycleSignal.LISTENING:
        return MotionRequest.speaking_state(True)
    return None


def _start_blocked_turn(
    stage: _ControllableMotionStage,
) -> tuple[framework.RealtimeSession, framework.RealtimeTurnStartResult, Thread]:
    session = framework.create_realtime_session(motion_stage=stage)
    session.set_motion_lifecycle_hook(_listening_motion)
    started = session.start_turn(input_text="motion control")
    thread = Thread(
        target=lambda: session.run_turn(
            framework.RealtimeTurn(
                turn_id=started.turn_id,
                session_id=started.session_id,
                input_text="motion control",
            )
        ),
        daemon=True,
    )
    thread.start()
    if not stage.active_started.wait(timeout=3.0):
        raise AssertionError("motion stage did not start")
    return session, started, thread


class MotionControlControlBTests(unittest.TestCase):
    def test_interrupt_cancels_outside_session_lock_and_suppresses_late_success(self) -> None:
        stage = _ControllableMotionStage()
        session, started, turn_thread = _start_blocked_turn(stage)

        result = session.interrupt(
            InterruptRequest.user_barge_in(turn_id=started.turn_id)
        )
        turn_thread.join(timeout=3.0)

        self.assertFalse(turn_thread.is_alive())
        self.assertEqual(stage.cancel_count, 1)
        self.assertIsNotNone(result.motion_result)
        motion = result.motion_result
        assert motion is not None
        self.assertIs(motion.outcome, MotionControlOutcome.COMPLETED)
        self.assertEqual(motion.session_id, started.session_id)
        self.assertEqual(motion.turn_id, started.turn_id)
        self.assertEqual(motion.generation_id, started.generation_id)
        self.assertTrue(motion.cancel_requested)
        self.assertTrue(motion.cancel_accepted)
        self.assertTrue(motion.cancel_completed)
        self.assertTrue(motion.future_delivery_suppressed)
        motion_events = [
            event.type
            for event in session.event_history
            if event.boundary == "motion"
        ]
        self.assertEqual(
            motion_events,
            [
                framework.RealtimeEventType.MOTION_REQUESTED,
                framework.RealtimeEventType.MOTION_STARTED,
            ],
        )

    def test_supported_stop_motion_executes_once_and_is_independent(self) -> None:
        stage = _ControllableMotionStage(stop_supported=True)
        session, started, turn_thread = _start_blocked_turn(stage)

        result = session.interrupt(
            InterruptRequest.user_barge_in(turn_id=started.turn_id)
        )
        turn_thread.join(timeout=3.0)

        motion = result.motion_result
        assert motion is not None
        self.assertEqual(stage.cancel_count, 1)
        self.assertEqual(stage.stop_count, 1)
        self.assertTrue(motion.cancel_completed)
        self.assertTrue(motion.stop_motion_requested)
        self.assertTrue(motion.stop_motion_supported)
        self.assertTrue(motion.stop_motion_applied)

    def test_unsupported_stop_is_truthful_while_cancel_still_completes(self) -> None:
        stage = _ControllableMotionStage(stop_supported=False)
        session, started, turn_thread = _start_blocked_turn(stage)

        result = session.interrupt(
            InterruptRequest.user_barge_in(turn_id=started.turn_id)
        )
        turn_thread.join(timeout=3.0)

        motion = result.motion_result
        assert motion is not None
        self.assertIs(motion.outcome, MotionControlOutcome.COMPLETED)
        self.assertEqual(stage.stop_count, 0)
        self.assertTrue(motion.stop_motion_requested)
        self.assertFalse(motion.stop_motion_supported)
        self.assertFalse(motion.stop_motion_applied)

    def test_unsupported_cancel_and_stop_never_call_stage_control(self) -> None:
        stage = _ControllableMotionStage(
            cancel_supported=False,
            stop_supported=False,
        )
        session, started, turn_thread = _start_blocked_turn(stage)
        holder: list[framework.InterruptResult] = []
        interrupt_thread = Thread(
            target=lambda: holder.append(
                session.interrupt(
                    InterruptRequest.user_barge_in(turn_id=started.turn_id)
                )
            ),
            daemon=True,
        )
        interrupt_thread.start()
        time.sleep(0.02)
        self.assertEqual(stage.cancel_count, 0)
        self.assertEqual(stage.stop_count, 0)
        stage.release_active.set()
        turn_thread.join(timeout=3.0)
        interrupt_thread.join(timeout=3.0)

        self.assertEqual(len(holder), 1)
        motion = holder[0].motion_result
        assert motion is not None
        self.assertIs(motion.outcome, MotionControlOutcome.UNSUPPORTED)
        self.assertFalse(motion.effective)
        self.assertFalse(motion.stop_motion_supported)
        self.assertFalse(motion.stop_motion_applied)

    def test_cancel_rejection_is_failed_without_completion_overclaim(self) -> None:
        stage = _ControllableMotionStage(cancel_accepted=False)
        session, started, turn_thread = _start_blocked_turn(stage)
        holder: list[framework.InterruptResult] = []
        interrupt_thread = Thread(
            target=lambda: holder.append(
                session.interrupt(
                    InterruptRequest(
                        scope=InterruptScope.CURRENT_TURN,
                        turn_id=started.turn_id,
                    )
                )
            ),
            daemon=True,
        )
        interrupt_thread.start()
        self.assertTrue(stage.cancel_entered.wait(timeout=3.0))
        stage.release_active.set()
        turn_thread.join(timeout=3.0)
        interrupt_thread.join(timeout=3.0)

        motion = holder[0].motion_result
        assert motion is not None
        self.assertIs(motion.outcome, MotionControlOutcome.FAILED)
        self.assertTrue(motion.cancel_requested)
        self.assertFalse(motion.cancel_accepted)
        self.assertFalse(motion.cancel_completed)
        self.assertFalse(motion.future_delivery_suppressed)

    def test_duplicate_control_calls_cancel_and_stop_at_most_once(self) -> None:
        stage = _ControllableMotionStage(
            stop_supported=True,
            block_cancel=True,
        )
        session, started, turn_thread = _start_blocked_turn(stage)
        results: list[framework.InterruptResult] = []

        def interrupt() -> None:
            results.append(
                session.interrupt(
                    InterruptRequest.user_barge_in(turn_id=started.turn_id)
                )
            )

        first = Thread(target=interrupt, daemon=True)
        second = Thread(target=interrupt, daemon=True)
        first.start()
        self.assertTrue(stage.cancel_entered.wait(timeout=3.0))
        second.start()
        time.sleep(0.02)
        stage.release_cancel.set()
        first.join(timeout=3.0)
        second.join(timeout=3.0)
        turn_thread.join(timeout=3.0)

        self.assertEqual(len(results), 2)
        self.assertEqual(stage.cancel_count, 1)
        self.assertEqual(stage.stop_count, 1)
        self.assertTrue(
            all(
                result.motion_result is not None
                and result.motion_result.stop_motion_applied
                for result in results
            )
        )

    def test_non_motion_scope_preserves_legacy_none_projection(self) -> None:
        stage = _ControllableMotionStage()
        session, started, turn_thread = _start_blocked_turn(stage)
        holder: list[framework.InterruptResult] = []
        interrupt_thread = Thread(
            target=lambda: holder.append(
                session.interrupt(
                    InterruptRequest(
                        scope=InterruptScope.LLM_STREAM,
                        turn_id=started.turn_id,
                    )
                )
            ),
            daemon=True,
        )
        interrupt_thread.start()
        time.sleep(0.02)
        self.assertEqual(stage.cancel_count, 0)
        stage.release_active.set()
        turn_thread.join(timeout=3.0)
        interrupt_thread.join(timeout=3.0)
        self.assertIsNone(holder[0].motion_result)

    def test_mismatched_target_does_not_cancel_another_turn_motion(self) -> None:
        stage = _ControllableMotionStage()
        session, _, turn_thread = _start_blocked_turn(stage)
        other_turn = framework.TurnId.new()
        holder: list[framework.InterruptResult] = []
        interrupt_thread = Thread(
            target=lambda: holder.append(
                session.interrupt(
                    InterruptRequest(
                        scope=InterruptScope.MOTION,
                        turn_id=other_turn,
                    )
                )
            ),
            daemon=True,
        )
        interrupt_thread.start()
        time.sleep(0.02)
        self.assertEqual(stage.cancel_count, 0)
        stage.release_active.set()
        turn_thread.join(timeout=3.0)
        interrupt_thread.join(timeout=3.0)
        motion = holder[0].motion_result
        assert motion is not None
        self.assertIs(motion.outcome, MotionControlOutcome.NOT_ACTIVE)
        self.assertEqual(motion.turn_id, other_turn)

    def test_no_active_terminal_and_closed_results_are_distinct(self) -> None:
        session = framework.create_realtime_session()
        no_active = session.interrupt(
            InterruptRequest(scope=InterruptScope.MOTION)
        )
        self.assertIsNotNone(no_active.motion_result)
        assert no_active.motion_result is not None
        self.assertIs(
            no_active.motion_result.outcome,
            MotionControlOutcome.NOT_ACTIVE,
        )

        completed = session.run_turn(input_text="terminal")
        terminal = session.interrupt(
            InterruptRequest(
                scope=InterruptScope.MOTION,
                turn_id=completed.turn_id,
            )
        )
        assert terminal.motion_result is not None
        self.assertIs(
            terminal.motion_result.outcome,
            MotionControlOutcome.ALREADY_TERMINAL,
        )

        session.close()
        closed = session.interrupt(InterruptRequest(scope=InterruptScope.MOTION))
        assert closed.motion_result is not None
        self.assertIs(
            closed.motion_result.outcome,
            MotionControlOutcome.ALREADY_CLOSED,
        )
        self.assertIs(closed.outcome, InterruptOutcome.ALREADY_CLOSED)

    def test_close_reaches_active_cancel_and_closes_stage_once(self) -> None:
        stage = _ControllableMotionStage()
        session, _, turn_thread = _start_blocked_turn(stage)
        close_thread = Thread(target=session.close, daemon=True)
        close_thread.start()
        close_thread.join(timeout=3.0)
        turn_thread.join(timeout=3.0)

        self.assertFalse(close_thread.is_alive())
        self.assertFalse(turn_thread.is_alive())
        self.assertEqual(stage.cancel_count, 1)
        self.assertEqual(stage.close_count, 1)
        self.assertFalse(
            any(
                event.type is framework.RealtimeEventType.MOTION_COMPLETED
                for event in session.event_history
            )
        )

    def test_public_surface_versions_and_aggregate_outcome_remain_unchanged(self) -> None:
        expected_factory = (
            "project_root",
            "public_metadata",
            "real_runtime_enabled",
            "voice_input_stage",
            "text_generation_stage",
            "voice_output_stage",
            "motion_stage",
            "config",
        )
        self.assertEqual(
            tuple(inspect.signature(framework.create_realtime_session).parameters),
            expected_factory,
        )
        self.assertFalse(hasattr(framework.RealtimeSession, "cancel_motion"))
        self.assertFalse(hasattr(framework.MotionSession, "cancel_motion"))
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")

        result = framework.create_realtime_session().interrupt(
            InterruptRequest(scope=InterruptScope.MOTION)
        )
        self.assertIs(result.outcome, InterruptOutcome.NO_ACTIVE_TURN)
        self.assertIsNotNone(result.motion_result)


if __name__ == "__main__":
    unittest.main()
