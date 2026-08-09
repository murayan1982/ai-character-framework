"""Provider-free tests for FW-RT6-9b Control B interrupt ordering."""

from __future__ import annotations

import inspect
from threading import Event, Lock, Thread
import time
import unittest

import framework
from framework.output_control import (
    InterruptOutcome,
    InterruptRequest,
    InterruptScope,
    OutputFlushRequest,
)
from framework.realtime_capabilities import (
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


class _OrderedTextStage:
    stage_kind = RealtimeStageKind.TEXT_GENERATION

    def __init__(self) -> None:
        self.started = Event()
        self.stage_release = Event()
        self.cancel_entered = Event()
        self.cancel_release = Event()
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
        if not self.stage_release.wait(timeout=3.0):
            raise RuntimeError("ordered test stage was not released")
        return object()

    def cancel(self, *, context):
        del context
        with self._lock:
            self.cancel_count += 1
        self.cancel_entered.set()
        if not self.cancel_release.wait(timeout=3.0):
            raise RuntimeError("ordered test cancellation was not released")
        self.stage_release.set()
        return True

    def close(self) -> None:
        with self._lock:
            self.close_count += 1
        self.cancel_release.set()
        self.stage_release.set()


class _CompletionRaceSession(framework.RealtimeSession):
    def __init__(self) -> None:
        super().__init__()
        self.interrupt_reserved = Event()
        self.interrupt_release = Event()

    def _claim_interrupt_request(self, request):
        admission = super()._claim_interrupt_request(request)
        if admission[0] == "owner":
            self.interrupt_reserved.set()
        return admission

    def _request_interrupt_coordination(self, request):
        if not self.interrupt_release.wait(timeout=3.0):
            raise RuntimeError("interrupt terminal race was not released")
        return super()._request_interrupt_coordination(request)

    def _coordinated_interrupt_result(
        self,
        *,
        request,
        current_turn_id,
        coordination_result,
    ):
        from framework.output_control import InterruptResult

        return InterruptResult(
            outcome=InterruptOutcome.ACCEPTED,
            scope=request.scope,
            reason=request.reason,
            turn_id=request.turn_id or current_turn_id,
            safe_message="Deterministic race interrupt was accepted.",
            coordination_result=coordination_result,
        )

class _FlushCountingSession(framework.RealtimeSession):
    def __init__(self, *, text_generation_stage) -> None:
        super().__init__(text_generation_stage=text_generation_stage)
        self.flush_count = 0

    def _flush_output_serialized(self, request=None):
        self.flush_count += 1
        return super()._flush_output_serialized(request)


class _NormalReservationSession(framework.RealtimeSession):
    def __init__(self) -> None:
        super().__init__()
        self.execution_started = Event()
        self.execution_release = Event()

    def _run_turn_serialized(self, *args, **kwargs):
        self.execution_started.set()
        if not self.execution_release.wait(timeout=3.0):
            raise RuntimeError("normal reservation test was not released")
        return super()._run_turn_serialized(*args, **kwargs)


def _active_stage(session, stage: _OrderedTextStage):
    started = session.start_turn(input_text="ordered interrupt")
    if not started.accepted or started.generation_id is None:
        raise AssertionError("ordered test turn was not admitted")
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
        raise AssertionError("ordered test stage did not start")
    return started, thread


def _thread_call(callable_):
    holder: list[object] = []
    thread = Thread(target=lambda: holder.append(callable_()), daemon=True)
    thread.start()
    return thread, holder


class InterruptOrderingControlBTests(unittest.TestCase):
    def test_concurrent_and_later_duplicate_replay_exact_owner_result(self) -> None:
        stage = _OrderedTextStage()
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, stage_thread = _active_stage(session, stage)
        request = InterruptRequest(
            scope=InterruptScope.LLM_STREAM,
            turn_id=started.turn_id,
            timeout_seconds=0.5,
        )
        owner_thread, owner = _thread_call(lambda: session.interrupt(request))
        self.assertTrue(stage.cancel_entered.wait(timeout=3.0))
        duplicate_thread, duplicate = _thread_call(
            lambda: session.interrupt(
                InterruptRequest(
                    scope=InterruptScope.ALL,
                    turn_id=started.turn_id,
                )
            )
        )
        time.sleep(0.02)
        self.assertTrue(duplicate_thread.is_alive())
        stage.cancel_release.set()
        for thread in (owner_thread, duplicate_thread, stage_thread):
            thread.join(timeout=3.0)

        self.assertIs(owner[0], duplicate[0])
        self.assertEqual(stage.cancel_count, 1)
        later = session.interrupt(request)
        self.assertIs(later, owner[0])
        event_types = [event.type for event in session.event_history]
        self.assertEqual(event_types.count(framework.RealtimeEventType.INTERRUPT_REQUESTED), 1)
        self.assertEqual(event_types.count(framework.RealtimeEventType.TURN_INTERRUPTED), 1)

    def test_interrupt_reservation_suppresses_later_normal_terminal(self) -> None:
        session = _CompletionRaceSession()
        started = session.start_turn(input_text="completion race")
        interrupt_thread, interrupt_result = _thread_call(
            lambda: session.interrupt(
                InterruptRequest(turn_id=started.turn_id)
            )
        )
        self.assertTrue(session.interrupt_reserved.wait(timeout=3.0))
        run_thread, run_result = _thread_call(
            lambda: session.run_turn(
                framework.RealtimeTurn(
                    turn_id=started.turn_id,
                    session_id=started.session_id,
                    input_text="completion race",
                )
            )
        )
        time.sleep(0.02)
        self.assertTrue(run_thread.is_alive())
        session.interrupt_release.set()
        run_thread.join(timeout=3.0)
        interrupt_thread.join(timeout=3.0)

        self.assertIs(interrupt_result[0].outcome, InterruptOutcome.ACCEPTED)
        self.assertEqual(run_result[0].outcome.value, "interrupted")
        terminal_types = [
            event.type
            for event in session.event_history
            if event.type in {
                framework.RealtimeEventType.TURN_COMPLETED,
                framework.RealtimeEventType.TURN_INTERRUPTED,
            }
        ]
        self.assertEqual(terminal_types, [framework.RealtimeEventType.TURN_INTERRUPTED])

    def test_preexisting_normal_terminal_wins_without_interrupt_effects(self) -> None:
        session = framework.create_realtime_session()
        terminal = session.run_turn(input_text="normal wins")
        before = len(session.event_history)
        result = session.interrupt(
            InterruptRequest(turn_id=terminal.turn_id)
        )

        self.assertIs(result.outcome, InterruptOutcome.NO_ACTIVE_TURN)
        self.assertEqual(len(session.event_history), before)
        self.assertEqual(len(session.terminal_results), 1)
        self.assertEqual(session.terminal_results[0].outcome.value, "completed")

        racing = _NormalReservationSession()
        run_thread, normal = _thread_call(
            lambda: racing.run_turn(input_text="normal reservation")
        )
        self.assertTrue(racing.execution_started.wait(timeout=3.0))
        turn_id = racing._active_turn_id
        interrupt_thread, interrupt = _thread_call(
            lambda: racing.interrupt(InterruptRequest(turn_id=turn_id))
        )
        racing.execution_release.set()
        run_thread.join(timeout=3.0)
        interrupt_thread.join(timeout=3.0)
        self.assertEqual(normal[0].outcome.value, "completed")
        self.assertIs(interrupt[0].outcome, InterruptOutcome.NO_ACTIVE_TURN)
        self.assertEqual(
            [result.outcome.value for result in racing.terminal_results],
            ["completed"],
        )

    def test_interrupt_admitted_before_close_finishes_first(self) -> None:
        stage = _OrderedTextStage()
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, stage_thread = _active_stage(session, stage)
        owner_thread, owner = _thread_call(
            lambda: session.interrupt(
                InterruptRequest(
                    scope=InterruptScope.LLM_STREAM,
                    turn_id=started.turn_id,
                )
            )
        )
        self.assertTrue(stage.cancel_entered.wait(timeout=3.0))
        close_thread = Thread(target=session.close, daemon=True)
        close_thread.start()
        time.sleep(0.02)
        self.assertTrue(close_thread.is_alive())
        self.assertFalse(session.is_closed)
        stage.cancel_release.set()
        for thread in (owner_thread, close_thread, stage_thread):
            thread.join(timeout=3.0)

        self.assertIs(owner[0].outcome, InterruptOutcome.ACCEPTED)
        self.assertTrue(session.is_closed)
        event_types = [event.type for event in session.event_history]
        self.assertLess(
            event_types.index(framework.RealtimeEventType.TURN_INTERRUPTED),
            event_types.index(framework.RealtimeEventType.SESSION_CLOSED),
        )

    def test_close_admitted_first_returns_existing_closed_result(self) -> None:
        session = framework.create_realtime_session()
        session.close()
        result = session.interrupt(InterruptRequest())
        self.assertIs(result.outcome, InterruptOutcome.ALREADY_CLOSED)
        self.assertIsNotNone(result.coordination_result)

    def test_owner_flush_precedes_terminal_and_standalone_reuses_it(self) -> None:
        stage = _OrderedTextStage()
        session = _FlushCountingSession(text_generation_stage=stage)
        started, stage_thread = _active_stage(session, stage)
        owner_thread, _ = _thread_call(
            lambda: session.interrupt(
                InterruptRequest(
                    scope=InterruptScope.LLM_STREAM,
                    turn_id=started.turn_id,
                    flush_output=True,
                )
            )
        )
        self.assertTrue(stage.cancel_entered.wait(timeout=3.0))
        flush_thread, flush_result = _thread_call(
            lambda: session.flush_output(
                OutputFlushRequest(turn_id=started.turn_id)
            )
        )
        time.sleep(0.02)
        self.assertTrue(flush_thread.is_alive())
        stage.cancel_release.set()
        for thread in (owner_thread, flush_thread, stage_thread):
            thread.join(timeout=3.0)

        self.assertEqual(session.flush_count, 1)
        self.assertEqual(flush_result[0].outcome.value, "nothing_to_flush")
        event_types = [event.type for event in session.event_history]
        self.assertLess(
            event_types.index(framework.RealtimeEventType.OUTPUT_FLUSH_COMPLETED),
            event_types.index(framework.RealtimeEventType.TURN_INTERRUPTED),
        )

    def test_new_turn_during_interrupt_is_immediate_typed_reject(self) -> None:
        stage = _OrderedTextStage()
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, stage_thread = _active_stage(session, stage)
        owner_thread, _ = _thread_call(
            lambda: session.interrupt(
                InterruptRequest(
                    scope=InterruptScope.LLM_STREAM,
                    turn_id=started.turn_id,
                )
            )
        )
        self.assertTrue(stage.cancel_entered.wait(timeout=3.0))
        before = time.monotonic()
        rejected = session.start_turn(input_text="must reject")
        elapsed = time.monotonic() - before

        self.assertLess(elapsed, 0.25)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.public_metadata["reason"], "interrupt_in_progress")
        self.assertEqual(
            rejected.terminal_result.public_metadata["reason"],
            "interrupt_in_progress",
        )
        self.assertEqual(session._active_turn_id, started.turn_id)
        stage.cancel_release.set()
        owner_thread.join(timeout=3.0)
        stage_thread.join(timeout=3.0)

    def test_cancel_and_interrupt_share_one_resolved_turn_owner(self) -> None:
        stage = _OrderedTextStage()
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, stage_thread = _active_stage(session, stage)
        owner_thread, owner = _thread_call(
            lambda: session.interrupt(
                InterruptRequest(
                    scope=InterruptScope.LLM_STREAM,
                    turn_id=started.turn_id,
                )
            )
        )
        self.assertTrue(stage.cancel_entered.wait(timeout=3.0))
        cancel_thread, cancel = _thread_call(session.cancel_current_turn)
        stage.cancel_release.set()
        for thread in (owner_thread, cancel_thread, stage_thread):
            thread.join(timeout=3.0)
        self.assertIs(cancel[0], owner[0])
        self.assertEqual(stage.cancel_count, 1)

    def test_public_factory_versions_and_root_surface_remain_unchanged(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(framework.create_realtime_session).parameters),
            (
                "project_root",
                "public_metadata",
                "real_runtime_enabled",
                "voice_input_stage",
                "text_generation_stage",
                "voice_output_stage",
                "motion_stage",
                "config",
            ),
        )
        self.assertEqual(len(framework.__all__), 127)
        self.assertFalse(hasattr(framework, "InterruptOrderingDecision"))
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")


if __name__ == "__main__":
    unittest.main()
