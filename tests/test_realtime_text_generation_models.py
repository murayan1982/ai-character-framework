from __future__ import annotations

import threading
import unittest

import framework
from framework.identity import GenerationId, SessionId, TurnId
from framework.realtime_stage import RealtimeStageContext
from framework.realtime_text_generation import (
    TextGenerationCancelReason,
    TextGenerationCancellationToken,
    TextGenerationDeltaEnvelope,
    TextGenerationStreamCloseOutcome,
    TextGenerationStreamCloseResult,
)


class RealtimeTextGenerationModelTests(unittest.TestCase):
    def _context(self) -> RealtimeStageContext:
        return RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )

    def test_cancel_reason_values_are_exact(self) -> None:
        self.assertEqual(
            tuple(reason.value for reason in TextGenerationCancelReason),
            (
                "host_request",
                "interrupt",
                "turn_cancelled",
                "session_closed",
                "reset",
            ),
        )

    def test_cancellation_token_starts_uncancelled(self) -> None:
        token = TextGenerationCancellationToken()
        self.assertFalse(token.cancel_requested)
        self.assertIsNone(token.reason)

    def test_first_cancellation_request_wins(self) -> None:
        token = TextGenerationCancellationToken()
        self.assertTrue(token.request_cancel(TextGenerationCancelReason.INTERRUPT))
        self.assertFalse(token.request_cancel(TextGenerationCancelReason.RESET))
        self.assertTrue(token.cancel_requested)
        self.assertIs(token.reason, TextGenerationCancelReason.INTERRUPT)

    def test_cancellation_request_normalizes_string_reason(self) -> None:
        token = TextGenerationCancellationToken()
        self.assertTrue(token.request_cancel("session_closed"))
        self.assertIs(token.reason, TextGenerationCancelReason.SESSION_CLOSED)

    def test_cancellation_token_is_thread_safe_and_accepts_once(self) -> None:
        token = TextGenerationCancellationToken()
        barrier = threading.Barrier(12)
        accepted: list[bool] = []
        lock = threading.Lock()

        def request() -> None:
            barrier.wait()
            result = token.request_cancel(TextGenerationCancelReason.HOST_REQUEST)
            with lock:
                accepted.append(result)

        threads = [threading.Thread(target=request) for _ in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive())

        self.assertEqual(accepted.count(True), 1)
        self.assertEqual(accepted.count(False), 11)
        self.assertIs(token.reason, TextGenerationCancelReason.HOST_REQUEST)

    def test_delta_exposes_context_identity_and_hides_text_from_repr(self) -> None:
        context = self._context()
        delta = TextGenerationDeltaEnvelope(
            context=context,
            delta_index=0,
            text="private transcript text",
            emotion_tags=("calm",),
        )
        self.assertEqual(delta.session_id, context.session_id)
        self.assertEqual(delta.turn_id, context.turn_id)
        self.assertEqual(delta.generation_id, context.generation_id)
        self.assertEqual(delta.text, "private transcript text")
        self.assertNotIn("private transcript text", repr(delta))

    def test_delta_normalizes_emotion_tags_to_tuple(self) -> None:
        delta = TextGenerationDeltaEnvelope(
            context=self._context(),
            delta_index=3,
            text="x",
            emotion_tags=["happy", "warm"],  # type: ignore[arg-type]
        )
        self.assertEqual(delta.emotion_tags, ("happy", "warm"))

    def test_delta_rejects_invalid_index(self) -> None:
        with self.assertRaises(TypeError):
            TextGenerationDeltaEnvelope(
                context=self._context(), delta_index=True, text="x"
            )
        with self.assertRaises(ValueError):
            TextGenerationDeltaEnvelope(
                context=self._context(), delta_index=-1, text="x"
            )

    def test_delta_rejects_invalid_context(self) -> None:
        with self.assertRaises(TypeError):
            TextGenerationDeltaEnvelope(  # type: ignore[arg-type]
                context=object(), delta_index=0, text="x"
            )

    def test_delta_rejects_non_string_text(self) -> None:
        with self.assertRaises(TypeError):
            TextGenerationDeltaEnvelope(  # type: ignore[arg-type]
                context=self._context(), delta_index=0, text=123
            )

    def test_close_outcome_values_are_exact(self) -> None:
        self.assertEqual(
            tuple(outcome.value for outcome in TextGenerationStreamCloseOutcome),
            ("closed", "already_closed", "failed"),
        )

    def test_close_result_normalizes_outcome_and_public_metadata(self) -> None:
        result = TextGenerationStreamCloseResult(
            outcome="failed",
            safe_message="cleanup failed",
            public_metadata={"token": "secret", "attempt": 1},
        )
        self.assertIs(result.outcome, TextGenerationStreamCloseOutcome.FAILED)
        self.assertEqual(result.safe_message, "cleanup failed")
        self.assertEqual(result.public_metadata["token"], "<redacted>")
        self.assertEqual(result.public_metadata["attempt"], 1)
        with self.assertRaises(TypeError):
            result.public_metadata["x"] = 1  # type: ignore[index]

    def test_module_public_names_are_exact(self) -> None:
        import framework.realtime_text_generation as module

        self.assertEqual(
            tuple(module.__all__[:5]),
            (
                "TextGenerationCancelReason",
                "TextGenerationCancellationToken",
                "TextGenerationDeltaEnvelope",
                "TextGenerationStreamCloseOutcome",
                "TextGenerationStreamCloseResult",
            ),
        )

    def test_root_public_surface_remains_127_and_excludes_stream_models(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        for name in (
            "TextGenerationCancelReason",
            "TextGenerationCancellationToken",
            "TextGenerationDeltaEnvelope",
            "TextGenerationStreamCloseOutcome",
            "TextGenerationStreamCloseResult",
        ):
            self.assertNotIn(name, framework.__all__)
            self.assertFalse(hasattr(framework, name))


if __name__ == "__main__":
    unittest.main()
