"""Provider-free FW-RT6-9d Control B runtime-adoption tests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest

import framework
from framework._realtime_voice_output_control import (
    CancelableProviderNeutralVoiceSynthesisStage,
)
from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
from framework.identity import GenerationId, SessionId, TurnId
from framework.motion import MotionOutcome, MotionRequest, MotionResult
from framework.realtime import RealtimeEvent, RealtimeEventType
from framework.realtime_capabilities import (
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from framework.realtime_event_hub import RealtimeEventHub
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    RealtimeGenerationGate,
    RealtimeStageCompletionEnvelope,
)
from framework.realtime_stage import RealtimeStageContext
from framework.realtime_text_generation import ProviderNeutralTextGenerationStream
from framework.voice_artifacts import FileVoiceArtifactStore, VoiceArtifactState


class _RecordingGate(RealtimeGenerationGate):
    def __init__(self) -> None:
        super().__init__()
        self.applied_stages: list[str] = []

    def apply_completion(self, envelope, *, deliver):
        self.applied_stages.append(envelope.stage)
        return super().apply_completion(envelope, deliver=deliver)


class _BlockingAppendList(list[str]):
    def __init__(self) -> None:
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def append(self, value: str) -> None:
        self.entered.set()
        if not self.release.wait(timeout=2.0):
            raise AssertionError("test did not release bounded delta application")
        super().append(value)


class _BlockingVoiceAdapter:
    def __init__(self, text: str = "late transcript") -> None:
        self.text = text
        self.entered = Event()
        self.release = Event()

    def transcribe(self, *, audio_source, request):
        self.entered.set()
        if not self.release.wait(timeout=2.0):
            raise AssertionError("test did not release voice input adapter")
        return framework.VoiceInputResult.completed(
            self.text,
            language=request.language,
        )


class _ArtifactAdapter:
    def __init__(self, store: FileVoiceArtifactStore) -> None:
        self.store = store

    def capability(self) -> RealtimeVoiceOutputCapability:
        return RealtimeVoiceOutputCapability(
            runtime=RuntimeCapabilityState(
                configured=True,
                runtime_available=True,
                fake_runtime=True,
                unavailable_reason=None,
            ),
            audio_formats=("mp3",),
        )

    def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
        ref = self.store.store(b"provider-free-audio", audio_format="mp3")
        return VoiceOutputResult(
            request_state="generated",
            audio_ready=True,
            audio_format="mp3",
            audio_artifact_ref=ref,
        )


class _BlockingBindStore(FileVoiceArtifactStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.bind_entered = Event()
        self.bind_release = Event()

    def bind_generation(self, artifact, generation_id):
        self.bind_entered.set()
        if not self.bind_release.wait(timeout=2.0):
            raise AssertionError("test did not release artifact binding")
        return super().bind_generation(artifact, generation_id)


def _text_context(gate: RealtimeGenerationGate) -> RealtimeStageContext:
    turn_id = TurnId.new()
    generation_id = gate.start_generation(turn_id)
    return RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=turn_id,
        generation_id=generation_id,
    )


def _text_stream(
    gate: RealtimeGenerationGate,
    context: RealtimeStageContext,
) -> ProviderNeutralTextGenerationStream:
    return ProviderNeutralTextGenerationStream(
        context=context,
        capability=TextGenerationCapability(
            streaming_supported=True,
            cooperative_cancel_supported=True,
        ),
        source=iter((("delta", ()),)),
        user_input="provider-free input",
        generation_gate=gate,
    )


def _audio_source():
    return framework.VoiceInputAudioSource.from_opaque_id(
        "fw-rt6-9d-control-b",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=100),
        language="ja-JP",
    )


class EndToEndStaleControlBTests(unittest.TestCase):
    def test_text_delta_uses_exact_atomic_delivery_label(self) -> None:
        gate = _RecordingGate()
        context = _text_context(gate)
        stream = _text_stream(gate, context)

        delta = next(stream)

        self.assertEqual(delta.text, "delta")
        self.assertEqual(stream.delivered_delta_count, 1)
        self.assertEqual(gate.applied_stages, ["text_generation_delta"])
        self.assertEqual(gate.diagnostics["accepted_completion_count"], 1)

    def test_retired_text_delta_is_suppressed_before_stream_state_application(self) -> None:
        gate = _RecordingGate()
        context = _text_context(gate)
        stream = _text_stream(gate, context)
        gate.advance(GenerationAdvanceReason.NEW_TURN)

        with self.assertRaises(StopIteration):
            next(stream)

        self.assertTrue(stream.closed)
        self.assertEqual(stream.delivered_delta_count, 0)
        self.assertEqual(gate.applied_stages, ["text_generation_delta"])
        self.assertEqual(gate.diagnostics["stale_completion_count"], 1)

    def test_text_delta_application_excludes_competing_generation_advance(self) -> None:
        gate = RealtimeGenerationGate()
        context = _text_context(gate)
        stream = _text_stream(gate, context)
        blocking_parts = _BlockingAppendList()
        stream._assistant_parts = blocking_parts
        output: list[object] = []
        advance_finished = Event()

        worker = Thread(target=lambda: output.append(next(stream)), daemon=True)
        worker.start()
        self.assertTrue(blocking_parts.entered.wait(timeout=2.0))
        advancer = Thread(
            target=lambda: (
                gate.advance(GenerationAdvanceReason.INTERRUPT),
                advance_finished.set(),
            ),
            daemon=True,
        )
        advancer.start()
        self.assertFalse(advance_finished.wait(timeout=0.05))
        blocking_parts.release.set()
        worker.join(timeout=2.0)
        advancer.join(timeout=2.0)

        self.assertFalse(worker.is_alive())
        self.assertFalse(advancer.is_alive())
        self.assertEqual(len(output), 1)
        self.assertEqual(stream.delivered_delta_count, 1)

    def test_transcript_uses_exact_atomic_delivery_label(self) -> None:
        session = framework.create_voice_input_session()
        gate = _RecordingGate()
        session._generation_gate = gate
        events: list[RealtimeEvent] = []
        session.on_realtime_event(events.append)

        result = session.transcribe_audio_result(_audio_source())

        self.assertTrue(result.is_completed)
        self.assertEqual(gate.applied_stages, ["voice_input_transcript"])
        self.assertEqual(events[-1].type, RealtimeEventType.TRANSCRIPT_FINAL)

    def test_reentrant_abort_wins_before_final_transcript_application(self) -> None:
        session = framework.create_voice_input_session()
        gate = _RecordingGate()
        session._generation_gate = gate
        events: list[RealtimeEvent] = []

        def abort_on_completion(event: RealtimeEvent) -> None:
            events.append(event)
            if event.type is RealtimeEventType.LISTENING_COMPLETED:
                self.assertTrue(session.abort_input())

        session.on_realtime_event(abort_on_completion)
        result = session.transcribe_audio_result(_audio_source())

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertNotIn(
            RealtimeEventType.TRANSCRIPT_FINAL,
            [event.type for event in events],
        )
        self.assertEqual(gate.applied_stages, ["voice_input_transcript"])
        self.assertEqual(gate.diagnostics["stale_completion_count"], 1)

    def test_close_retires_inflight_voice_input_before_transcript_application(self) -> None:
        session = framework.create_voice_input_session()
        adapter = _BlockingVoiceAdapter()
        events: list[RealtimeEvent] = []
        output: list[framework.VoiceInputResult] = []
        session.on_realtime_event(events.append)
        worker = Thread(
            target=lambda: output.append(
                session.transcribe_audio_result(_audio_source(), adapter=adapter)
            ),
            daemon=True,
        )
        worker.start()
        self.assertTrue(adapter.entered.wait(timeout=2.0))

        session.close()
        adapter.release.set()
        worker.join(timeout=2.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(output[0].outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertNotIn(
            RealtimeEventType.TRANSCRIPT_FINAL,
            [event.type for event in events],
        )
        stale = next(
            event for event in events
            if event.type is RealtimeEventType.STALE_RESULT_DROPPED
        )
        self.assertEqual(stale.public_metadata["retired_by"], "session_closed")

    def test_voice_artifact_uses_exact_atomic_delivery_label(self) -> None:
        with TemporaryDirectory() as directory:
            store = FileVoiceArtifactStore(Path(directory) / "artifacts")
            gate = _RecordingGate()
            context = _text_context(gate)
            stage = CancelableProviderNeutralVoiceSynthesisStage(
                _ArtifactAdapter(store),
                artifact_store=store,
                generation_gate=gate,
            )

            envelope = stage.start(
                context=context,
                request=VoiceOutputRequest(text="provider-free"),
            )

            record = store.resolve(envelope.result.audio_artifact_ref)
            self.assertTrue(envelope.result.has_audio_handoff)
            self.assertIsNotNone(record)
            self.assertEqual(record.generation_id, context.generation_id)
            self.assertEqual(gate.applied_stages, ["voice_output_artifact"])

    def test_retired_voice_artifact_is_suppressed_and_invalidated(self) -> None:
        with TemporaryDirectory() as directory:
            store = FileVoiceArtifactStore(Path(directory) / "artifacts")
            gate = _RecordingGate()
            context = _text_context(gate)
            gate.advance(GenerationAdvanceReason.INTERRUPT)
            stage = CancelableProviderNeutralVoiceSynthesisStage(
                _ArtifactAdapter(store),
                artifact_store=store,
                generation_gate=gate,
            )

            envelope = stage.start(
                context=context,
                request=VoiceOutputRequest(text="provider-free"),
            )

            self.assertEqual(envelope.result.request_state, "stale")
            self.assertFalse(envelope.result.has_audio_handoff)
            records = tuple(stored.record for stored in store._records.values())
            self.assertEqual(records[0].state, VoiceArtifactState.INVALIDATED)
            self.assertEqual(gate.applied_stages, ["voice_output_artifact"])

    def test_voice_artifact_binding_excludes_competing_generation_advance(self) -> None:
        with TemporaryDirectory() as directory:
            store = _BlockingBindStore(Path(directory) / "artifacts")
            gate = RealtimeGenerationGate()
            context = _text_context(gate)
            stage = CancelableProviderNeutralVoiceSynthesisStage(
                _ArtifactAdapter(store),
                artifact_store=store,
                generation_gate=gate,
            )
            output: list[object] = []
            advance_finished = Event()
            worker = Thread(
                target=lambda: output.append(
                    stage.start(
                        context=context,
                        request=VoiceOutputRequest(text="provider-free"),
                    )
                ),
                daemon=True,
            )
            worker.start()
            self.assertTrue(store.bind_entered.wait(timeout=2.0))
            advancer = Thread(
                target=lambda: (
                    gate.advance(GenerationAdvanceReason.CANCEL),
                    advance_finished.set(),
                ),
                daemon=True,
            )
            advancer.start()
            self.assertFalse(advance_finished.wait(timeout=0.05))
            store.bind_release.set()
            worker.join(timeout=2.0)
            advancer.join(timeout=2.0)

            self.assertFalse(worker.is_alive())
            self.assertFalse(advancer.is_alive())
            self.assertTrue(output[0].result.has_audio_handoff)

    def test_motion_completion_uses_exact_atomic_delivery_label(self) -> None:
        hub = RealtimeEventHub[RealtimeEvent]()
        gate = _RecordingGate()
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        session = framework.create_motion_session()
        session._bind_realtime_coordination(event_hub=hub, generation_gate=gate)

        result = session.apply_motion(
            MotionRequest.expression_change(
                "smile",
                turn_id=turn_id,
                generation_id=generation_id,
            )
        )

        self.assertEqual(result.outcome, MotionOutcome.COMPLETED)
        self.assertEqual(gate.applied_stages, ["motion_completion"])

    def test_retired_motion_completion_is_not_published_as_completed(self) -> None:
        hub = RealtimeEventHub[RealtimeEvent]()
        gate = _RecordingGate()
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        gate.advance(GenerationAdvanceReason.RESET)
        session = framework.create_motion_session()
        session._bind_realtime_coordination(event_hub=hub, generation_gate=gate)

        result = session.apply_motion(
            MotionRequest.expression_change(
                "smile",
                turn_id=turn_id,
                generation_id=generation_id,
            )
        )

        self.assertEqual(result.outcome, MotionOutcome.INTERRUPTED)
        self.assertNotIn(
            RealtimeEventType.MOTION_COMPLETED,
            [event.type for event in hub.event_history],
        )
        self.assertEqual(gate.applied_stages, ["motion_completion"])

    def test_motion_application_excludes_competing_generation_advance(self) -> None:
        hub = RealtimeEventHub[RealtimeEvent]()
        gate = RealtimeGenerationGate()
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        session = framework.create_motion_session()
        session._bind_realtime_coordination(event_hub=hub, generation_gate=gate)
        request = MotionRequest.expression_change(
            "smile",
            turn_id=turn_id,
            generation_id=generation_id,
        )
        result = MotionResult.completed(request=request, session_id=session.info.session_id)
        delivery_entered = Event()
        release_delivery = Event()
        advance_finished = Event()
        decisions: list[object] = []

        def deliver(_result: MotionResult) -> None:
            delivery_entered.set()
            self.assertTrue(release_delivery.wait(timeout=2.0))

        worker = Thread(
            target=lambda: decisions.append(
                session._apply_motion_completion(
                    request=request,
                    result=result,
                    deliver=deliver,
                )
            ),
            daemon=True,
        )
        worker.start()
        self.assertTrue(delivery_entered.wait(timeout=2.0))
        advancer = Thread(
            target=lambda: (
                gate.advance(GenerationAdvanceReason.INTERRUPT),
                advance_finished.set(),
            ),
            daemon=True,
        )
        advancer.start()
        self.assertFalse(advance_finished.wait(timeout=0.05))
        release_delivery.set()
        worker.join(timeout=2.0)
        advancer.join(timeout=2.0)

        self.assertFalse(worker.is_alive())
        self.assertFalse(advancer.is_alive())
        self.assertTrue(decisions[0].accepted)

    def test_session_central_ingress_adopts_atomic_application(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="provider-free")
        delivered: list[str] = []
        decision = session._apply_stage_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=started.turn_id,
                generation_id=started.generation_id,
                stage="text_generation_delta",
                value="delta",
            ),
            deliver=delivered.append,
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(delivered, ["delta"])

    def test_public_versions_and_later_reset_scope_remain_unchanged(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        self.assertTrue(hasattr(framework.RealtimeSession, "reset"))


if __name__ == "__main__":
    unittest.main()
