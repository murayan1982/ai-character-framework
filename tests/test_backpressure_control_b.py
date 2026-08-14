"""Provider-free FW-RT6-12b Control B runtime-adoption tests."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import subprocess
import sys
import threading
import unittest

import framework
from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
from framework.backpressure import (
    BackpressureBoundary,
    BackpressureRejectionCode,
    BackpressureState,
)
from framework.backpressure_runtime import BoundedBackpressureRuntime
from framework.identity import EventSequence, GenerationId, SessionId, TurnId
from framework.realtime_capabilities import (
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
)
from framework.realtime_event_hub import (
    EventHubBackpressureError,
    RealtimeEventHub,
)
from framework.realtime_stage import RealtimeStageContext
from framework.realtime_voice_output import ProviderNeutralVoiceSynthesisStage
from framework.realtime_voice_output_queue import (
    BoundedVoiceSynthesisPendingQueue,
    VoiceSynthesisEnqueueOutcome,
)
from framework.voice_input_audio import VoiceInputAudioEncoding, VoiceInputAudioFormat
from framework.voice_input_streaming import (
    VoiceInputAudioChunk,
    VoiceInputStreamConfig,
    VoiceInputStreamRejectionCode,
)
from framework.voice_input_streaming_adapter import (
    DeterministicFakeVoiceInputStreamingAdapter,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_backpressure_flow_control.md",
    "framework/backpressure_runtime.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_session.py",
    "framework/realtime_voice_output_queue.py",
    "framework/voice_input_session.py",
    "framework/voice_input_stream_runtime.py",
    "scripts/smoke_v600_backpressure_control_b.py",
    "tests/test_backpressure_control_b.py",
}


@dataclass(frozen=True, slots=True)
class _Event:
    sequence: EventSequence
    label: str
    type: str = "realtime.diagnostic"


class _BlockingStreamingAdapter(DeterministicFakeVoiceInputStreamingAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def accept_chunk(self, chunk, *, emit_partial):  # type: ignore[no-untyped-def]
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("test audio release timeout")
        super().accept_chunk(chunk, emit_partial=emit_partial)


class _BlockingSynthesisAdapter:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

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
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("test synthesis release timeout")
        return VoiceOutputResult(
            request_state="generated",
            audio_ready=True,
            audio_url="https://example.invalid/audio",
        )


def _config() -> VoiceInputStreamConfig:
    return VoiceInputStreamConfig(
        stream_id="stream_001",
        audio_format=VoiceInputAudioFormat(
            encoding=VoiceInputAudioEncoding.PCM16,
            sample_rate_hz=16_000,
            channel_count=1,
        ),
    )


def _chunk(sequence: int) -> VoiceInputAudioChunk:
    return VoiceInputAudioChunk(
        stream_id="stream_001",
        sequence_number=sequence,
        data=b"private audio payload",
        duration_ms=20,
    )


def _context() -> RealtimeStageContext:
    return RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )


class BackpressureControlBTests(unittest.TestCase):
    def test_runtime_namespace_is_explicit_only(self) -> None:
        namespace = importlib.import_module("framework.backpressure_runtime")
        self.assertEqual(namespace.__all__, ("BoundedBackpressureRuntime",))
        self.assertNotIn("BoundedBackpressureRuntime", framework.__all__)
        self.assertEqual(len(framework.__all__), 127)

    def test_runtime_import_is_provider_network_and_device_safe(self) -> None:
        code = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.backpressure_runtime as runtime
assert runtime.__all__ == ("BoundedBackpressureRuntime",)
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_runtime_pending_capacity_rejects_and_emits(self) -> None:
        events = []
        runtime = BoundedBackpressureRuntime(
            boundary="audio_input",
            maximum_pending_count=1,
            maximum_in_flight_count=1,
            on_overflow=events.append,
        )
        first = runtime.admit_item("audio_1")
        rejected = runtime.admit_item("audio_2")
        self.assertTrue(first.accepted)
        self.assertFalse(rejected.accepted)
        self.assertEqual(
            rejected.rejection_code,
            BackpressureRejectionCode.CAPACITY_REACHED,
        )
        self.assertTrue(rejected.retryable)
        self.assertFalse(rejected.dropped)
        self.assertEqual(runtime.pending_item_ids, ("audio_1",))
        self.assertEqual(events[0].admission.item_id, "audio_2")

    def test_runtime_in_flight_capacity_is_nonblocking(self) -> None:
        runtime = BoundedBackpressureRuntime(
            boundary="response_delta",
            maximum_pending_count=2,
            maximum_in_flight_count=1,
        )
        self.assertTrue(runtime.admit_item("delta_1", start_immediately=True).accepted)
        rejected = runtime.admit_item("delta_2", start_immediately=True)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.snapshot.in_flight_count, 1)
        self.assertTrue(runtime.complete("delta_1"))
        self.assertTrue(runtime.admit_item("delta_2", start_immediately=True).accepted)

    def test_runtime_pause_resume_preserves_accepted_pending_work(self) -> None:
        runtime = BoundedBackpressureRuntime(
            boundary="voice_output",
            maximum_pending_count=2,
            maximum_in_flight_count=1,
        )
        self.assertTrue(runtime.admit_item("voice_1").accepted)
        paused = runtime.pause()
        rejected = runtime.admit_item("voice_2")
        self.assertTrue(paused.accepted)
        self.assertEqual(paused.cancelled_count, 0)
        self.assertEqual(runtime.pending_item_ids, ("voice_1",))
        self.assertEqual(rejected.rejection_code, BackpressureRejectionCode.PAUSED)
        self.assertTrue(rejected.retryable)
        self.assertTrue(runtime.resume().accepted)
        self.assertEqual(runtime.claim().item_id, "voice_1")
        self.assertTrue(runtime.complete("voice_1"))

    def test_runtime_close_retains_accepted_work_and_is_terminal_for_new_work(self) -> None:
        runtime = BoundedBackpressureRuntime(
            boundary="event_subscriber",
            maximum_pending_count=2,
            maximum_in_flight_count=1,
        )
        runtime.admit_item("event_1")
        snapshot = runtime.close()
        rejected = runtime.admit_item("event_2")
        self.assertEqual(snapshot.state, BackpressureState.CLOSED)
        self.assertEqual(runtime.pending_item_ids, ("event_1",))
        self.assertEqual(rejected.rejection_code, BackpressureRejectionCode.CLOSED)
        self.assertFalse(rejected.retryable)
        self.assertEqual(runtime.claim().item_id, "event_1")
        self.assertTrue(runtime.complete("event_1"))

    def test_runtime_overflow_callback_failure_is_isolated(self) -> None:
        def fail(_event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("diagnostic failure")

        runtime = BoundedBackpressureRuntime(
            boundary="audio_input",
            maximum_pending_count=1,
            maximum_in_flight_count=1,
            on_overflow=fail,
        )
        runtime.admit_item("audio_1")
        result = runtime.admit_item("audio_2")
        self.assertFalse(result.accepted)
        self.assertEqual(runtime.snapshot.overflow_count, 1)

    def test_event_hub_exposes_exact_owned_capabilities(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub(delivery_pending_limit=2)
        for boundary in (
            BackpressureBoundary.RESPONSE_DELTA,
            BackpressureBoundary.EVENT_SUBSCRIBER,
        ):
            capability = hub.backpressure_capability(boundary)
            self.assertTrue(capability.supported)
            self.assertEqual(capability.maximum_pending_count, 2)
            self.assertEqual(capability.maximum_in_flight_count, 1)
            self.assertFalse(capability.silent_drop)
        with self.assertRaises(ValueError):
            hub.backpressure_capability(BackpressureBoundary.AUDIO_INPUT)

    def test_event_hub_reentrant_overflow_does_not_consume_sequence(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub(delivery_pending_limit=1)
        delivered = []
        rejected = []

        def callback(event: _Event) -> None:
            delivered.append(event)
            if event.label == "root":
                hub.emit(lambda sequence: _Event(sequence, "queued"))
                try:
                    hub.emit(lambda sequence: _Event(sequence, "rejected"))
                except EventHubBackpressureError as error:
                    rejected.append(error.result)

        hub.subscribe(callback)
        root = hub.emit(lambda sequence: _Event(sequence, "root"))
        next_event = hub.emit(lambda sequence: _Event(sequence, "next"))
        self.assertEqual(root.sequence, 1)
        self.assertEqual(next_event.sequence, 3)
        self.assertEqual([event.label for event in delivered], ["root", "queued", "next"])
        self.assertEqual(
            rejected[0].rejection_code,
            BackpressureRejectionCode.CAPACITY_REACHED,
        )
        self.assertFalse(rejected[0].dropped)
        self.assertEqual(hub.diagnostics.delivery_backpressure_rejection_count, 1)

    def test_response_delta_pause_rejects_atomically_and_resumes(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub()
        hub.pause_backpressure(BackpressureBoundary.RESPONSE_DELTA)
        with self.assertRaises(EventHubBackpressureError) as raised:
            hub.emit(
                lambda sequence: _Event(
                    sequence,
                    "delta",
                    "realtime.response.delta",
                )
            )
        self.assertEqual(
            raised.exception.result.admission.boundary,
            BackpressureBoundary.RESPONSE_DELTA,
        )
        self.assertEqual(
            hub.backpressure_snapshot(BackpressureBoundary.EVENT_SUBSCRIBER).pending_count,
            0,
        )
        hub.resume_backpressure(BackpressureBoundary.RESPONSE_DELTA)
        accepted = hub.emit(
            lambda sequence: _Event(sequence, "delta", "realtime.response.delta")
        )
        self.assertEqual(accepted.sequence, 1)

    def test_event_subscriber_pause_rejects_every_event(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub()
        hub.pause_backpressure(BackpressureBoundary.EVENT_SUBSCRIBER)
        with self.assertRaises(EventHubBackpressureError) as raised:
            hub.emit(lambda sequence: _Event(sequence, "blocked"))
        self.assertEqual(
            raised.exception.result.rejection_code,
            BackpressureRejectionCode.PAUSED,
        )
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(hub.event_history, ())

    def test_realtime_session_proxies_event_boundaries(self) -> None:
        session = framework.RealtimeSession()
        try:
            capability = session.backpressure_capability("event_subscriber")
            self.assertTrue(capability.supported)
            self.assertEqual(capability.boundary, BackpressureBoundary.EVENT_SUBSCRIBER)
            self.assertTrue(session.pause_backpressure("response_delta").accepted)
            self.assertEqual(
                session.backpressure_snapshot("response_delta").state,
                BackpressureState.PAUSED,
            )
            self.assertTrue(session.resume_backpressure("response_delta").accepted)
        finally:
            session.close()

    def test_voice_input_session_exposes_truthful_audio_capability(self) -> None:
        session = framework.VoiceInputSession()
        capability = session.audio_input_backpressure_capability
        self.assertEqual(capability.boundary, BackpressureBoundary.AUDIO_INPUT)
        self.assertEqual(capability.maximum_pending_count, 1)
        self.assertEqual(capability.maximum_in_flight_count, 1)
        self.assertTrue(capability.pause_resume_supported)
        self.assertFalse(capability.silent_drop)

    def test_voice_input_pause_is_retryable_and_resume_preserves_sequence(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        self.assertTrue(session.begin_audio_stream(_config()))
        self.assertTrue(session.pause_audio_input().accepted)
        rejected = session.send_audio_chunk(_chunk(0))
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.rejection_code, VoiceInputStreamRejectionCode.NOT_SUPPORTED)
        self.assertTrue(rejected.retryable)
        self.assertEqual(
            rejected.public_metadata["backpressure_rejection_code"],
            "paused",
        )
        self.assertTrue(session.resume_audio_input().accepted)
        self.assertTrue(session.send_audio_chunk(_chunk(0)).accepted)

    def test_voice_input_concurrent_chunk_is_typed_capacity_rejected(self) -> None:
        session = framework.VoiceInputSession()
        adapter = _BlockingStreamingAdapter()
        session.configure_audio_streaming(adapter)
        self.assertTrue(session.begin_audio_stream(_config()))
        completed = []
        worker = threading.Thread(
            target=lambda: completed.append(session.send_audio_chunk(_chunk(0)))
        )
        worker.start()
        self.assertTrue(adapter.entered.wait(5))
        rejected = session.send_audio_chunk(_chunk(0))
        self.assertFalse(rejected.accepted)
        self.assertTrue(rejected.retryable)
        self.assertEqual(
            rejected.public_metadata["backpressure_rejection_code"],
            "capacity_reached",
        )
        self.assertEqual(session.audio_input_backpressure_snapshot.in_flight_count, 1)
        adapter.release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(completed[0].accepted)
        self.assertEqual(session.audio_input_backpressure_snapshot.in_flight_count, 0)
        self.assertTrue(session.send_audio_chunk(_chunk(1)).accepted)

    def test_voice_input_close_is_terminal_and_payload_free(self) -> None:
        session = framework.VoiceInputSession()
        session.close()
        rejected = session.send_audio_chunk(_chunk(0))
        self.assertEqual(rejected.rejection_code, VoiceInputStreamRejectionCode.SESSION_CLOSED)
        self.assertFalse(rejected.retryable)
        generic = session.last_audio_input_backpressure_result
        self.assertEqual(generic.rejection_code, BackpressureRejectionCode.CLOSED)
        self.assertNotIn("private audio payload", repr(generic))

    def test_voice_output_queue_exposes_truthful_capability(self) -> None:
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=2)
        capability = queue.backpressure_capability
        self.assertEqual(capability.boundary, BackpressureBoundary.VOICE_OUTPUT)
        self.assertEqual(capability.maximum_pending_count, 2)
        self.assertEqual(capability.maximum_in_flight_count, 1)
        self.assertFalse(capability.silent_drop)

    def test_voice_output_capacity_rejection_preserves_old_and_new_types(self) -> None:
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=1)
        accepted = queue.enqueue(context=_context(), request=VoiceOutputRequest("first"))
        rejected = queue.enqueue(context=_context(), request=VoiceOutputRequest("second"))
        self.assertTrue(accepted.accepted)
        self.assertEqual(rejected.outcome, VoiceSynthesisEnqueueOutcome.REJECTED_FULL)
        self.assertEqual(
            rejected.backpressure_result.rejection_code,
            BackpressureRejectionCode.CAPACITY_REACHED,
        )
        self.assertTrue(rejected.retryable)
        self.assertFalse(rejected.dropped)
        self.assertEqual(queue.pending_work, (accepted.work,))

    def test_voice_output_pause_resume_is_typed_and_non_consuming(self) -> None:
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=1)
        self.assertTrue(queue.pause().accepted)
        rejected = queue.enqueue(context=_context(), request=VoiceOutputRequest("paused"))
        self.assertEqual(rejected.outcome, VoiceSynthesisEnqueueOutcome.REJECTED_PAUSED)
        self.assertTrue(rejected.retryable)
        self.assertEqual(queue.pending_count, 0)
        self.assertTrue(queue.resume().accepted)
        self.assertTrue(
            queue.enqueue(context=_context(), request=VoiceOutputRequest("accepted")).accepted
        )

    def test_voice_output_close_retains_pending_and_rejects_new_work(self) -> None:
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=2)
        accepted = queue.enqueue(context=_context(), request=VoiceOutputRequest("pending"))
        queue.close()
        rejected = queue.enqueue(context=_context(), request=VoiceOutputRequest("closed"))
        self.assertEqual(rejected.outcome, VoiceSynthesisEnqueueOutcome.REJECTED_CLOSED)
        self.assertFalse(rejected.retryable)
        self.assertEqual(queue.pending_work, (accepted.work,))

    def test_voice_output_handoff_reports_in_flight_and_never_leaks_request(self) -> None:
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=1)
        adapter = _BlockingSynthesisAdapter()
        stage = ProviderNeutralVoiceSynthesisStage(adapter)
        accepted = queue.enqueue(
            context=_context(),
            request=VoiceOutputRequest("private synthesis text"),
        )
        completed = []
        worker = threading.Thread(
            target=lambda: completed.append(queue.handoff_next(stage=stage))
        )
        worker.start()
        self.assertTrue(adapter.entered.wait(5))
        snapshot = queue.backpressure_snapshot
        self.assertEqual(snapshot.pending_count, 0)
        self.assertEqual(snapshot.in_flight_count, 1)
        self.assertNotIn("private synthesis text", repr(snapshot))
        second = queue.enqueue(context=_context(), request=VoiceOutputRequest("next"))
        self.assertTrue(second.accepted)
        adapter.release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(completed[0].work_id, accepted.work.work_id)
        self.assertEqual(queue.backpressure_snapshot.in_flight_count, 0)

    def test_voice_output_clear_withdraws_only_explicit_pending_work(self) -> None:
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=2)
        first = queue.enqueue(context=_context(), request=VoiceOutputRequest("first"))
        second = queue.enqueue(context=_context(), request=VoiceOutputRequest("second"))
        cleared = queue.clear_pending(context=first.work.context)
        self.assertEqual(cleared.cleared_work, (first.work,))
        self.assertEqual(queue.pending_work, (second.work,))
        self.assertEqual(queue.backpressure_snapshot.pending_count, 1)

    def test_docs_and_task_boundary_describe_control_b_without_closure(self) -> None:
        docs = {
            name: (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
            for name in (
                "app_integration_contract.md",
                "public_facade.md",
                "v600_backpressure_flow_control.md",
            )
        }
        combined = "\n".join(docs.values())
        for marker in (
            "FW-RT6-12b-B-APP-BACKPRESSURE:BEGIN",
            "FW-RT6-12b-B-PUBLIC-BACKPRESSURE:BEGIN",
            "FW-RT6-12b-B-RUNTIME-ADOPTION:BEGIN",
        ):
            self.assertEqual(combined.count(marker), 1)
        for phrase in (
            "framework.backpressure_runtime",
            "VoiceInputSession",
            "RealtimeSession",
            "BoundedVoiceSynthesisPendingQueue",
            "reject_newest",
            "0 / 6 CLOSED",
            "Control B: IMPLEMENTED / AWAITING_REVIEW",
        ):
            self.assertIn(phrase, combined)
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
        section = tasklist.split("## FW-RT6-12b — P1 backpressure", 1)[1].split(
            "## FW-RT6-12c", 1
        )[0]
        self.assertEqual(section.count("- [ ]"), 6)
        self.assertEqual(section.count("- [x]"), 0)
        acceptance_marker_count = tasklist.count(
            "FW-RT6-12b-B-ACCEPTANCE-SYNC:BEGIN"
        )
        self.assertLessEqual(acceptance_marker_count, 1)
        if acceptance_marker_count:
            self.assertEqual(
                tasklist.count("FW-RT6-12b-B-ACCEPTANCE-SYNC:END"),
                1,
            )
            self.assertIn(
                "Control B: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH",
                tasklist,
            )


if __name__ == "__main__":
    unittest.main()
