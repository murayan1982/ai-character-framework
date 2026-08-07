from __future__ import annotations

import unittest

import framework
from framework.facade import TextChatSession, TextChatSessionInfo
from framework.output_control import (
    InterruptOutcome,
    InterruptReason,
    InterruptRequest,
    InterruptScope,
)
from framework.realtime import RealtimeEventType, RealtimeState
from framework.realtime_event_payloads import InterruptEventPayload
from llm.base import BaseLLM


class _FakeLLM(BaseLLM):
    def __init__(self, chunks: tuple[str, ...] = ("one", "two")) -> None:
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
    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def ask_stream(self, text: str):
        del text
        yield "partial", []
        raise RuntimeError("PRIVATE_CONTROL_C_PROVIDER_DETAIL")


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


class TextChatCompatibilityControlCTests(unittest.TestCase):
    def test_idle_interrupt_result_is_no_active_turn_and_emits_canonical_request(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)

        result = session.interrupt_result()

        self.assertIs(result.outcome, InterruptOutcome.NO_ACTIVE_TURN)
        self.assertIsNone(result.turn_id)
        self.assertFalse(result.provider_cancel_supported)
        self.assertFalse(result.queue_flush_supported)
        self.assertEqual([event.type for event in canonical], [RealtimeEventType.INTERRUPT_REQUESTED])
        event = canonical[0]
        self.assertIs(event.state, RealtimeState.IDLE)
        self.assertIsNone(event.turn_id)
        self.assertIsNone(event.generation_id)
        self.assertIsInstance(event.payload, InterruptEventPayload)
        self.assertIs(event.payload.outcome, InterruptOutcome.NO_ACTIVE_TURN)
        self.assertEqual([(event.type, event.data) for event in legacy], [("interrupt_requested", {})])

    def test_active_interrupt_result_is_accepted_and_correlated(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)
        stream = session.ask_stream("question")
        self.assertEqual(next(stream), "one")
        turn_id = canonical[0].turn_id
        generation_id = canonical[0].generation_id

        result = session.interrupt_result()

        self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
        self.assertEqual(result.turn_id, turn_id)
        self.assertFalse(result.provider_cancel_supported)
        self.assertFalse(result.queue_flush_supported)
        requested = canonical[-1]
        self.assertIs(requested.type, RealtimeEventType.INTERRUPT_REQUESTED)
        self.assertEqual(requested.turn_id, turn_id)
        self.assertEqual(requested.generation_id, generation_id)
        self.assertIs(requested.payload.outcome, InterruptOutcome.ACCEPTED)
        self.assertEqual([(event.type, event.data) for event in legacy][-1], ("interrupt_requested", {}))

    def test_active_typed_interrupt_suppresses_future_delivery_and_finishes_interrupted(self) -> None:
        session = TextChatSession(_FakeLLM(("one", "two", "three")), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        stream = session.ask_stream("question")
        self.assertEqual(next(stream), "one")

        self.assertTrue(session.interrupt_result().accepted)
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
        terminals = [event for event in canonical if event.terminal]
        self.assertEqual(len(terminals), 1)
        self.assertIs(terminals[0].type, RealtimeEventType.TURN_INTERRUPTED)

    def test_closed_interrupt_result_is_already_closed_and_emits_safe_request_event(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)
        session.close()

        result = session.interrupt_result()

        self.assertIs(result.outcome, InterruptOutcome.ALREADY_CLOSED)
        self.assertFalse(result.provider_cancel_supported)
        self.assertFalse(result.queue_flush_supported)
        event = canonical[0]
        self.assertIs(event.type, RealtimeEventType.INTERRUPT_REQUESTED)
        self.assertIs(event.state, RealtimeState.CLOSED)
        self.assertIs(event.payload.outcome, InterruptOutcome.ALREADY_CLOSED)
        self.assertNotIn("PRIVATE", repr(result))
        self.assertEqual([(item.type, item.data) for item in legacy], [("interrupt_requested", {})])

    def test_legacy_interrupt_idle_remains_true_with_no_active_typed_outcome(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)

        self.assertIs(session.interrupt(), True)

        self.assertIs(canonical[0].payload.outcome, InterruptOutcome.NO_ACTIVE_TURN)
        self.assertEqual([(event.type, event.data) for event in legacy], [("interrupt_requested", {})])

    def test_legacy_interrupt_active_remains_true_and_uses_accepted_typed_bridge(self) -> None:
        session = TextChatSession(_FakeLLM(("one", "two")), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        stream = session.ask_stream("question")
        self.assertEqual(next(stream), "one")

        self.assertIs(session.interrupt(), True)
        self.assertIs(canonical[-1].type, RealtimeEventType.INTERRUPT_REQUESTED)
        self.assertIs(canonical[-1].payload.outcome, InterruptOutcome.ACCEPTED)
        self.assertEqual(list(stream), [])
        self.assertIs(canonical[-1].type, RealtimeEventType.TURN_INTERRUPTED)

    def test_legacy_interrupt_closed_remains_true_while_typed_outcome_is_closed(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)
        session.close()

        self.assertIs(session.interrupt(), True)

        self.assertIs(canonical[0].payload.outcome, InterruptOutcome.ALREADY_CLOSED)
        self.assertEqual([(event.type, event.data) for event in legacy], [("interrupt_requested", {})])

    def test_custom_interrupt_request_preserves_scope_reason_and_active_turn_identity(self) -> None:
        session = TextChatSession(_FakeLLM(("one", "two")), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        stream = session.ask_stream("question")
        next(stream)
        turn_id = canonical[0].turn_id
        request = InterruptRequest(
            scope=InterruptScope.ALL,
            reason=InterruptReason.USER_CANCEL,
            cancel_llm_stream=True,
            public_metadata={"source": "test"},
        )

        result = session.interrupt_result(request)

        self.assertIs(result.outcome, InterruptOutcome.ACCEPTED)
        self.assertIs(result.scope, InterruptScope.ALL)
        self.assertIs(result.reason, InterruptReason.USER_CANCEL)
        self.assertEqual(result.turn_id, turn_id)
        self.assertFalse(result.provider_cancel_supported)
        self.assertFalse(result.queue_flush_supported)
        payload = canonical[-1].payload
        self.assertIs(payload.scope, InterruptScope.ALL)
        self.assertIs(payload.outcome, InterruptOutcome.ACCEPTED)
        self.assertEqual(payload.reason, InterruptReason.USER_CANCEL.value)
        self.assertEqual(list(stream), [])

    def test_interrupt_result_rejects_non_request_argument(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        with self.assertRaisesRegex(TypeError, "InterruptRequest"):
            session.interrupt_result(object())  # type: ignore[arg-type]

    def test_interrupt_requested_reuses_existing_v5_event_adapter(self) -> None:
        session = TextChatSession(_FakeLLM(), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        session.interrupt_result()
        event = canonical[0]

        self.assertIs(event.type, RealtimeEventType.INTERRUPT_REQUESTED)
        self.assertIs(event.to_v5(), event)
        v5 = event.as_v5_dict()
        self.assertIsNotNone(v5)
        assert v5 is not None
        self.assertEqual(v5["type"], RealtimeEventType.INTERRUPT_REQUESTED.value)
        self.assertEqual(v5["session_id"], str(session.session_id))
        self.assertNotIn("payload", v5)
        self.assertNotIn("generation_id", v5)

    def test_existing_response_v5_projection_is_reused_without_duplicate_mapping(self) -> None:
        session = TextChatSession(_FakeLLM(("one",)), _info())
        canonical = []
        session.on_realtime_event(canonical.append)
        list(session.ask_stream("question"))

        started = next(event for event in canonical if event.type is RealtimeEventType.RESPONSE_STARTED)
        delta = next(event for event in canonical if event.type is RealtimeEventType.RESPONSE_DELTA)
        completed = next(event for event in canonical if event.type is RealtimeEventType.RESPONSE_COMPLETED)

        self.assertIs(started.to_v5().type, RealtimeEventType.TEXT_CHAT_STARTED)
        self.assertIsNone(delta.to_v5())
        self.assertIs(completed.to_v5().type, RealtimeEventType.TEXT_CHAT_COMPLETED)

    def test_sequence_remains_session_local_monotonic_across_interrupt_and_turn_events(self) -> None:
        session = TextChatSession(_FakeLLM(("one", "two")), _info())
        canonical = []
        session.on_realtime_event(canonical.append)

        session.interrupt_result()
        stream = session.ask_stream("question")
        next(stream)
        session.interrupt_result()
        list(stream)

        self.assertEqual(
            [int(event.sequence) for event in canonical],
            list(range(1, len(canonical) + 1)),
        )
        self.assertTrue(all(event.session_id == session.session_id for event in canonical))

    def test_raw_provider_exception_remains_absent_from_canonical_and_legacy_events(self) -> None:
        session = TextChatSession(_FailingLLM(), _info())
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)

        with self.assertRaisesRegex(RuntimeError, "PRIVATE_CONTROL_C_PROVIDER_DETAIL"):
            list(session.ask_stream("question"))

        public_surface = repr(canonical) + repr(legacy)
        self.assertNotIn("PRIVATE_CONTROL_C_PROVIDER_DETAIL", public_surface)
        self.assertIs(canonical[-1].type, RealtimeEventType.TURN_FAILED)
        self.assertEqual(legacy[-1].type, "error")

    def test_public_surface_and_info_shape_remain_unchanged(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(TextChatSessionInfo.__dataclass_fields__["api_version"].default, "4.0")
        self.assertTrue(hasattr(TextChatSession, "interrupt_result"))
        self.assertIn("InterruptRequest", framework.__all__)
        self.assertIn("InterruptResult", framework.__all__)


if __name__ == "__main__":
    unittest.main()
