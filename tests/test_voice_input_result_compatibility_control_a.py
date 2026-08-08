"""Provider-free FW-RT6-7c Control A result-correlation tests."""

from __future__ import annotations

from dataclasses import fields
from threading import Event, Thread
import unittest

import framework


def _source(audio_id: str = "result_control_a_audio"):
    return framework.VoiceInputAudioSource.from_opaque_id(
        audio_id,
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=250),
        language="ja-JP",
    )


def _context():
    return {
        "session_id": framework.SessionId.new(),
        "turn_id": framework.TurnId.new(),
        "generation_id": framework.GenerationId.new(),
    }


class _ResultAdapter:
    def __init__(self, result) -> None:
        self.result = result

    def transcribe(self, *, audio_source, request):
        return self.result


class _BlockingAdapter:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def transcribe(self, *, audio_source, request):
        self.started.set()
        if not self.release.wait(timeout=5.0):
            raise TimeoutError("test adapter release timed out")
        return framework.VoiceInputResult.completed("late transcript")


class VoiceInputResultCompatibilityControlATests(unittest.TestCase):
    def test_legacy_constructor_and_factories_remain_uncorrelated(self) -> None:
        direct = framework.VoiceInputResult(
            framework.VoiceInputOutcome.COMPLETED,
            "legacy text",
        )
        results = (
            direct,
            framework.VoiceInputResult.completed("completed"),
            framework.VoiceInputResult.no_input(),
            framework.VoiceInputResult.interrupted(),
            framework.VoiceInputResult.unavailable(),
            framework.VoiceInputResult.failed(),
            framework.VoiceInputResult.closed(),
        )

        self.assertEqual(direct.text, "legacy text")
        for result in results:
            self.assertIsNone(result.session_id)
            self.assertIsNone(result.turn_id)
            self.assertIsNone(result.generation_id)
        self.assertEqual(
            tuple(item.name for item in fields(framework.VoiceInputResult))[-3:],
            ("session_id", "turn_id", "generation_id"),
        )

    def test_all_factories_accept_one_typed_correlation_context(self) -> None:
        context = _context()
        results = (
            framework.VoiceInputResult.completed("completed", **context),
            framework.VoiceInputResult.no_input(**context),
            framework.VoiceInputResult.interrupted(**context),
            framework.VoiceInputResult.unavailable(**context),
            framework.VoiceInputResult.failed(**context),
            framework.VoiceInputResult.closed(**context),
        )

        for result in results:
            self.assertIs(result.session_id, context["session_id"])
            self.assertIs(result.turn_id, context["turn_id"])
            self.assertIs(result.generation_id, context["generation_id"])

    def test_serialized_ids_normalize_and_invalid_context_is_rejected(self) -> None:
        context = _context()
        normalized = framework.VoiceInputResult.completed(
            "normalized",
            session_id=str(context["session_id"]),
            turn_id=str(context["turn_id"]),
            generation_id=str(context["generation_id"]),
        )

        self.assertIsInstance(normalized.session_id, framework.SessionId)
        self.assertIsInstance(normalized.turn_id, framework.TurnId)
        self.assertIsInstance(normalized.generation_id, framework.GenerationId)
        legacy = framework.VoiceInputResult.completed(
            "legacy",
            session_id="legacy-session",
            turn_id="legacy-turn",
        )
        self.assertEqual(legacy.session_id, "legacy-session")
        self.assertEqual(legacy.turn_id, "legacy-turn")
        with self.assertRaises(ValueError):
            framework.VoiceInputResult.completed(
                "missing session",
                turn_id=context["turn_id"],
            )
        with self.assertRaises(ValueError):
            framework.VoiceInputResult.completed(
                "missing turn",
                session_id=context["session_id"],
                generation_id=context["generation_id"],
            )
        with self.assertRaises(ValueError):
            framework.VoiceInputResult.completed(
                "wrong kind",
                session_id=context["turn_id"],
            )

    def test_completed_result_matches_canonical_event_context(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        result = session.transcribe_audio_result(_source())

        self.assertTrue(result.is_completed)
        self.assertEqual(result.session_id, session.session_id)
        self.assertEqual(result.turn_id, events[-1].turn_id)
        self.assertEqual(result.generation_id, events[-1].generation_id)
        self.assertTrue(all(event.session_id == result.session_id for event in events))
        self.assertTrue(all(event.turn_id == result.turn_id for event in events))
        self.assertTrue(
            all(event.generation_id == result.generation_id for event in events)
        )

    def test_noncompleted_adapter_result_gets_session_owned_context(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)
        adapter = _ResultAdapter(
            framework.VoiceInputResult.unavailable(
                safe_message="Unavailable in provider-free test."
            )
        )

        result = session.transcribe_audio_result(_source(), adapter=adapter)

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.UNAVAILABLE)
        self.assertEqual(result.session_id, session.session_id)
        self.assertEqual(result.turn_id, events[-1].turn_id)
        self.assertEqual(result.generation_id, events[-1].generation_id)
        self.assertEqual(events[-1].type, framework.RealtimeEventType.VOICE_INPUT_FAILED)

    def test_session_overrides_adapter_supplied_correlation(self) -> None:
        supplied = _context()
        adapter = _ResultAdapter(
            framework.VoiceInputResult.completed(
                "adapter transcript",
                **supplied,
            )
        )
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)

        result = session.transcribe_audio_result(_source(), adapter=adapter)

        self.assertNotEqual(result.session_id, supplied["session_id"])
        self.assertNotEqual(result.turn_id, supplied["turn_id"])
        self.assertNotEqual(result.generation_id, supplied["generation_id"])
        self.assertEqual(result.session_id, session.session_id)
        self.assertEqual(result.turn_id, events[-1].turn_id)
        self.assertEqual(result.generation_id, events[-1].generation_id)

    def test_abort_late_result_keeps_retired_event_context(self) -> None:
        session = framework.create_voice_input_session()
        events = []
        session.on_realtime_event(events.append)
        adapter = _BlockingAdapter()
        output = {}

        def target() -> None:
            output["result"] = session.transcribe_audio_result(
                _source(),
                adapter=adapter,
            )

        thread = Thread(target=target, daemon=True)
        thread.start()
        self.assertTrue(adapter.started.wait(timeout=5.0))
        self.assertTrue(session.abort_input())
        adapter.release.set()
        thread.join(timeout=5.0)

        self.assertFalse(thread.is_alive())
        result = output["result"]
        stale = next(
            event
            for event in events
            if event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED
        )
        self.assertEqual(result.outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertEqual(result.session_id, stale.session_id)
        self.assertEqual(result.turn_id, stale.turn_id)
        self.assertEqual(result.generation_id, stale.generation_id)

    def test_reentrant_preflight_abort_returns_correlated_interruption(self) -> None:
        session = framework.create_voice_input_session()
        events = []

        def callback(event) -> None:
            events.append(event)
            if event.type is framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT:
                self.assertTrue(session.abort_input())

        session.on_realtime_event(callback)
        result = session.transcribe_audio_result(_source())

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertEqual(result.session_id, events[0].session_id)
        self.assertEqual(result.turn_id, events[0].turn_id)
        self.assertEqual(result.generation_id, events[0].generation_id)
        self.assertNotIn(
            framework.RealtimeEventType.TRANSCRIPT_FINAL,
            [event.type for event in events],
        )


if __name__ == "__main__":
    unittest.main()
