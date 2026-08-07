from __future__ import annotations

import unittest

from framework.identity import GenerationId, SessionId, TurnId
from framework.realtime import RealtimeTurn
from framework.realtime_stage import RealtimeStageContext
from framework.realtime_text_generation import (
    TextGenerationCancelReason,
    TextGenerationCancellationToken,
    TextGenerationProviderError,
)
from framework.realtime_text_generation_provider_adapters import (
    FallbackTextGenerationAdapter,
    GeminiTextGenerationAdapter,
    OpenAITextGenerationAdapter,
    RouterTextGenerationAdapter,
    XAITextGenerationAdapter,
)
from tests.test_realtime_text_generation_provider_adapters import (
    _FakeClient,
    _FakeProviderStream as _OpenAIProviderStream,
    _chunk,
)
from tests.test_realtime_text_generation_provider_control_b import (
    _FakeGeminiClient,
    _FakeProviderStream as _GeminiProviderStream,
    _FakeStage,
    _GeminiChunk,
    _TupleSource,
)


class ProviderAggregateAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )

    def _turn(self, text: str = "hello") -> RealtimeTurn:
        return RealtimeTurn(
            turn_id=self.context.turn_id,
            session_id=self.context.session_id,
            input_text=text,
        )

    def test_openai_fake_stream_correlates_and_hard_cancel_is_truthful(self) -> None:
        client = _FakeClient(
            lambda: _OpenAIProviderStream([_chunk("open"), _chunk("ai")])
        )
        adapter = OpenAITextGenerationAdapter(client=client, model="fake-openai")
        token = TextGenerationCancellationToken()
        deltas = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=token,
            )
        )
        self.assertEqual([delta.text for delta in deltas], ["open", "ai"])
        self.assertTrue(all(delta.context == self.context for delta in deltas))
        self.assertEqual([delta.delta_index for delta in deltas], [0, 1])
        self.assertFalse(adapter.capability().provider_hard_cancel_supported)

    def test_xai_fake_stream_correlates_and_hard_cancel_is_truthful(self) -> None:
        client = _FakeClient(lambda: _OpenAIProviderStream([_chunk("xai")]))
        adapter = XAITextGenerationAdapter(client=client, model="fake-xai")
        deltas = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual([delta.text for delta in deltas], ["xai"])
        self.assertEqual(deltas[0].context, self.context)
        self.assertFalse(adapter.capability().provider_hard_cancel_supported)

    def test_gemini_fake_stream_is_stateless_and_hard_cancel_truthful(self) -> None:
        client = _FakeGeminiClient(
            lambda: _GeminiProviderStream([_GeminiChunk("gemini")])
        )
        adapter = GeminiTextGenerationAdapter(client=client, model="fake-gemini")
        deltas = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual([delta.text for delta in deltas], ["gemini"])
        self.assertFalse(hasattr(client, "chats"))
        self.assertFalse(adapter.capability().provider_hard_cancel_supported)

    def test_direct_provider_cancel_suppresses_future_delivery(self) -> None:
        factories = (
            lambda: OpenAITextGenerationAdapter(
                client=_FakeClient(
                    lambda: _OpenAIProviderStream([_chunk("first"), _chunk("never")])
                ),
                model="fake-openai",
            ),
            lambda: XAITextGenerationAdapter(
                client=_FakeClient(
                    lambda: _OpenAIProviderStream([_chunk("first"), _chunk("never")])
                ),
                model="fake-xai",
            ),
            lambda: GeminiTextGenerationAdapter(
                client=_FakeGeminiClient(
                    lambda: _GeminiProviderStream(
                        [_GeminiChunk("first"), _GeminiChunk("never")]
                    )
                ),
                model="fake-gemini",
            ),
        )
        for factory in factories:
            with self.subTest(factory=factory):
                token = TextGenerationCancellationToken()
                stream = factory().open_stream(
                    context=self.context,
                    request=self._turn(),
                    cancellation_token=token,
                )
                self.assertEqual(next(stream).text, "first")
                self.assertTrue(
                    stream.request_cancel(TextGenerationCancelReason.INTERRUPT)
                )
                self.assertEqual(list(stream), [])

    def test_fallback_pre_delta_failure_uses_same_context_and_token(self) -> None:
        primary = _FakeStage(
            open_error=TextGenerationProviderError(
                public_error_code="provider_unavailable",
                safe_message="Primary unavailable.",
                retryable=True,
            )
        )
        fallback = _FakeStage(sources=[_TupleSource([("fallback", ())])])
        adapter = FallbackTextGenerationAdapter(primary=primary, fallback=fallback)
        token = TextGenerationCancellationToken()
        deltas = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=token,
            )
        )
        self.assertEqual([delta.text for delta in deltas], ["fallback"])
        self.assertEqual(fallback.open_calls, 1)
        self.assertIs(fallback.received[0][0], self.context)
        self.assertIs(fallback.received[0][2], token)

    def test_fallback_post_delta_failure_never_mixes_fallback_answer(self) -> None:
        primary = _FakeStage(
            sources=[_TupleSource([("partial", ())], fail_after=1)]
        )
        fallback = _FakeStage(sources=[_TupleSource([("fallback", ())])])
        adapter = FallbackTextGenerationAdapter(primary=primary, fallback=fallback)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        self.assertEqual(next(stream).text, "partial")
        with self.assertRaises(TextGenerationProviderError):
            next(stream)
        self.assertEqual(fallback.open_calls, 0)

    def test_fallback_cancellation_never_starts_fallback(self) -> None:
        primary = _FakeStage(
            sources=[_TupleSource([("partial", ()), ("never", ())])]
        )
        fallback = _FakeStage(sources=[_TupleSource([("fallback", ())])])
        adapter = FallbackTextGenerationAdapter(primary=primary, fallback=fallback)
        token = TextGenerationCancellationToken()
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=token,
        )
        self.assertEqual(next(stream).text, "partial")
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.HOST_REQUEST))
        self.assertEqual(list(stream), [])
        self.assertEqual(fallback.open_calls, 0)

    def test_router_selects_once_and_preserves_context_token(self) -> None:
        selected = _FakeStage(sources=[_TupleSource([("selected", ())])])
        calls: list[str] = []

        def choose(_request: RealtimeTurn) -> str:
            calls.append("choose")
            return "selected"

        adapter = RouterTextGenerationAdapter(
            routes={"selected": selected},
            route_selector=choose,
        )
        token = TextGenerationCancellationToken()
        deltas = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=token,
            )
        )
        self.assertEqual([delta.text for delta in deltas], ["selected"])
        self.assertEqual(calls, ["choose"])
        self.assertIs(selected.received[0][0], self.context)
        self.assertIs(selected.received[0][2], token)

    def test_composite_capabilities_never_overclaim_hard_cancel(self) -> None:
        hard = _FakeStage(
            sources=[_TupleSource([("hard", ())])],
            hard_cancel=True,
        )
        soft = _FakeStage(
            sources=[_TupleSource([("soft", ())])],
            hard_cancel=False,
        )
        fallback = FallbackTextGenerationAdapter(primary=hard, fallback=soft)
        router = RouterTextGenerationAdapter(
            routes={"hard": hard, "soft": soft},
            route_selector=lambda _request: "hard",
        )
        self.assertFalse(fallback.capability().provider_hard_cancel_supported)
        self.assertFalse(router.capability().provider_hard_cancel_supported)

    def test_raw_provider_exception_detail_is_not_public_across_adapters(self) -> None:
        direct_cases = (
            OpenAITextGenerationAdapter(
                client=_FakeClient(
                    lambda: _OpenAIProviderStream([]),
                    create_error=ConnectionError("raw-openai bearer-secret-1"),
                ),
                model="fake-openai",
            ),
            XAITextGenerationAdapter(
                client=_FakeClient(
                    lambda: _OpenAIProviderStream([]),
                    create_error=TimeoutError("raw-xai bearer-secret-2"),
                ),
                model="fake-xai",
            ),
            GeminiTextGenerationAdapter(
                client=_FakeGeminiClient(
                    lambda: _GeminiProviderStream([]),
                    create_error=PermissionError("raw-gemini bearer-secret-3"),
                ),
                model="fake-gemini",
            ),
        )
        for adapter in direct_cases:
            with self.subTest(adapter=type(adapter).__name__):
                with self.assertRaises(TextGenerationProviderError) as caught:
                    adapter.open_stream(
                        context=self.context,
                        request=self._turn(),
                        cancellation_token=TextGenerationCancellationToken(),
                    )
                public = repr(caught.exception).lower()
                self.assertNotIn("bearer-secret", public)
                self.assertNotIn("raw-openai", public)
                self.assertNotIn("raw-xai", public)
                self.assertNotIn("raw-gemini", public)
                self.assertIsNone(caught.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
