from __future__ import annotations

import unittest

import framework
from framework.facade import TextChatSession, TextChatSessionInfo
from framework.identity import EventSequence, GenerationId, SessionId, TurnId
from framework.realtime import RealtimeEvent, RealtimeEventType, RealtimeState
from llm.base import BaseLLM


class _FakeLLM(BaseLLM):
    def __init__(self, chunks: tuple[str, ...] = ("hello", " world")) -> None:
        self._chunks = chunks
        self.reset_calls = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def ask_stream(self, text: str):
        del text
        for chunk in self._chunks:
            yield chunk, []

    def reset_session(self) -> None:
        self.reset_calls += 1


def _info() -> TextChatSessionInfo:
    return TextChatSessionInfo(
        preset="text_chat",
        character_name="test",
        input_language_code="ja",
        output_language_code="ja",
        llm_mode="fake",
        provider="fake",
        model="fake-model",
        route_name=None,
    )


class TextChatCompatibilityControlATests(unittest.TestCase):
    def test_session_id_is_stable_framework_identity(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        first = session.session_id
        second = session.session_id
        self.assertIsInstance(first, SessionId)
        self.assertIs(first, second)
        self.assertEqual(first, second)

    def test_distinct_text_sessions_receive_distinct_session_ids(self) -> None:
        first = TextChatSession(_FakeLLM(), _info())
        second = TextChatSession(_FakeLLM(), _info())
        self.assertNotEqual(first.session_id, second.session_id)

    def test_text_chat_session_info_shape_and_api_version_remain_unchanged(self) -> None:
        self.assertEqual(
            tuple(TextChatSessionInfo.__dataclass_fields__),
            (
                "preset",
                "character_name",
                "input_language_code",
                "output_language_code",
                "llm_mode",
                "provider",
                "model",
                "route_name",
                "api_version",
                "session_type",
                "supports_streaming",
                "supports_reset",
                "supports_interrupt",
                "supports_events",
                "supports_close",
                "supports_voice_input",
                "supports_voice_output",
                "supports_live2d",
            ),
        )
        self.assertEqual(TextChatSessionInfo.__dataclass_fields__["api_version"].default, "4.0")

    def test_internal_turn_context_correlates_session_turn_and_generation(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        context = session._new_realtime_turn_context("private input text")
        self.assertEqual(context.session_id, session.session_id)
        self.assertIsInstance(context.turn_id, TurnId)
        self.assertIsInstance(context.generation_id, GenerationId)
        self.assertEqual(context.input_text, "private input text")
        self.assertNotIn("private input text", repr(context))

    def test_internal_turn_context_allocates_new_turn_and_generation_each_time(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        first = session._new_realtime_turn_context("one")
        second = session._new_realtime_turn_context("two")
        self.assertEqual(first.session_id, second.session_id)
        self.assertNotEqual(first.turn_id, second.turn_id)
        self.assertNotEqual(first.generation_id, second.generation_id)

    def test_on_realtime_event_registers_and_returns_callback(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        events: list[RealtimeEvent] = []
        callback = events.append
        returned = session.on_realtime_event(callback)
        self.assertIs(returned, callback)
        context = session._new_realtime_turn_context("one")
        session._emit_realtime_event(
            RealtimeEventType.TURN_STARTED,
            state=RealtimeState.THINKING,
            context=context,
        )
        self.assertEqual(len(events), 1)

    def test_on_realtime_event_rejects_non_callable(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        with self.assertRaises(TypeError):
            session.on_realtime_event(None)  # type: ignore[arg-type]

    def test_canonical_event_uses_context_and_starts_sequence_at_one(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        context = session._new_realtime_turn_context("one")
        event = session._emit_realtime_event(
            RealtimeEventType.TURN_STARTED,
            state=RealtimeState.THINKING,
            context=context,
        )
        self.assertEqual(event.session_id, session.session_id)
        self.assertEqual(event.turn_id, context.turn_id)
        self.assertEqual(event.generation_id, context.generation_id)
        self.assertEqual(event.sequence, EventSequence.first())
        self.assertEqual(event.boundary, "text_chat")

    def test_canonical_event_sequence_is_session_local_and_monotonic(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        context = session._new_realtime_turn_context("one")
        first = session._emit_realtime_event(
            RealtimeEventType.TURN_STARTED,
            state=RealtimeState.THINKING,
            context=context,
        )
        second = session._emit_realtime_event(
            RealtimeEventType.RESPONSE_STARTED,
            state=RealtimeState.THINKING,
            context=context,
        )
        self.assertEqual(int(first.sequence), 1)
        self.assertEqual(int(second.sequence), 2)

        other = TextChatSession(_FakeLLM(), _info())
        other_event = other._emit_realtime_event(
            RealtimeEventType.SESSION_STARTED,
            state=RealtimeState.IDLE,
        )
        self.assertEqual(int(other_event.sequence), 1)

    def test_session_scoped_canonical_event_can_omit_turn_and_generation(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        event = session._emit_realtime_event(
            RealtimeEventType.SESSION_STARTED,
            state=RealtimeState.IDLE,
        )
        self.assertEqual(event.session_id, session.session_id)
        self.assertIsNone(event.turn_id)
        self.assertIsNone(event.generation_id)

    def test_legacy_ask_stream_behavior_remains_unchanged_after_adoption(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        legacy = []
        canonical = []
        states = []
        session.on_event(legacy.append)
        session.on_realtime_event(canonical.append)
        session.on_state_change(states.append)

        self.assertEqual(list(session.ask_stream("question")), ["hello", " world"])
        self.assertEqual(
            [(event.type, event.data) for event in legacy],
            [
                ("response_started", {"text": "question"}),
                ("response_chunk", {"chunk": "hello"}),
                ("response_chunk", {"chunk": " world"}),
                ("response_completed", {}),
            ],
        )
        self.assertEqual(
            [(event.old_state, event.new_state) for event in states],
            [("idle", "responding"), ("responding", "idle")],
        )
        self.assertEqual(
            [event.type for event in canonical],
            [
                RealtimeEventType.TURN_STARTED,
                RealtimeEventType.RESPONSE_STARTED,
                RealtimeEventType.RESPONSE_DELTA,
                RealtimeEventType.RESPONSE_DELTA,
                RealtimeEventType.RESPONSE_COMPLETED,
                RealtimeEventType.TURN_COMPLETED,
            ],
        )

    def test_legacy_interrupt_boolean_and_event_remain_unchanged(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        legacy = []
        canonical = []
        session.on_event(legacy.append)
        session.on_realtime_event(canonical.append)

        self.assertIs(session.interrupt(), True)
        self.assertEqual([(event.type, event.data) for event in legacy], [("interrupt_requested", {})])
        self.assertEqual([event.type for event in canonical], [RealtimeEventType.INTERRUPT_REQUESTED])

    def test_reset_preserves_session_id_and_legacy_behavior(self) -> None:
        llm = _FakeLLM()
        session = TextChatSession(llm, _info())
        legacy = []
        session.on_event(legacy.append)
        session_id = session.session_id

        session.reset()
        self.assertEqual(session.session_id, session_id)
        self.assertEqual(llm.reset_calls, 1)
        self.assertEqual([(event.type, event.data) for event in legacy], [("reset", {})])

    def test_root_public_surface_remains_127_names(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertNotIn("_TextChatRealtimeTurnContext", framework.__all__)
        self.assertTrue(hasattr(TextChatSession, "session_id"))
        self.assertTrue(hasattr(TextChatSession, "on_realtime_event"))


if __name__ == "__main__":
    unittest.main()
