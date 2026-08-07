from __future__ import annotations

import threading
import unittest

from framework.identity import GenerationId, SessionId, TurnId
from framework.realtime_capabilities import TextGenerationCapability
from framework.realtime_stage import RealtimeStageContext
from framework.realtime_text_generation import (
    ProviderNeutralTextGenerationStream,
    TextGenerationCancelReason,
    TextGenerationCompletedTurn,
    TextGenerationHistorySink,
    TextGenerationStream,
    TextGenerationStreamCloseOutcome,
)


class _Source:
    def __init__(self, items, *, fail_after: int | None = None, close_error=False):
        self._items = list(items)
        self._index = 0
        self._fail_after = fail_after
        self._close_error = close_error
        self.close_calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._fail_after is not None and self._index >= self._fail_after:
            raise RuntimeError("private provider detail")
        if self._index >= len(self._items):
            raise StopIteration
        item = self._items[self._index]
        self._index += 1
        return item

    def close(self):
        self.close_calls += 1
        if self._close_error:
            raise RuntimeError("private close detail")


class _BlockingSecondSource:
    def __init__(self):
        self._index = 0
        self.entered = threading.Event()
        self.release = threading.Event()
        self.close_calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index == 0:
            self._index = 1
            return ("first", [])
        if self._index == 1:
            self._index = 2
            self.entered.set()
            if not self.release.wait(timeout=2.0):
                raise RuntimeError("test release timeout")
            return ("second", [])
        raise StopIteration

    def close(self):
        self.close_calls += 1


class _Sink:
    def __init__(self, *, fail=False):
        self.turns: list[TextGenerationCompletedTurn] = []
        self.fail = fail

    def commit_completed_turn(self, turn: TextGenerationCompletedTurn) -> None:
        if self.fail:
            raise RuntimeError("private history detail")
        self.turns.append(turn)


class TextGenerationStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
        self.capability = TextGenerationCapability(
            streaming_supported=True,
            cooperative_cancel_supported=True,
            provider_hard_cancel_supported=False,
        )

    def _stream(self, source, *, sink=None):
        return ProviderNeutralTextGenerationStream(
            context=self.context,
            capability=self.capability,
            source=source,
            user_input="secret user text",
            history_sink=sink,
        )

    def test_reference_stream_matches_protocols(self) -> None:
        stream = self._stream(_Source([]), sink=_Sink())
        self.assertIsInstance(stream, TextGenerationStream)
        self.assertIsInstance(_Sink(), TextGenerationHistorySink)

    def test_normal_completion_correlates_monotonic_deltas(self) -> None:
        source = _Source([("a", []), ("b", ["happy"])])
        stream = self._stream(source)
        deltas = list(stream)
        self.assertEqual([delta.delta_index for delta in deltas], [0, 1])
        self.assertTrue(all(delta.context == self.context for delta in deltas))
        self.assertEqual(deltas[1].emotion_tags, ("happy",))
        self.assertTrue(stream.completed)
        self.assertEqual(stream.delivered_delta_count, 2)
        self.assertEqual(source.close_calls, 1)

    def test_normal_completion_commits_one_atomic_history_pair(self) -> None:
        sink = _Sink()
        stream = self._stream(_Source([("hello ", []), ("world", [])]), sink=sink)
        list(stream)
        self.assertTrue(stream.history_committed)
        self.assertEqual(len(sink.turns), 1)
        turn = sink.turns[0]
        self.assertEqual(turn.context, self.context)
        self.assertEqual(turn.user_input, "secret user text")
        self.assertEqual(turn.assistant_output, "hello world")
        self.assertNotIn("secret user text", repr(turn))
        self.assertNotIn("hello world", repr(turn))

    def test_completed_stream_does_not_commit_twice(self) -> None:
        sink = _Sink()
        stream = self._stream(_Source([("done", [])]), sink=sink)
        list(stream)
        self.assertEqual(list(stream), [])
        self.assertEqual(len(sink.turns), 1)

    def test_cancel_after_first_delta_suppresses_all_future_delivery(self) -> None:
        sink = _Sink()
        source = _Source([("first", []), ("second", []), ("third", [])])
        stream = self._stream(source, sink=sink)
        first = next(stream)
        self.assertEqual(first.text, "first")
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.INTERRUPT))
        self.assertEqual(list(stream), [])
        self.assertEqual(stream.delivered_delta_count, 1)
        self.assertEqual(source.close_calls, 1)
        self.assertFalse(stream.history_committed)
        self.assertEqual(sink.turns, [])

    def test_cancel_while_source_pull_is_in_flight_suppresses_returned_delta(self) -> None:
        source = _BlockingSecondSource()
        stream = self._stream(source)
        self.assertEqual(next(stream).text, "first")
        outcome: list[str] = []

        def pull_second() -> None:
            try:
                next(stream)
            except StopIteration:
                outcome.append("stopped")
            else:
                outcome.append("delivered")

        thread = threading.Thread(target=pull_second)
        thread.start()
        self.assertTrue(source.entered.wait(timeout=2.0))
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.INTERRUPT))
        source.release.set()
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, ["stopped"])
        self.assertEqual(stream.delivered_delta_count, 1)
        self.assertEqual(source.close_calls, 1)

    def test_cancel_before_first_delta_suppresses_delivery_and_cleans_up(self) -> None:
        source = _Source([("never", [])])
        stream = self._stream(source, sink=_Sink())
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.HOST_REQUEST))
        self.assertEqual(list(stream), [])
        self.assertEqual(stream.delivered_delta_count, 0)
        self.assertEqual(source.close_calls, 1)

    def test_close_before_completion_never_commits_history(self) -> None:
        sink = _Sink()
        source = _Source([("partial", []), ("later", [])])
        stream = self._stream(source, sink=sink)
        next(stream)
        result = stream.close()
        self.assertIs(result.outcome, TextGenerationStreamCloseOutcome.CLOSED)
        self.assertEqual(list(stream), [])
        self.assertFalse(stream.history_committed)
        self.assertEqual(sink.turns, [])
        self.assertEqual(source.close_calls, 1)

    def test_close_is_typed_idempotent_and_source_closes_once(self) -> None:
        source = _Source([("unused", [])])
        stream = self._stream(source)
        first = stream.close()
        second = stream.close()
        self.assertIs(first.outcome, TextGenerationStreamCloseOutcome.CLOSED)
        self.assertIs(second.outcome, TextGenerationStreamCloseOutcome.ALREADY_CLOSED)
        self.assertEqual(source.close_calls, 1)

    def test_dispose_is_close_compatibility_alias(self) -> None:
        source = _Source([])
        stream = self._stream(source)
        first = stream.dispose()
        second = stream.dispose()
        self.assertIs(first.outcome, TextGenerationStreamCloseOutcome.CLOSED)
        self.assertIs(second.outcome, TextGenerationStreamCloseOutcome.ALREADY_CLOSED)
        self.assertEqual(source.close_calls, 1)

    def test_cleanup_failure_returns_public_safe_typed_result(self) -> None:
        stream = self._stream(_Source([], close_error=True))
        result = stream.close()
        self.assertIs(result.outcome, TextGenerationStreamCloseOutcome.FAILED)
        self.assertEqual(result.safe_message, "Text-generation stream cleanup failed.")
        self.assertNotIn("private close detail", repr(result))

    def test_source_failure_never_commits_history_and_cleans_up(self) -> None:
        sink = _Sink()
        source = _Source([("partial", [])], fail_after=1)
        stream = self._stream(source, sink=sink)
        self.assertEqual(next(stream).text, "partial")
        with self.assertRaisesRegex(RuntimeError, "private provider detail"):
            next(stream)
        self.assertEqual(source.close_calls, 1)
        self.assertFalse(stream.history_committed)
        self.assertEqual(sink.turns, [])

    def test_invalid_source_delta_closes_without_history_commit(self) -> None:
        sink = _Sink()
        source = _Source([("ok", []), (123, [])])
        stream = self._stream(source, sink=sink)
        next(stream)
        with self.assertRaises(TypeError):
            next(stream)
        self.assertEqual(source.close_calls, 1)
        self.assertEqual(sink.turns, [])

    def test_history_sink_failure_is_safe_and_not_retried(self) -> None:
        sink = _Sink(fail=True)
        stream = self._stream(_Source([("done", [])]), sink=sink)
        self.assertEqual(next(stream).text, "done")
        with self.assertRaisesRegex(RuntimeError, "Text-generation history commit failed") as ctx:
            next(stream)
        self.assertNotIn("private history detail", str(ctx.exception))
        self.assertTrue(stream.closed)
        self.assertFalse(stream.history_committed)
        self.assertEqual(list(stream), [])

    def test_request_cancel_after_close_is_rejected(self) -> None:
        stream = self._stream(_Source([]))
        stream.close()
        self.assertFalse(stream.request_cancel(TextGenerationCancelReason.RESET))
        self.assertFalse(stream.cancellation_token.cancel_requested)

    def test_capability_hard_cancel_is_not_overclaimed(self) -> None:
        stream = self._stream(_Source([]))
        self.assertFalse(stream.capability.provider_hard_cancel_supported)
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.TURN_CANCELLED))
        self.assertFalse(stream.capability.provider_hard_cancel_supported)

    def test_natural_completion_then_close_is_already_closed(self) -> None:
        source = _Source([("done", [])])
        stream = self._stream(source)
        list(stream)
        result = stream.close()
        self.assertIs(result.outcome, TextGenerationStreamCloseOutcome.ALREADY_CLOSED)
        self.assertTrue(stream.completed)
        self.assertEqual(source.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
