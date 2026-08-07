"""Provider-free FW-RT6-7b Control A lifecycle/privacy tests."""

from __future__ import annotations

import json
import unittest

import framework
from framework.realtime_event_payloads import (
    LifecycleEventPayload,
    TranscriptEventPayload,
)


class _FailedAdapter:
    def transcribe(self, *, audio_source, request):
        return framework.VoiceInputResult.failed(
            safe_message="Voice input provider failed.",
        )


class _RaisingAdapter:
    def transcribe(self, *, audio_source, request):
        raise RuntimeError("private/provider detail must not enter public events")


def _opaque_source():
    return framework.VoiceInputAudioSource.from_opaque_id(
        "control_a_audio",
        audio_format=framework.VoiceInputAudioFormat.wav(
            sample_rate_hz=16000,
            channel_count=1,
            duration_ms=250,
        ),
        language="ja-JP",
        max_duration_ms=1000,
    )


class VoiceInputStageCompositionControlATests(unittest.TestCase):
    def test_completed_event_order_and_correlation(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        result = session.transcribe_audio_result(_opaque_source())

        self.assertTrue(result.is_completed)
        self.assertEqual(
            [event.type for event in events],
            [
                framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
                framework.RealtimeEventType.LISTENING_STARTED,
                framework.RealtimeEventType.LISTENING_COMPLETED,
                framework.RealtimeEventType.TRANSCRIPT_FINAL,
            ],
        )
        self.assertTrue(all(event.session_id == session.session_id for event in events))
        self.assertEqual(len({event.turn_id for event in events}), 1)
        self.assertEqual(len({event.generation_id for event in events}), 1)
        self.assertEqual([int(event.sequence) for event in events], [1, 2, 3, 4])

    def test_lifecycle_and_final_transcript_payloads_are_typed(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        session.transcribe_audio_result(_opaque_source())

        self.assertTrue(all(isinstance(event.payload, LifecycleEventPayload) for event in events[:3]))
        final = events[-1]
        self.assertIsInstance(final.payload, TranscriptEventPayload)
        self.assertEqual(final.payload.text, "fake transcript")
        self.assertTrue(final.payload.is_final)

    def test_file_path_never_enters_public_event(self) -> None:
        private_path = r"E:\private\operator\voice-input.wav"
        source = framework.VoiceInputAudioSource.from_file_path(
            private_path,
            audio_format=framework.VoiceInputAudioFormat.wav(),
            language="ja-JP",
        )
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        session.transcribe_audio_result(source)

        serialized = json.dumps(
            [dict(event.as_v6_dict()) for event in events],
            ensure_ascii=False,
            default=lambda value: dict(value),
        )
        self.assertNotIn(private_path, serialized)
        self.assertNotIn("operator", serialized)
        for event in events:
            self.assertEqual(event.public_metadata["source_kind"], "file_path")
            self.assertFalse(event.public_metadata["audio_path_exposed"])
            self.assertFalse(event.public_metadata["raw_audio_retained"])

    def test_failed_result_emits_typed_failure_without_result_change(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        result = session.transcribe_audio_result(_opaque_source(), adapter=_FailedAdapter())

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.FAILED)
        self.assertEqual(
            [event.type for event in events],
            [
                framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
                framework.RealtimeEventType.LISTENING_STARTED,
                framework.RealtimeEventType.VOICE_INPUT_FAILED,
            ],
        )
        failed = events[-1]
        self.assertIsInstance(failed.payload, LifecycleEventPayload)
        self.assertEqual(failed.payload.reason, "failed")
        self.assertEqual(failed.public_error_code, framework.RealtimeErrorCode.PROVIDER_ERROR)

    def test_adapter_exception_emits_safe_failure_and_preserves_exception(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        with self.assertRaisesRegex(RuntimeError, "private/provider detail"):
            session.transcribe_audio_result(_opaque_source(), adapter=_RaisingAdapter())

        failed = events[-1]
        self.assertEqual(failed.type, framework.RealtimeEventType.VOICE_INPUT_FAILED)
        self.assertEqual(failed.safe_message, "Voice input failed.")
        self.assertNotIn("private/provider", repr(failed.as_v6_dict()))

    def test_audio_source_is_not_retained_and_result_shape_is_unchanged(self) -> None:
        session = framework.create_voice_input_session()
        source = _opaque_source()
        result_fields = tuple(framework.VoiceInputResult.__dataclass_fields__)

        session.transcribe_audio_result(source)

        self.assertEqual(
            result_fields,
            (
                "outcome",
                "text",
                "language",
                "confidence",
                "duration_ms",
                "public_error_code",
                "safe_message",
                "retryable",
                "public_metadata",
            ),
        )
        self.assertFalse(any(value is source for value in vars(session).values()))
        self.assertFalse(any("audio_source" in name for name in vars(session)))


if __name__ == "__main__":
    unittest.main()
