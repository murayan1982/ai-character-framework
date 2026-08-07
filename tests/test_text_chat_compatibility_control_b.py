from __future__ import annotations

import unittest

import framework
from framework.facade import TextChatSession, TextChatSessionInfo
from framework.lifecycle import RealtimePhase, TurnOutcome
from framework.realtime import RealtimeErrorCode, RealtimeEventType, RealtimeState
from framework.realtime_event_payloads import LifecycleEventPayload, ResponseEventPayload
from llm.base import BaseLLM


class _FakeLLM(BaseLLM):
    def __init__(self, chunks: tuple[str, ...] = ("hello", " world")) -> None:
        self._chunks = chunks

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


class _FailingLLM(BaseLLM):
    def __init__(self, error: Exception) -> None:
        self.error = error

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def ask_stream(self, text: str):
        del text
        yield "partial", []
        raise self.error


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


class TextChatCompatibilityControlBTests(unittest.TestCase):
    def test_normal_stream_emits_exact_canonical_event_order(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        events = []
        session.on_realtime_event(events.append)

        self.assertEqual(list(session.ask_stream("question")), ["hello", " world"])
        self.assertEqual(
            [event.type for event in events],
            [
                RealtimeEventType.TURN_STARTED,
                RealtimeEventType.RESPONSE_STARTED,
                RealtimeEventType.RESPONSE_DELTA,
                RealtimeEventType.RESPONSE_DELTA,
                RealtimeEventType.RESPONSE_COMPLETED,
                RealtimeEventType.TURN_COMPLETED,
            ],
        )

    def test_normal_stream_correlates_one_session_turn_and_generation(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        events = []
        session.on_realtime_event(events.append)
        list(session.ask_stream("question"))

        self.assertTrue(all(event.session_id == session.session_id for event in events))
        turn_ids = {event.turn_id for event in events}
        generation_ids = {event.generation_id for event in events}
        self.assertEqual(len(turn_ids), 1)
        self.assertEqual(len(generation_ids), 1)
        self.assertNotIn(None, turn_ids)
        self.assertNotIn(None, generation_ids)

    def test_canonical_sequence_is_monotonic_across_multiple_turns(self) -> None:
        session = TextChatSession(_FakeLLM(("one",)), _info())
        events = []
        session.on_realtime_event(events.append)
        list(session.ask_stream("first"))
        first_turn = events[0].turn_id
        first_generation = events[0].generation_id
        list(session.ask_stream("second"))

        self.assertEqual([int(event.sequence) for event in events], list(range(1, 11)))
        self.assertNotEqual(events[5].turn_id, first_turn)
        self.assertNotEqual(events[5].generation_id, first_generation)
        self.assertTrue(all(event.session_id == session.session_id for event in events))

    def test_response_payloads_use_delivered_non_empty_delta_indexes(self) -> None:
        session = TextChatSession(_FakeLLM(("", "a", "", "b")), _info())
        events = []
        session.on_realtime_event(events.append)
        self.assertEqual(list(session.ask_stream("question")), ["a", "b"])

        response_events = [
            event for event in events
            if event.type in {
                RealtimeEventType.RESPONSE_STARTED,
                RealtimeEventType.RESPONSE_DELTA,
                RealtimeEventType.RESPONSE_COMPLETED,
            }
        ]
        self.assertEqual(len(response_events), 4)
        started = response_events[0].payload
        first = response_events[1].payload
        second = response_events[2].payload
        completed = response_events[3].payload
        self.assertEqual(started, ResponseEventPayload(text="", is_final=False))
        self.assertEqual(first, ResponseEventPayload(text="a", delta_index=0, is_final=False))
        self.assertEqual(second, ResponseEventPayload(text="b", delta_index=1, is_final=False))
        self.assertEqual(completed, ResponseEventPayload(text="ab", is_final=True))

    def test_turn_started_and_response_events_use_thinking_phase(self) -> None:
        session = TextChatSession(_FakeLLM(("one",)), _info())
        events = []
        session.on_realtime_event(events.append)
        list(session.ask_stream("question"))

        for event in events[:-1]:
            self.assertIs(event.state, RealtimeState.THINKING)
            self.assertIs(event.phase, RealtimePhase.THINKING)
        self.assertIs(events[-1].state, RealtimeState.COMPLETED)
        self.assertIsNone(events[-1].phase)

    def test_normal_turn_terminal_is_exactly_one_completed_event(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        events = []
        session.on_realtime_event(events.append)
        list(session.ask_stream("question"))

        terminals = [event for event in events if event.terminal]
        self.assertEqual(len(terminals), 1)
        terminal = terminals[0]
        self.assertIs(terminal.type, RealtimeEventType.TURN_COMPLETED)
        self.assertIsInstance(terminal.payload, LifecycleEventPayload)
        self.assertIs(terminal.payload.outcome, TurnOutcome.COMPLETED)

    def test_ask_uses_exactly_one_turn_context_and_returns_legacy_string(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        events = []
        session.on_realtime_event(events.append)

        self.assertEqual(session.ask("question"), "hello world")
        self.assertEqual(len({event.turn_id for event in events}), 1)
        self.assertEqual(len({event.generation_id for event in events}), 1)

    def test_legacy_normal_events_and_states_remain_exact(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        legacy = []
        states = []
        session.on_event(legacy.append)
        session.on_state_change(states.append)
        list(session.ask_stream("question"))

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

    def test_turn_lifecycle_events_are_not_projected_as_new_legacy_types(self) -> None:
        session = TextChatSession(_FakeLLM(("one",)), _info())
        legacy = []
        session.on_event(legacy.append)
        list(session.ask_stream("question"))
        self.assertEqual(
            [event.type for event in legacy],
            ["response_started", "response_chunk", "response_completed"],
        )

    def test_interrupt_emits_turn_interrupted_without_response_completed(self) -> None:
        session = TextChatSession(_FakeLLM(("one", "two")), _info())
        canonical = []
        legacy = []
        states = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)
        session.on_state_change(states.append)

        stream = session.ask_stream("question")
        self.assertEqual(next(stream), "one")
        self.assertIs(session.interrupt(), True)
        self.assertEqual(list(stream), [])

        self.assertEqual(
            [event.type for event in canonical],
            [
                RealtimeEventType.TURN_STARTED,
                RealtimeEventType.RESPONSE_STARTED,
                RealtimeEventType.RESPONSE_DELTA,
                RealtimeEventType.INTERRUPT_REQUESTED,
                RealtimeEventType.TURN_INTERRUPTED,
            ],
        )
        self.assertNotIn("response_completed", [event.type for event in legacy])
        self.assertEqual(
            [(event.old_state, event.new_state) for event in states],
            [
                ("idle", "responding"),
                ("responding", "interrupted"),
                ("interrupted", "idle"),
            ],
        )

    def test_interrupted_terminal_is_exactly_once_and_correlated(self) -> None:
        session = TextChatSession(_FakeLLM(("one", "two")), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        stream = session.ask_stream("question")
        next(stream)
        session.interrupt()
        list(stream)

        terminals = [event for event in canonical if event.terminal]
        self.assertEqual(len(terminals), 1)
        terminal = terminals[0]
        self.assertIs(terminal.type, RealtimeEventType.TURN_INTERRUPTED)
        self.assertIs(terminal.state, RealtimeState.INTERRUPTED)
        self.assertIs(terminal.public_error_code, RealtimeErrorCode.INTERRUPTED)
        self.assertIs(terminal.payload.outcome, TurnOutcome.INTERRUPTED)
        self.assertEqual(terminal.turn_id, canonical[0].turn_id)
        self.assertEqual(terminal.generation_id, canonical[0].generation_id)

    def test_interrupt_request_projects_to_legacy_event_without_shape_drift(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)
        self.assertIs(session.interrupt(), True)
        self.assertEqual([event.type for event in canonical], [RealtimeEventType.INTERRUPT_REQUESTED])
        self.assertEqual([(event.type, event.data) for event in legacy], [("interrupt_requested", {})])

    def test_provider_failure_emits_one_safe_turn_failed_and_reraises_original(self) -> None:
        error = RuntimeError("PRIVATE_PROVIDER_DETAIL_123")
        session = TextChatSession(_FailingLLM(error), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        stream = session.ask_stream("question")
        self.assertEqual(next(stream), "partial")
        with self.assertRaises(RuntimeError) as caught:
            next(stream)
        self.assertIs(caught.exception, error)

        terminals = [event for event in canonical if event.terminal]
        self.assertEqual(len(terminals), 1)
        failed = terminals[0]
        self.assertIs(failed.type, RealtimeEventType.TURN_FAILED)
        self.assertIs(failed.state, RealtimeState.FAILED)
        self.assertIs(failed.public_error_code, RealtimeErrorCode.PROVIDER_ERROR)
        self.assertIs(failed.payload.outcome, TurnOutcome.FAILED)
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL_123", repr(failed))
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL_123", failed.safe_message)
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL_123", repr(dict(failed.public_metadata)))

    def test_legacy_failure_event_shape_remains_safe_and_exception_is_reraised(self) -> None:
        error = RuntimeError("PRIVATE_PROVIDER_DETAIL_456")
        session = TextChatSession(_FailingLLM(error), _info())
        legacy = []
        states = []
        session.on_event(legacy.append)
        session.on_state_change(states.append)
        stream = session.ask_stream("question")
        self.assertEqual(next(stream), "partial")
        with self.assertRaises(RuntimeError) as caught:
            next(stream)
        self.assertIs(caught.exception, error)

        self.assertEqual([event.type for event in legacy], ["response_started", "response_chunk", "error"])
        error_data = legacy[-1].data
        self.assertEqual(set(error_data), {"public_error_code", "safe_message", "retryable", "public_metadata"})
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL_456", repr(error_data))
        self.assertEqual(
            [(event.old_state, event.new_state) for event in states],
            [("idle", "responding"), ("responding", "error"), ("error", "idle")],
        )

    def test_failure_has_no_response_completed_or_turn_completed(self) -> None:
        session = TextChatSession(_FailingLLM(RuntimeError("failure")), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        with self.assertRaises(RuntimeError):
            list(session.ask_stream("question"))
        types = [event.type for event in canonical]
        self.assertNotIn(RealtimeEventType.RESPONSE_COMPLETED, types)
        self.assertNotIn(RealtimeEventType.TURN_COMPLETED, types)
        self.assertEqual(types[-1], RealtimeEventType.TURN_FAILED)

    def test_active_context_matches_current_turn_and_is_cleared_after_completion(self) -> None:
        session = TextChatSession(_FakeLLM(("one", "two")), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        stream = session.ask_stream("question")
        self.assertEqual(next(stream), "one")
        active = session._active_realtime_turn_context
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.turn_id, canonical[0].turn_id)
        self.assertEqual(active.generation_id, canonical[0].generation_id)
        list(stream)
        self.assertIsNone(session._active_realtime_turn_context)

    def test_active_context_is_cleared_after_interrupt_and_failure(self) -> None:
        interrupted = TextChatSession(_FakeLLM(("one", "two")), _info())
        stream = interrupted.ask_stream("question")
        next(stream)
        interrupted.interrupt()
        list(stream)
        self.assertIsNone(interrupted._active_realtime_turn_context)

        failed = TextChatSession(_FailingLLM(RuntimeError("failure")), _info())
        with self.assertRaises(RuntimeError):
            list(failed.ask_stream("question"))
        self.assertIsNone(failed._active_realtime_turn_context)

    def test_root_public_and_text_chat_info_shape_remain_unchanged(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(TextChatSessionInfo.__dataclass_fields__["api_version"].default, "4.0")
        self.assertTrue(hasattr(TextChatSession, "interrupt_result"))


if __name__ == "__main__":
    unittest.main()
