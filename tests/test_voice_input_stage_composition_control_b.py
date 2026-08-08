"""Provider-free FW-RT6-7b Control B abort/stale tests."""

from __future__ import annotations

from threading import Event, Thread
import unittest

import framework
from framework.realtime_event_payloads import DiagnosticEventPayload


def _source(audio_id: str = "control_b_audio"):
    return framework.VoiceInputAudioSource.from_opaque_id(
        audio_id,
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=250),
        language="ja-JP",
    )


class _BlockingAdapter:
    def __init__(self, *, text: str = "late transcript", raises: bool = False) -> None:
        self.text = text
        self.raises = raises
        self.started = Event()
        self.release = Event()
        self.finished = Event()

    def transcribe(self, *, audio_source, request):
        self.started.set()
        if not self.release.wait(timeout=5.0):
            raise TimeoutError("test adapter release timed out")
        self.finished.set()
        if self.raises:
            raise RuntimeError("private late provider detail")
        return framework.VoiceInputResult.completed(
            self.text,
            language=request.language,
        )


def _run_transcription(session, adapter, output) -> Thread:
    def target() -> None:
        try:
            output["result"] = session.transcribe_audio_result(
                _source(),
                adapter=adapter,
            )
        except BaseException as exc:  # test capture only
            output["exception"] = exc

    thread = Thread(target=target, daemon=True)
    thread.start()
    return thread


class VoiceInputStageCompositionControlBTests(unittest.TestCase):
    def test_abort_without_active_input_is_false(self) -> None:
        session = framework.create_voice_input_session()
        self.assertFalse(session.abort_input())

    def test_active_abort_is_once_and_late_transcript_is_dropped(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)
        adapter = _BlockingAdapter()
        output = {}
        thread = _run_transcription(session, adapter, output)
        self.assertTrue(adapter.started.wait(timeout=5.0))

        self.assertTrue(session.abort_input())
        self.assertFalse(session.abort_input())
        adapter.release.set()
        thread.join(timeout=5.0)

        self.assertFalse(thread.is_alive())
        self.assertTrue(adapter.finished.is_set())
        self.assertNotIn("exception", output)
        self.assertEqual(output["result"].outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertNotIn(framework.RealtimeEventType.TRANSCRIPT_FINAL, [event.type for event in events])
        stale = [event for event in events if event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0].public_metadata["retired_by"], "cancel")
        self.assertFalse(stale[0].public_metadata["provider_hard_cancel_claimed"])

    def test_new_input_retires_old_generation(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)
        adapter = _BlockingAdapter(text="obsolete transcript")
        output = {}
        thread = _run_transcription(session, adapter, output)
        self.assertTrue(adapter.started.wait(timeout=5.0))

        current = session.transcribe_audio_result(_source("current_audio"))
        adapter.release.set()
        thread.join(timeout=5.0)

        self.assertEqual(current.text, "fake transcript")
        self.assertEqual(output["result"].outcome, framework.VoiceInputOutcome.INTERRUPTED)
        finals = [event for event in events if event.type is framework.RealtimeEventType.TRANSCRIPT_FINAL]
        self.assertEqual([event.payload.text for event in finals], ["fake transcript"])
        stale = [event for event in events if event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0].public_metadata["retired_by"], "new_turn")

    def test_reentrant_abort_before_final_transcript_suppresses_delivery(self) -> None:
        session = framework.create_voice_input_session()
        events = []

        def callback(event) -> None:
            events.append(event)
            if event.type is framework.RealtimeEventType.LISTENING_COMPLETED:
                self.assertTrue(session.abort_input())

        session.on_realtime_event(callback)
        result = session.transcribe_audio_result(_source())

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertNotIn(framework.RealtimeEventType.TRANSCRIPT_FINAL, [event.type for event in events])
        self.assertEqual(
            sum(event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED for event in events),
            1,
        )

    def test_late_exception_after_abort_is_safely_suppressed(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)
        adapter = _BlockingAdapter(raises=True)
        output = {}
        thread = _run_transcription(session, adapter, output)
        self.assertTrue(adapter.started.wait(timeout=5.0))

        self.assertTrue(session.abort_input())
        adapter.release.set()
        thread.join(timeout=5.0)

        self.assertNotIn("exception", output)
        self.assertEqual(output["result"].outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertNotIn("private late provider detail", repr([event.as_v6_dict() for event in events]))
        self.assertEqual(
            sum(event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED for event in events),
            1,
        )

    def test_normal_current_completion_is_unchanged(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        result = session.transcribe_audio_result(_source())

        self.assertTrue(result.is_completed)
        self.assertEqual(result.text, "fake transcript")
        self.assertEqual(events[-1].type, framework.RealtimeEventType.TRANSCRIPT_FINAL)
        self.assertFalse(session.abort_input())

    def test_stale_diagnostic_is_typed_and_path_safe(self) -> None:
        private_path = r"E:\private\operator\late-input.wav"
        source = framework.VoiceInputAudioSource.from_file_path(private_path)
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)
        adapter = _BlockingAdapter()
        output = {}

        def target() -> None:
            output["result"] = session.transcribe_audio_result(source, adapter=adapter)

        thread = Thread(target=target, daemon=True)
        thread.start()
        self.assertTrue(adapter.started.wait(timeout=5.0))
        self.assertTrue(session.abort_input())
        adapter.release.set()
        thread.join(timeout=5.0)

        stale = next(event for event in events if event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED)
        self.assertIsInstance(stale.payload, DiagnosticEventPayload)
        self.assertEqual(stale.payload.code, "stale_voice_input_completion")
        self.assertFalse(stale.public_metadata["late_transcript_delivered"])
        self.assertNotIn(private_path, repr(stale.as_v6_dict()))
        self.assertNotIn("operator", repr(stale.as_v6_dict()))


if __name__ == "__main__":
    unittest.main()
