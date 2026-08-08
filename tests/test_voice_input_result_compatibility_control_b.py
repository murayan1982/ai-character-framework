"""Provider-free FW-RT6-7c Control B compatibility-bridge tests."""

from __future__ import annotations

import unittest

import framework
from framework.realtime_event_payloads import (
    LifecycleEventPayload,
    TranscriptEventPayload,
)


def _source(audio_id: str = "result_control_b_audio"):
    return framework.VoiceInputAudioSource.from_opaque_id(
        audio_id,
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=250),
        language="ja-JP",
    )


class VoiceInputResultCompatibilityControlBTests(unittest.TestCase):
    def test_listen_result_has_full_context_and_legacy_projection(self) -> None:
        session = framework.create_voice_input_session(language="ja-JP")
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)

        result = session.listen_result()

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.UNAVAILABLE)
        self.assertEqual(result.session_id, session.session_id)
        self.assertIsNotNone(result.turn_id)
        self.assertIsNotNone(result.generation_id)
        self.assertTrue(all(event.session_id == result.session_id for event in canonical))
        self.assertTrue(all(event.turn_id == result.turn_id for event in canonical))
        self.assertTrue(
            all(event.generation_id == result.generation_id for event in canonical)
        )
        self.assertEqual(
            [event["type"] for event in legacy],
            ["voice_input.started", "voice_input.unavailable"],
        )
        self.assertEqual(legacy[0]["payload"]["language"], "ja-JP")

    def test_listen_result_uses_typed_canonical_failure(self) -> None:
        session = framework.create_voice_input_session()
        canonical = []
        session.on_realtime_event(canonical.append)

        result = session.listen_result()

        self.assertEqual(
            [event.type for event in canonical],
            [
                framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
                framework.RealtimeEventType.VOICE_INPUT_FAILED,
            ],
        )
        self.assertTrue(all(isinstance(event.payload, LifecycleEventPayload) for event in canonical))
        self.assertEqual(canonical[-1].safe_message, result.safe_message)
        self.assertEqual(canonical[-1].retryable, result.retryable)

    def test_text_fallback_has_full_context_and_legacy_projection(self) -> None:
        session = framework.create_voice_input_session(language="ja-JP")
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)

        result = session.text_fallback_result(
            "fallback text",
            public_metadata={"purpose": "test", "token": "private-value"},
        )

        self.assertTrue(result.is_completed)
        self.assertEqual(result.session_id, session.session_id)
        self.assertIsNotNone(result.turn_id)
        self.assertIsNotNone(result.generation_id)
        self.assertEqual(result.public_metadata["token"], "<redacted>")
        self.assertEqual([event["type"] for event in legacy], ["voice_input.text_fallback"])
        self.assertEqual(legacy[0]["payload"]["language"], "ja-JP")
        self.assertNotIn("private-value", repr(legacy))

    def test_text_fallback_uses_typed_preflight_and_final_transcript(self) -> None:
        session = framework.create_voice_input_session()
        canonical = []
        session.on_realtime_event(canonical.append)

        result = session.text_fallback_result("typed fallback")

        self.assertEqual(
            [event.type for event in canonical],
            [
                framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
                framework.RealtimeEventType.TRANSCRIPT_FINAL,
            ],
        )
        self.assertIsInstance(canonical[0].payload, LifecycleEventPayload)
        self.assertIsInstance(canonical[1].payload, TranscriptEventPayload)
        self.assertEqual(canonical[1].payload.text, result.text)
        self.assertTrue(canonical[1].payload.is_final)

    def test_all_post_close_result_paths_share_session_only_rejection(self) -> None:
        session = framework.create_voice_input_session()
        session.close()

        results = (
            session.listen_result(),
            session.text_fallback_result("ignored"),
            session.transcribe_audio_result(_source()),
        )

        for result in results:
            self.assertEqual(result.outcome, framework.VoiceInputOutcome.CLOSED)
            self.assertEqual(
                result.public_error_code,
                framework.VoiceInputErrorCode.SESSION_CLOSED,
            )
            self.assertEqual(result.session_id, session.session_id)
            self.assertIsNone(result.turn_id)
            self.assertIsNone(result.generation_id)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_close_projects_one_canonical_and_one_legacy_event(self) -> None:
        session = framework.create_voice_input_session()
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)

        session.close()
        session.close()
        session.listen_result()
        session.text_fallback_result("ignored")
        session.transcribe_audio_result(_source())

        self.assertEqual([event.type for event in canonical], [framework.RealtimeEventType.SESSION_CLOSED])
        self.assertIsInstance(canonical[0].payload, LifecycleEventPayload)
        self.assertEqual(canonical[0].session_id, session.session_id)
        self.assertIsNone(canonical[0].turn_id)
        self.assertIsNone(canonical[0].generation_id)
        self.assertEqual([event["type"] for event in legacy], ["voice_input.closed"])
        self.assertFalse(session.abort_input())

    def test_host_audio_keeps_existing_legacy_mapping_silence(self) -> None:
        session = framework.create_voice_input_session()
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)

        result = session.transcribe_audio_result(_source())

        self.assertTrue(result.is_completed)
        self.assertEqual(legacy, [])
        self.assertEqual(canonical[-1].type, framework.RealtimeEventType.TRANSCRIPT_FINAL)

    def test_legacy_started_callback_can_abort_listen_generation(self) -> None:
        session = framework.create_voice_input_session()
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)

        def callback(event) -> None:
            legacy.append(event)
            if event["type"] == "voice_input.started":
                self.assertTrue(session.abort_input())

        session.on_event(callback)
        result = session.listen_result()

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertEqual(result.session_id, session.session_id)
        self.assertIsNotNone(result.turn_id)
        self.assertIsNotNone(result.generation_id)
        self.assertEqual([event["type"] for event in legacy], ["voice_input.started"])
        self.assertNotIn(
            "voice_input.unavailable",
            [event["type"] for event in legacy],
        )
        self.assertEqual(
            [event.type for event in canonical],
            [
                framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
                framework.RealtimeEventType.VOICE_INPUT_FAILED,
            ],
        )


if __name__ == "__main__":
    unittest.main()
