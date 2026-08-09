"""Provider-free tests for FW-RT6-9a Control B runtime coordination."""

from __future__ import annotations

import inspect
from threading import Event, Lock, Thread
import time
import unittest

import framework
from framework.interrupt_coordination import (
    InterruptAggregateOutcome,
    InterruptSubsystem,
    InterruptSubsystemOutcome,
)
from framework.output_control import InterruptOutcome, InterruptRequest, InterruptScope
from framework.realtime_capabilities import (
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind
from framework.realtime_voice_output import (
    SynthesisWorkId,
    VoiceSynthesisCancelOutcome,
    VoiceSynthesisCancelResult,
)
from framework.realtime_voice_output_queue import (
    VoiceSynthesisPendingClearOutcome,
    VoiceSynthesisPendingClearResult,
    VoiceSynthesisPendingWork,
)


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


class _BlockingStage:
    def __init__(
        self,
        stage_kind: RealtimeStageKind,
        *,
        cancel_supported: bool = True,
        hard_supported: bool = False,
        cancel_accepted: bool = True,
        release_on_cancel: bool = True,
        queue_supported: bool = False,
        artifact_supported: bool = False,
        pending_count: int = 0,
        artifact_count: int = 0,
        malformed_queue: bool = False,
        typed_voice_cancel: bool = False,
    ) -> None:
        self.stage_kind = stage_kind
        self.cancel_accepted = cancel_accepted
        self.release_on_cancel = release_on_cancel
        self.pending_count = pending_count
        self.artifact_count = artifact_count
        self.malformed_queue = malformed_queue
        self.typed_voice_cancel = typed_voice_cancel
        self.started = Event()
        self.release = Event()
        self._lock = Lock()
        self.start_count = 0
        self.cancel_count = 0
        self.clear_count = 0
        self.invalidate_count = 0
        self.close_count = 0
        if stage_kind is RealtimeStageKind.TEXT_GENERATION:
            self._capability = TextGenerationCapability(
                runtime=_runtime(),
                streaming_supported=True,
                cooperative_cancel_supported=cancel_supported,
                provider_hard_cancel_supported=hard_supported,
            )
        elif stage_kind is RealtimeStageKind.VOICE_OUTPUT:
            self._capability = RealtimeVoiceOutputCapability(
                runtime=_runtime(),
                streaming_audio_supported=True,
                generation_cancel_supported=cancel_supported,
                provider_hard_cancel_supported=hard_supported,
                pending_flush_supported=queue_supported,
                active_audio_invalidation_supported=artifact_supported,
            )
        else:
            raise ValueError("test stage kind must be text or voice output")

    def preflight(self):
        return self._capability

    def capability(self):
        return self._capability

    def start(self, *, context, request):
        del context, request
        with self._lock:
            self.start_count += 1
        self.started.set()
        if not self.release.wait(timeout=3.0):
            raise RuntimeError("test stage was not released")
        return object()

    def cancel(self, *, context):
        with self._lock:
            self.cancel_count += 1
        if self.release_on_cancel:
            self.release.set()
        if self.typed_voice_cancel:
            return VoiceSynthesisCancelResult(
                outcome=VoiceSynthesisCancelOutcome.COMPLETED,
                context=context,
                work_id=SynthesisWorkId.new(),
                cooperative_cancel_requested=True,
                cooperative_cancel_completed=True,
                provider_hard_cancel_applied=True,
                future_delivery_suppressed=True,
                safe_message="Typed voice cancellation completed.",
            )
        return self.cancel_accepted

    def clear_pending(self, *, context):
        with self._lock:
            self.clear_count += 1
        if self.malformed_queue:
            return object()
        cleared = tuple(
            VoiceSynthesisPendingWork(
                context=context,
                work_id=SynthesisWorkId.new(),
            )
            for _ in range(self.pending_count)
        )
        count = self.pending_count
        self.pending_count = 0
        return VoiceSynthesisPendingClearResult(
            outcome=(
                VoiceSynthesisPendingClearOutcome.CLEARED
                if count
                else VoiceSynthesisPendingClearOutcome.NOTHING_CLEARED
            ),
            cleared_work=cleared,
            pending_count=0,
            max_pending_depth=max(1, count),
            safe_message="Pending synthesis work was inspected.",
        )

    def invalidate_completed(self, context):
        del context
        with self._lock:
            self.invalidate_count += 1
        count = self.artifact_count
        self.artifact_count = 0
        return count

    def close(self) -> None:
        with self._lock:
            self.close_count += 1
        self.release.set()


def _active_context(session, *, text: str = "interrupt"):
    started = session.start_turn(input_text=text)
    if not started.accepted or started.generation_id is None:
        raise AssertionError("test turn was not admitted")
    return started, RealtimeStageContext(
        session_id=started.session_id,
        turn_id=started.turn_id,
        generation_id=started.generation_id,
    )


def _start_stage(session, stage_kind: str, context, started_event: Event):
    holder: list[object | None] = []
    thread = Thread(
        target=lambda: holder.append(
            session._execute_interruptible_stage(
                stage_kind=stage_kind,
                context=context,
                request=object(),
            )
        ),
        daemon=True,
    )
    thread.start()
    if not started_event.wait(timeout=3.0):
        raise AssertionError("interruptible stage did not start")
    return thread, holder


def _result_for(result, subsystem: InterruptSubsystem):
    aggregate = result.coordination_result
    if aggregate is None:
        raise AssertionError("coordination result is missing")
    return next(item for item in aggregate.subsystem_results if item.subsystem is subsystem)


class InterruptCoordinatorControlBTests(unittest.TestCase):
    def test_scope_and_flag_dispatch_is_exact_and_stably_ordered(self) -> None:
        method = framework.RealtimeSession._interrupt_target_names
        self.assertEqual(method(InterruptRequest(scope=InterruptScope.LLM_STREAM)), ("text_generation",))
        self.assertEqual(method(InterruptRequest(scope=InterruptScope.TTS_QUEUE)), ("tts_queue",))
        self.assertEqual(
            method(InterruptRequest(scope=InterruptScope.VOICE_OUTPUT)),
            ("tts_generation", "tts_queue", "audio_artifact"),
        )
        self.assertEqual(method(InterruptRequest(scope=InterruptScope.MOTION)), ("motion",))
        self.assertEqual(
            method(InterruptRequest(scope=InterruptScope.ALL)),
            ("text_generation", "tts_generation", "tts_queue", "audio_artifact", "motion"),
        )
        self.assertEqual(
            method(InterruptRequest(scope=InterruptScope.TTS_QUEUE, cancel_llm_stream=True)),
            ("text_generation", "tts_queue"),
        )

    def test_text_cancel_completes_and_suppresses_late_delivery(self) -> None:
        stage = _BlockingStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, context = _active_context(session)
        thread, holder = _start_stage(session, "text_generation", context, stage.started)

        result = session.interrupt(
            InterruptRequest(
                scope=InterruptScope.LLM_STREAM,
                turn_id=started.turn_id,
                timeout_seconds=0.5,
            )
        )
        thread.join(timeout=3.0)

        self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
        self.assertEqual(stage.cancel_count, 1)
        self.assertEqual(holder, [None])
        text = _result_for(result, InterruptSubsystem.TEXT_GENERATION)
        self.assertIs(text.outcome, InterruptSubsystemOutcome.COMPLETED)
        self.assertTrue(text.cooperative_cancel_completed)
        self.assertTrue(text.future_delivery_suppressed)
        self.assertEqual(session.terminal_results[-1].outcome.value, "interrupted")
        self.assertEqual(
            [event.type for event in session.event_history[-4:]],
            [
                framework.RealtimeEventType.INTERRUPT_REQUESTED,
                framework.RealtimeEventType.INTERRUPT_ACCEPTED,
                framework.RealtimeEventType.INTERRUPT_COMPLETED,
                framework.RealtimeEventType.TURN_INTERRUPTED,
            ],
        )

    def test_voice_generation_queue_and_artifact_are_distinct_completed_results(self) -> None:
        stage = _BlockingStage(
            RealtimeStageKind.VOICE_OUTPUT,
            queue_supported=True,
            artifact_supported=True,
            pending_count=2,
            artifact_count=1,
        )
        session = framework.create_realtime_session(voice_output_stage=stage)
        started, context = _active_context(session)
        thread, holder = _start_stage(session, "voice_output", context, stage.started)

        result = session.interrupt(
            InterruptRequest(
                scope=InterruptScope.VOICE_OUTPUT,
                turn_id=started.turn_id,
                timeout_seconds=0.5,
            )
        )
        thread.join(timeout=3.0)

        self.assertEqual(holder, [None])
        self.assertIs(result.coordination_result.outcome, InterruptAggregateOutcome.COMPLETED)
        generation = _result_for(result, InterruptSubsystem.TTS_GENERATION)
        queue = _result_for(result, InterruptSubsystem.TTS_QUEUE)
        artifact = _result_for(result, InterruptSubsystem.AUDIO_ARTIFACT)
        self.assertTrue(generation.cooperative_cancel_completed)
        self.assertEqual(queue.affected_count, 2)
        self.assertEqual(artifact.affected_count, 1)
        self.assertEqual((stage.cancel_count, stage.clear_count, stage.invalidate_count), (1, 1, 1))

    def test_all_scope_derives_partial_without_hiding_success(self) -> None:
        text_stage = _BlockingStage(RealtimeStageKind.TEXT_GENERATION)
        voice_stage = _BlockingStage(
            RealtimeStageKind.VOICE_OUTPUT,
            queue_supported=True,
            artifact_supported=True,
            pending_count=1,
            artifact_count=1,
        )
        session = framework.create_realtime_session(
            text_generation_stage=text_stage,
            voice_output_stage=voice_stage,
        )
        started, context = _active_context(session)
        text_thread, _ = _start_stage(session, "text_generation", context, text_stage.started)
        voice_thread, _ = _start_stage(session, "voice_output", context, voice_stage.started)

        result = session.interrupt(
            InterruptRequest.user_barge_in(
                turn_id=started.turn_id,
                timeout_seconds=0.5,
            )
        )
        text_thread.join(timeout=3.0)
        voice_thread.join(timeout=3.0)

        self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
        self.assertIs(result.coordination_result.outcome, InterruptAggregateOutcome.PARTIAL)
        self.assertEqual(len(result.coordination_result.subsystem_results), 5)
        self.assertIs(
            _result_for(result, InterruptSubsystem.MOTION).outcome,
            InterruptSubsystemOutcome.NOT_ACTIVE,
        )

    def test_bounded_wait_reports_timeout_and_keeps_delivery_barrier(self) -> None:
        stage = _BlockingStage(
            RealtimeStageKind.TEXT_GENERATION,
            release_on_cancel=False,
        )
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, context = _active_context(session)
        thread, holder = _start_stage(session, "text_generation", context, stage.started)

        before = time.monotonic()
        result = session.interrupt(
            InterruptRequest(
                scope=InterruptScope.LLM_STREAM,
                turn_id=started.turn_id,
                timeout_seconds=0.03,
            )
        )
        elapsed = time.monotonic() - before
        stage.release.set()
        thread.join(timeout=3.0)

        text = _result_for(result, InterruptSubsystem.TEXT_GENERATION)
        self.assertLess(elapsed, 0.5)
        self.assertIs(result.outcome, InterruptOutcome.FAILED)
        self.assertIs(text.outcome, InterruptSubsystemOutcome.TIMED_OUT)
        self.assertTrue(text.cooperative_cancel_accepted)
        self.assertFalse(text.cooperative_cancel_completed)
        self.assertTrue(text.future_delivery_suppressed)
        self.assertEqual(holder, [None])

    def test_cancel_rejection_is_failed_without_effect_overclaim(self) -> None:
        stage = _BlockingStage(
            RealtimeStageKind.TEXT_GENERATION,
            cancel_accepted=False,
            release_on_cancel=False,
        )
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, context = _active_context(session)
        thread, _ = _start_stage(session, "text_generation", context, stage.started)
        result = session.interrupt(
            InterruptRequest(scope=InterruptScope.LLM_STREAM, turn_id=started.turn_id)
        )
        stage.release.set()
        thread.join(timeout=3.0)

        text = _result_for(result, InterruptSubsystem.TEXT_GENERATION)
        self.assertIs(text.outcome, InterruptSubsystemOutcome.FAILED)
        self.assertTrue(text.cooperative_cancel_requested)
        self.assertFalse(text.cooperative_cancel_accepted)
        self.assertFalse(text.future_delivery_suppressed)

    def test_capability_false_never_calls_stage_cancel(self) -> None:
        stage = _BlockingStage(
            RealtimeStageKind.TEXT_GENERATION,
            cancel_supported=False,
        )
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, context = _active_context(session)
        thread, _ = _start_stage(session, "text_generation", context, stage.started)
        result = session.interrupt(
            InterruptRequest(scope=InterruptScope.LLM_STREAM, turn_id=started.turn_id)
        )
        stage.release.set()
        thread.join(timeout=3.0)

        self.assertEqual(stage.cancel_count, 0)
        text = _result_for(result, InterruptSubsystem.TEXT_GENERATION)
        self.assertIs(text.outcome, InterruptSubsystemOutcome.UNSUPPORTED)
        self.assertFalse(text.effective)

    def test_configured_idle_stage_reports_not_active(self) -> None:
        stage = _BlockingStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(text_generation_stage=stage)
        started, _ = _active_context(session)
        result = session.interrupt(
            InterruptRequest(scope=InterruptScope.LLM_STREAM, turn_id=started.turn_id)
        )

        self.assertEqual(stage.cancel_count, 0)
        self.assertIs(
            _result_for(result, InterruptSubsystem.TEXT_GENERATION).outcome,
            InterruptSubsystemOutcome.NOT_ACTIVE,
        )

    def test_mismatched_turn_never_reaches_another_turn_stage(self) -> None:
        stage = _BlockingStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(text_generation_stage=stage)
        _, context = _active_context(session)
        thread, _ = _start_stage(session, "text_generation", context, stage.started)
        result = session.interrupt(
            InterruptRequest(
                scope=InterruptScope.LLM_STREAM,
                turn_id=framework.TurnId.new(),
            )
        )
        stage.release.set()
        thread.join(timeout=3.0)

        self.assertEqual(stage.cancel_count, 0)
        self.assertIs(
            _result_for(result, InterruptSubsystem.TEXT_GENERATION).outcome,
            InterruptSubsystemOutcome.NOT_ACTIVE,
        )

    def test_terminal_and_closed_targets_are_distinct(self) -> None:
        session = framework.create_realtime_session()
        terminal = session.run_turn(input_text="terminal")
        terminal_result = session.interrupt(
            InterruptRequest(scope=InterruptScope.LLM_STREAM, turn_id=terminal.turn_id)
        )
        self.assertIs(
            _result_for(terminal_result, InterruptSubsystem.TEXT_GENERATION).outcome,
            InterruptSubsystemOutcome.ALREADY_TERMINAL,
        )

        session.close()
        closed = session.interrupt(InterruptRequest(scope=InterruptScope.LLM_STREAM))
        self.assertIs(closed.outcome, InterruptOutcome.ALREADY_CLOSED)
        self.assertIs(
            _result_for(closed, InterruptSubsystem.TEXT_GENERATION).outcome,
            InterruptSubsystemOutcome.ALREADY_CLOSED,
        )

    def test_malformed_queue_result_fails_without_flush_overclaim(self) -> None:
        stage = _BlockingStage(
            RealtimeStageKind.VOICE_OUTPUT,
            cancel_supported=False,
            queue_supported=True,
            malformed_queue=True,
        )
        session = framework.create_realtime_session(voice_output_stage=stage)
        started, _ = _active_context(session)
        result = session.interrupt(
            InterruptRequest(scope=InterruptScope.TTS_QUEUE, turn_id=started.turn_id)
        )

        queue = _result_for(result, InterruptSubsystem.TTS_QUEUE)
        self.assertIs(queue.outcome, InterruptSubsystemOutcome.FAILED)
        self.assertEqual(queue.affected_count, 0)
        self.assertFalse(queue.future_delivery_suppressed)

    def test_typed_voice_cancel_preserves_hard_cancel_facts(self) -> None:
        stage = _BlockingStage(
            RealtimeStageKind.VOICE_OUTPUT,
            hard_supported=True,
            typed_voice_cancel=True,
        )
        session = framework.create_realtime_session(voice_output_stage=stage)
        started, context = _active_context(session)
        thread, holder = _start_stage(session, "voice_output", context, stage.started)
        result = session.interrupt(
            InterruptRequest(
                scope=InterruptScope.VOICE_OUTPUT,
                turn_id=started.turn_id,
                timeout_seconds=0.5,
            )
        )
        thread.join(timeout=3.0)

        generation = _result_for(result, InterruptSubsystem.TTS_GENERATION)
        self.assertTrue(generation.provider_hard_cancel_supported)
        self.assertTrue(generation.provider_hard_cancel_applied)
        self.assertTrue(generation.cooperative_cancel_completed)
        self.assertEqual(holder, [None])

    def test_one_active_owner_per_stage_prevents_replacement(self) -> None:
        stage = _BlockingStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(text_generation_stage=stage)
        _, context = _active_context(session)
        first_thread, _ = _start_stage(session, "text_generation", context, stage.started)
        second = session._execute_interruptible_stage(
            stage_kind="text_generation",
            context=context,
            request=object(),
        )
        self.assertIsNone(second)
        self.assertEqual(stage.start_count, 1)
        stage.release.set()
        first_thread.join(timeout=3.0)

    def test_default_timeout_is_bounded_without_changing_request_projection(self) -> None:
        session = framework.create_realtime_session()
        result = session.interrupt(InterruptRequest(scope=InterruptScope.LLM_STREAM))
        self.assertIsNone(result.coordination_result.timeout_seconds)
        self.assertTrue(result.coordination_result.public_metadata["default_timeout_applied"])

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
        self.assertFalse(hasattr(framework, "InterruptAggregateResult"))
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")


if __name__ == "__main__":
    unittest.main()
