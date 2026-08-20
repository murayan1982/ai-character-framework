"""Provider-free integrated acceptance tests for FW-RT6-13a.

The suite composes accepted Framework session, generation, terminal, interrupt,
reset, close, and deterministic fake-runtime boundaries.  Every adapter in this
file is an in-process test double; no provider SDK, network, microphone, audio
playback, or real motion runtime is used.
"""

from __future__ import annotations

from threading import Event, Lock, Thread
import unittest

import framework
from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
from framework.lifecycle import RecoveryAction, TurnOutcome
from framework.motion import MotionOutcome, MotionRequest
from framework.output_control import (
    InterruptOutcome,
    InterruptReason,
    InterruptRequest,
    InterruptScope,
)
from framework.realtime import RealtimeEventType
from framework.realtime_capabilities import (
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from framework.realtime_fake_runtime import (
    DeterministicFakeRuntimeController,
    DeterministicRealtimeRaceHarness,
    FakeRuntimeQueueOverflow,
)
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    RealtimeStageCompletionEnvelope,
    StaleCompletionReason,
)
from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind
from framework.realtime_terminal_registry import TerminalCommitStatus
from framework.recovery_control import (
    RecoveryResetOutcome,
    build_recovery_control_plan,
)


def _execution_ready_test_runtime() -> RuntimeCapabilityState:
    """Advertise the accepted executable-stage seam without provider work."""

    return RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=False,
        fake_runtime=False,
        real_runtime=True,
        unavailable_reason=None,
        public_metadata={"provider_execution_performed": False},
    )


class _BlockingTestStage:
    """In-process stage double used only to expose an interruptible window."""

    def __init__(self, stage_kind: RealtimeStageKind) -> None:
        self.stage_kind = stage_kind
        self.started = Event()
        self.release = Event()
        self._lock = Lock()
        self.cancel_count = 0
        self.close_count = 0
        runtime = _execution_ready_test_runtime()
        if stage_kind is RealtimeStageKind.TEXT_GENERATION:
            self._capability = TextGenerationCapability(
                runtime=runtime,
                streaming_supported=True,
                cooperative_cancel_supported=True,
                provider_hard_cancel_supported=False,
            )
        elif stage_kind is RealtimeStageKind.VOICE_OUTPUT:
            self._capability = RealtimeVoiceOutputCapability(
                runtime=runtime,
                streaming_audio_supported=True,
                generation_cancel_supported=True,
                provider_hard_cancel_supported=False,
                pending_flush_supported=False,
                active_audio_invalidation_supported=False,
            )
        else:
            raise ValueError("integrated interrupt stage must be text or voice output")

    def preflight(self):
        return self._capability

    def capability(self):
        return self._capability

    def start(self, *, context, request):
        del context, request
        self.started.set()
        if not self.release.wait(timeout=2.0):
            raise TimeoutError("integrated fake stage was not released")
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


class _HostAudioAdapter:
    def transcribe(self, *, audio_source, request):
        del audio_source
        return framework.VoiceInputResult.completed(
            "integrated host transcript",
            language=request.language,
            public_metadata={"fake_adapter": True},
        )


class _FakeSynthesisAdapter:
    def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
        if not isinstance(request, VoiceOutputRequest):
            raise TypeError("request must be a VoiceOutputRequest")
        return VoiceOutputResult(
            request_state="generated",
            audio_ready=True,
            audio_format="wav",
            audio_url="memory://fw-rt6-13a/fake.wav",
            public_metadata={"fake_adapter": "true"},
        )


def _start_interruptible_stage(session, stage: _BlockingTestStage):
    started = session.start_turn(input_text="integrated fake interrupt")
    if not started.accepted or started.generation_id is None:
        raise AssertionError("integrated fake turn was not admitted")
    context = RealtimeStageContext(
        session_id=started.session_id,
        turn_id=started.turn_id,
        generation_id=started.generation_id,
    )
    results: list[object | None] = []
    errors: list[BaseException] = []

    def execute() -> None:
        try:
            results.append(
                session._execute_interruptible_stage(
                    stage_kind=stage.stage_kind.value,
                    context=context,
                    request=object(),
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted by caller
            errors.append(exc)

    thread = Thread(target=execute, daemon=True)
    thread.start()
    if not stage.started.wait(timeout=2.0):
        raise AssertionError("integrated fake stage did not start")
    return started, thread, results, errors


class IntegratedFakeRuntimeAcceptanceTests(unittest.TestCase):
    def test_text_only_normal_turn_has_exact_trace_and_one_terminal(self) -> None:
        session = framework.create_realtime_session()
        try:
            result = session.run_turn(input_text="text-only")

            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(session.terminal_results, (result,))
            self.assertEqual(
                tuple(event.type for event in session.event_history),
                (
                    RealtimeEventType.TURN_STARTED,
                    RealtimeEventType.LISTENING_STARTED,
                    RealtimeEventType.LISTENING_COMPLETED,
                    RealtimeEventType.TRANSCRIPT_FINAL,
                    RealtimeEventType.RESPONSE_STARTED,
                    RealtimeEventType.RESPONSE_COMPLETED,
                    RealtimeEventType.SYNTHESIS_STARTED,
                    RealtimeEventType.SYNTHESIS_COMPLETED,
                    RealtimeEventType.TURN_COMPLETED,
                ),
            )
        finally:
            session.close()

    def test_host_audio_transcript_text_tts_motion_chain_is_fake_only(self) -> None:
        voice_input = framework.create_voice_input_session()
        realtime = framework.create_realtime_session()
        motion = framework.create_motion_session()
        try:
            source = framework.VoiceInputAudioSource.from_opaque_id(
                "fw-rt6-13a-host-audio",
                audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=120),
                language="ja-JP",
            )
            transcript = voice_input.transcribe_audio_result(
                source,
                adapter=_HostAudioAdapter(),
            )
            text_result = realtime.run_turn(input_text=transcript.text)
            tts_result = _FakeSynthesisAdapter().synthesize(
                VoiceOutputRequest(text="integrated fake response")
            )
            motion_result = motion.apply_motion(
                MotionRequest.expression_change(
                    "smile",
                    turn_id=text_result.turn_id,
                    generation_id=text_result.generation_id,
                )
            )

            self.assertTrue(transcript.is_completed)
            self.assertIs(text_result.outcome, TurnOutcome.COMPLETED)
            self.assertTrue(tts_result.is_generated)
            self.assertIs(motion_result.outcome, MotionOutcome.COMPLETED)
            self.assertEqual(
                (
                    transcript.text,
                    text_result.input_text,
                    tts_result.audio_handoff_kind,
                    motion_result.public_metadata["mock_motion"],
                ),
                (
                    "integrated host transcript",
                    "integrated host transcript",
                    "audio_url",
                    True,
                ),
            )
        finally:
            voice_input.close()
            realtime.close()
            motion.close()

    def test_user_stop_during_response_stream_terminalizes_once(self) -> None:
        stage = _BlockingTestStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(text_generation_stage=stage)
        try:
            started, thread, results, errors = _start_interruptible_stage(
                session,
                stage,
            )
            request = InterruptRequest(
                scope=InterruptScope.LLM_STREAM,
                reason=InterruptReason.USER_CANCEL,
                turn_id=started.turn_id,
                timeout_seconds=0.5,
            )

            result = session.interrupt(request)
            thread.join(timeout=2.0)

            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(results, [None])
            self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
            self.assertEqual(stage.cancel_count, 1)
            self.assertEqual(len(session.terminal_results), 1)
            self.assertIs(session.terminal_results[0].outcome, TurnOutcome.INTERRUPTED)
        finally:
            session.close()

    def test_user_speech_interrupt_during_voice_output_terminalizes_once(self) -> None:
        stage = _BlockingTestStage(RealtimeStageKind.VOICE_OUTPUT)
        session = framework.create_realtime_session(voice_output_stage=stage)
        try:
            started, thread, results, errors = _start_interruptible_stage(
                session,
                stage,
            )
            result = session.interrupt(
                InterruptRequest(
                    scope=InterruptScope.VOICE_OUTPUT,
                    reason=InterruptReason.USER_BARGE_IN,
                    turn_id=started.turn_id,
                    timeout_seconds=0.5,
                )
            )
            thread.join(timeout=2.0)

            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(results, [None])
            self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
            self.assertEqual(stage.cancel_count, 1)
            self.assertEqual(len(session.terminal_results), 1)
            self.assertIs(session.terminal_results[0].outcome, TurnOutcome.INTERRUPTED)
        finally:
            session.close()

    def test_duplicate_interrupt_replays_exact_owner_result(self) -> None:
        stage = _BlockingTestStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(text_generation_stage=stage)
        try:
            started, thread, _results, errors = _start_interruptible_stage(
                session,
                stage,
            )
            request = InterruptRequest(
                scope=InterruptScope.LLM_STREAM,
                turn_id=started.turn_id,
                timeout_seconds=0.5,
            )

            first = session.interrupt(request)
            thread.join(timeout=2.0)
            duplicate = session.interrupt(request)

            self.assertEqual(errors, [])
            self.assertIs(duplicate, first)
            self.assertEqual(stage.cancel_count, 1)
            self.assertEqual(len(session.terminal_results), 1)
            event_types = tuple(event.type for event in session.event_history)
            self.assertEqual(event_types.count(RealtimeEventType.INTERRUPT_REQUESTED), 1)
            self.assertEqual(event_types.count(RealtimeEventType.TURN_INTERRUPTED), 1)
        finally:
            session.close()

    def test_late_response_tts_and_motion_completions_are_stale(self) -> None:
        scenarios = (
            (RealtimeStageKind.TEXT_GENERATION, "late-response-delta"),
            (RealtimeStageKind.VOICE_OUTPUT, "late-tts-artifact"),
            (RealtimeStageKind.MOTION, "late-motion-completion"),
        )
        for stage_kind, correlation_key in scenarios:
            with self.subTest(stage=stage_kind.value):
                harness: DeterministicRealtimeRaceHarness[str, str] = (
                    DeterministicRealtimeRaceHarness()
                )
                generation_id = harness.start_generation("turn-stale")
                harness.inject_late_generation_completion(
                    stage_kind,
                    turn_id="turn-stale",
                    generation_id=generation_id,
                    value=correlation_key,
                    correlation_key=correlation_key,
                    delay_ticks=2,
                )
                harness.advance_generation(GenerationAdvanceReason.INTERRUPT)

                harness.run_until_idle()

                self.assertEqual(len(harness.generation_admissions), 1)
                admission = harness.generation_admissions[0]
                self.assertFalse(admission.accepted)
                self.assertIs(
                    admission.stale_reason,
                    StaleCompletionReason.RETIRED_GENERATION,
                )
                self.assertEqual(
                    harness.generation_diagnostics["stale_completion_count"],
                    1,
                )

    def test_queue_overflow_is_explicit_and_does_not_drop_silently(self) -> None:
        controller = DeterministicFakeRuntimeController(max_queue_size=1)
        controller.schedule_stage_action(
            RealtimeStageKind.TEXT_GENERATION,
            lambda action: None,
            correlation_key="accepted",
        )

        with self.assertRaises(FakeRuntimeQueueOverflow):
            controller.schedule_stage_action(
                RealtimeStageKind.VOICE_OUTPUT,
                lambda action: None,
                correlation_key="overflow",
            )

        self.assertEqual(controller.pending_count, 1)
        self.assertEqual(
            controller.trace[-1].kind.value,
            "queue_overflow_injected",
        )

    def test_session_reset_retires_previous_generation(self) -> None:
        session = framework.create_realtime_session()
        try:
            started = session.start_turn(input_text="reset")
            self.assertTrue(started.accepted)
            plan = build_recovery_control_plan(RecoveryAction.RESET_SESSION)

            reset = session.reset(plan)
            delivered: list[str] = []
            stale = session._apply_stage_completion(
                RealtimeStageCompletionEnvelope(
                    turn_id=started.turn_id,
                    generation_id=started.generation_id,
                    stage="integrated_reset_late_completion",
                    value="late",
                ),
                deliver=delivered.append,
            )

            self.assertIs(reset.outcome, RecoveryResetOutcome.APPLIED)
            self.assertTrue(reset.generation_advanced)
            self.assertFalse(stale.accepted)
            self.assertIs(stale.retired_by, GenerationAdvanceReason.RESET)
            self.assertEqual(delivered, [])
        finally:
            session.close()

    def test_active_close_terminalizes_once_and_post_close_start_is_rejected(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="close-active-turn")
        self.assertTrue(started.accepted)

        session.close()
        after_close = session.start_turn(input_text="must-reject")

        self.assertEqual(len(session.terminal_results), 1)
        self.assertIs(session.terminal_results[0].outcome, TurnOutcome.CLOSED)
        self.assertEqual(session.terminal_results[0].turn_id, started.turn_id)
        self.assertFalse(after_close.accepted)
        self.assertIs(after_close.terminal_result.outcome, TurnOutcome.REJECTED)
        self.assertEqual(
            after_close.terminal_result.public_metadata["reason"],
            "session_closed",
        )

    def test_deterministic_race_has_exact_trace_and_exactly_once_terminal(self) -> None:
        harness: DeterministicRealtimeRaceHarness[str, str] = (
            DeterministicRealtimeRaceHarness()
        )
        generation_id = harness.start_generation("turn-a")
        harness.inject_late_generation_completion(
            RealtimeStageKind.TEXT_GENERATION,
            turn_id="turn-a",
            generation_id=generation_id,
            value="late",
            correlation_key="late-response-delta",
            delay_ticks=2,
        )
        harness.schedule_terminal(
            RealtimeStageKind.TEXT_GENERATION,
            turn_id="turn-a",
            outcome=TurnOutcome.INTERRUPTED,
            correlation_key="user-stop",
            result="interrupted",
            delay_ticks=1,
        )
        harness.inject_duplicate_terminal(
            RealtimeStageKind.TEXT_GENERATION,
            turn_id="turn-a",
            outcome=TurnOutcome.INTERRUPTED,
            correlation_key="duplicate",
            result="duplicate",
            copies=2,
            delay_ticks=3,
        )
        harness.advance_generation(GenerationAdvanceReason.INTERRUPT)

        harness.run_until_idle()

        expected_trace = (
            "0|0|late_completion_injected|-|-|text_generation|late-response-delta",
            "1|0|action_scheduled|fake-action-000000|late_completion|text_generation|late-response-delta",
            "2|0|action_scheduled|fake-action-000001|terminal|text_generation|user-stop",
            "3|0|duplicate_terminal_injected|-|-|text_generation|duplicate",
            "4|0|action_scheduled|fake-action-000002|terminal|text_generation|duplicate",
            "5|0|action_scheduled|fake-action-000003|terminal|text_generation|duplicate",
            "6|1|clock_advanced|-|-|-|-",
            "7|1|action_executed|fake-action-000001|terminal|text_generation|user-stop",
            "8|2|clock_advanced|-|-|-|-",
            "9|2|action_executed|fake-action-000000|late_completion|text_generation|late-response-delta",
            "10|3|clock_advanced|-|-|-|-",
            "11|3|action_executed|fake-action-000002|terminal|text_generation|duplicate",
            "12|3|action_executed|fake-action-000003|terminal|text_generation|duplicate",
        )
        harness.assert_trace(expected_trace)
        self.assertEqual(
            tuple(record.status for record in harness.terminal_commits),
            (
                TerminalCommitStatus.FIRST_TERMINAL,
                TerminalCommitStatus.DUPLICATE_TERMINAL,
                TerminalCommitStatus.DUPLICATE_TERMINAL,
            ),
        )
        self.assertEqual(len(harness.terminal_records), 1)
        self.assertEqual(harness.terminal_records[0].result, "interrupted")
        self.assertFalse(harness.generation_admissions[0].accepted)


if __name__ == "__main__":
    unittest.main()
