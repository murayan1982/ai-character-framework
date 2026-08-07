from __future__ import annotations

from dataclasses import dataclass
import unittest

from framework.identity import GenerationId, SessionId, TurnId
from framework.realtime import RealtimeTurn
from framework.realtime_capabilities import RuntimeCapabilityState, TextGenerationCapability
from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind
from framework.realtime_text_generation import (
    CancelableTextGenerationStage,
    ProviderNeutralTextGenerationStream,
    TextGenerationCancelReason,
    TextGenerationCancellationToken,
    TextGenerationProviderError,
)
from framework.realtime_text_generation_provider_adapters import (
    FallbackTextGenerationAdapter,
    GeminiTextGenerationAdapter,
    RouterTextGenerationAdapter,
)


@dataclass
class _GeminiChunk:
    text: str | None


class _FakeProviderStream:
    def __init__(self, items, *, fail_after=None, error=None):
        self.items = list(items)
        self.index = 0
        self.fail_after = fail_after
        self.error = error or RuntimeError("raw gemini response bearer-secret-456")
        self.close_calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.fail_after is not None and self.index >= self.fail_after:
            raise self.error
        if self.index >= len(self.items):
            raise StopIteration
        item = self.items[self.index]
        self.index += 1
        return item

    def close(self):
        self.close_calls += 1


class _GeminiModels:
    def __init__(self, owner):
        self.owner = owner

    def generate_content_stream(self, **kwargs):
        self.owner.calls.append(kwargs)
        if self.owner.create_error is not None:
            raise self.owner.create_error
        stream = self.owner.stream_factory()
        self.owner.streams.append(stream)
        return stream


class _FakeGeminiClient:
    def __init__(self, stream_factory, *, create_error=None):
        self.stream_factory = stream_factory
        self.create_error = create_error
        self.calls = []
        self.streams = []
        self.models = _GeminiModels(self)


class _TupleSource:
    def __init__(self, items, *, fail_after=None, error=None):
        self.items = list(items)
        self.index = 0
        self.fail_after = fail_after
        self.error = error or RuntimeError("raw child provider payload private-token")
        self.close_calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.fail_after is not None and self.index >= self.fail_after:
            raise self.error
        if self.index >= len(self.items):
            raise StopIteration
        item = self.items[self.index]
        self.index += 1
        return item

    def close(self):
        self.close_calls += 1


class _FakeStage:
    def __init__(
        self,
        *,
        sources=None,
        open_error=None,
        hard_cancel=False,
        cooperative=True,
    ):
        self.sources = list(sources or [])
        self.open_error = open_error
        self.open_calls = 0
        self.close_calls = 0
        self.received = []
        self._capability = TextGenerationCapability(
            runtime=RuntimeCapabilityState(
                configured=True,
                runtime_available=True,
                unavailable_reason=None,
                public_metadata={"fake": True},
            ),
            streaming_supported=True,
            cooperative_cancel_supported=cooperative,
            provider_hard_cancel_supported=hard_cancel,
            public_metadata={"fake": True},
        )

    @property
    def stage_kind(self):
        return RealtimeStageKind.TEXT_GENERATION

    def preflight(self):
        return self._capability

    def capability(self):
        return self._capability

    def open_stream(self, *, context, request, cancellation_token):
        self.open_calls += 1
        self.received.append((context, request, cancellation_token))
        if self.open_error is not None:
            raise self.open_error
        if not self.sources:
            source = _TupleSource([])
        else:
            source = self.sources.pop(0)
        return ProviderNeutralTextGenerationStream(
            context=context,
            capability=self._capability,
            source=source,
            user_input=request.input_text,
            cancellation_token=cancellation_token,
        )

    def close(self):
        self.close_calls += 1


class ProviderControlBTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )

    def _turn(self, text="hello") -> RealtimeTurn:
        return RealtimeTurn(
            turn_id=self.context.turn_id,
            session_id=self.context.session_id,
            input_text=text,
        )

    def _next_context(self) -> RealtimeStageContext:
        return RealtimeStageContext(
            session_id=self.context.session_id,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )

    def _gemini(self, client, **kwargs) -> GeminiTextGenerationAdapter:
        return GeminiTextGenerationAdapter(
            client=client,
            model="fake-gemini",
            system_instruction="system",
            **kwargs,
        )

    def test_gemini_adapter_matches_cancelable_stage_protocol(self) -> None:
        client = _FakeGeminiClient(
            lambda: _FakeProviderStream([_GeminiChunk("ok")])
        )
        adapter = self._gemini(client)
        self.assertIsInstance(adapter, CancelableTextGenerationStage)
        self.assertIs(adapter.stage_kind, RealtimeStageKind.TEXT_GENERATION)
        self.assertEqual(adapter.provider_name, "google")
        self.assertTrue(adapter.capability().streaming_supported)
        self.assertTrue(adapter.capability().cooperative_cancel_supported)
        self.assertFalse(adapter.capability().provider_hard_cancel_supported)
        self.assertFalse(
            adapter.capability().public_metadata["provider_owned_chat_state"]
        )

    def test_gemini_normal_stream_uses_stateless_transactional_history(self) -> None:
        streams = [
            [_GeminiChunk("hello "), _GeminiChunk("[happy]world")],
            [_GeminiChunk("again")],
        ]
        client = _FakeGeminiClient(
            lambda: _FakeProviderStream(streams.pop(0))
        )
        adapter = self._gemini(client, temperature=0.3, max_output_tokens=80)
        first = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn("user-one"),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual([delta.text for delta in first], ["hello ", "world"])
        self.assertEqual(first[1].emotion_tags, ("happy",))
        self.assertEqual(
            client.calls[0]["contents"],
            [{"role": "user", "parts": [{"text": "user-one"}]}],
        )
        self.assertEqual(
            client.calls[0]["config"],
            {
                "system_instruction": "system",
                "temperature": 0.3,
                "max_output_tokens": 80,
            },
        )

        context2 = self._next_context()
        list(
            adapter.open_stream(
                context=context2,
                request=RealtimeTurn(
                    turn_id=context2.turn_id,
                    session_id=context2.session_id,
                    input_text="user-two",
                ),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual(
            client.calls[1]["contents"],
            [
                {"role": "user", "parts": [{"text": "user-one"}]},
                {"role": "model", "parts": [{"text": "hello world"}]},
                {"role": "user", "parts": [{"text": "user-two"}]},
            ],
        )

    def test_gemini_cancelled_turn_does_not_commit_history(self) -> None:
        streams = [
            [_GeminiChunk("partial"), _GeminiChunk("never")],
            [_GeminiChunk("next")],
        ]
        client = _FakeGeminiClient(
            lambda: _FakeProviderStream(streams.pop(0))
        )
        adapter = self._gemini(client)
        token = TextGenerationCancellationToken()
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn("cancel-me"),
            cancellation_token=token,
        )
        self.assertEqual(next(stream).text, "partial")
        token.request_cancel(TextGenerationCancelReason.INTERRUPT)
        self.assertEqual(list(stream), [])

        context2 = self._next_context()
        list(
            adapter.open_stream(
                context=context2,
                request=RealtimeTurn(
                    turn_id=context2.turn_id,
                    session_id=context2.session_id,
                    input_text="after-cancel",
                ),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual(
            client.calls[1]["contents"],
            [{"role": "user", "parts": [{"text": "after-cancel"}]}],
        )

    def test_gemini_source_failure_does_not_commit_history(self) -> None:
        streams = [
            _FakeProviderStream([_GeminiChunk("partial")], fail_after=1),
            _FakeProviderStream([_GeminiChunk("next")]),
        ]
        client = _FakeGeminiClient(lambda: streams.pop(0))
        adapter = self._gemini(client)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn("failure"),
            cancellation_token=TextGenerationCancellationToken(),
        )
        self.assertEqual(next(stream).text, "partial")
        with self.assertRaises(TextGenerationProviderError):
            next(stream)

        context2 = self._next_context()
        list(
            adapter.open_stream(
                context=context2,
                request=RealtimeTurn(
                    turn_id=context2.turn_id,
                    session_id=context2.session_id,
                    input_text="after-failure",
                ),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual(
            client.calls[1]["contents"],
            [{"role": "user", "parts": [{"text": "after-failure"}]}],
        )

    def test_gemini_create_exception_is_public_safe(self) -> None:
        client = _FakeGeminiClient(
            lambda: _FakeProviderStream([]),
            create_error=ConnectionError("raw endpoint token=secret"),
        )
        adapter = self._gemini(client)
        with self.assertRaises(TextGenerationProviderError) as caught:
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        error = caught.exception
        self.assertEqual(error.public_error_code, "provider_unavailable")
        self.assertTrue(error.retryable)
        self.assertNotIn("secret", str(error))
        self.assertIsNone(error.__cause__)

    def test_gemini_iteration_exception_is_public_safe(self) -> None:
        client = _FakeGeminiClient(
            lambda: _FakeProviderStream(
                [], fail_after=0, error=TimeoutError("raw body secret")
            )
        )
        stream = self._gemini(client).open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        with self.assertRaises(TextGenerationProviderError) as caught:
            next(stream)
        self.assertEqual(caught.exception.public_error_code, "timeout")
        self.assertNotIn("secret", repr(caught.exception))

    def test_gemini_adapter_does_not_depend_on_mutable_chat_surface(self) -> None:
        client = _FakeGeminiClient(
            lambda: _FakeProviderStream([_GeminiChunk("ok")])
        )
        self.assertFalse(hasattr(client, "chats"))
        adapter = self._gemini(client)
        self.assertEqual(
            [delta.text for delta in adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )],
            ["ok"],
        )

    def test_gemini_stream_close_is_typed_and_source_cleanup_once(self) -> None:
        source = _FakeProviderStream([_GeminiChunk("unused")])
        client = _FakeGeminiClient(lambda: source)
        stream = self._gemini(client).open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        self.assertEqual(stream.close().outcome.value, "closed")
        self.assertEqual(stream.dispose().outcome.value, "already_closed")
        self.assertEqual(source.close_calls, 1)

    def test_fallback_adapter_matches_protocol_and_uses_conservative_capability(self) -> None:
        primary = _FakeStage(
            sources=[_TupleSource([("primary", ())])],
            hard_cancel=True,
        )
        fallback = _FakeStage(
            sources=[_TupleSource([("fallback", ())])],
            hard_cancel=False,
        )
        adapter = FallbackTextGenerationAdapter(
            primary=primary,
            fallback=fallback,
        )
        self.assertIsInstance(adapter, CancelableTextGenerationStage)
        self.assertTrue(adapter.capability().streaming_supported)
        self.assertTrue(adapter.capability().cooperative_cancel_supported)
        self.assertFalse(adapter.capability().provider_hard_cancel_supported)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        self.assertIs(stream.capability, adapter.capability())

    def test_fallback_primary_success_never_starts_fallback(self) -> None:
        primary = _FakeStage(sources=[_TupleSource([("primary", ())])])
        fallback = _FakeStage(sources=[_TupleSource([("fallback", ())])])
        adapter = FallbackTextGenerationAdapter(primary=primary, fallback=fallback)
        deltas = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual([delta.text for delta in deltas], ["primary"])
        self.assertEqual(primary.open_calls, 1)
        self.assertEqual(fallback.open_calls, 0)

    def test_fallback_open_failure_before_delta_starts_fallback(self) -> None:
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
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=token,
        )
        self.assertEqual([delta.text for delta in stream], ["fallback"])
        self.assertEqual(fallback.open_calls, 1)
        self.assertIs(fallback.received[0][2], token)
        self.assertEqual(fallback.received[0][0], self.context)

    def test_fallback_iteration_failure_before_delta_starts_fallback(self) -> None:
        primary = _FakeStage(
            sources=[_TupleSource([], fail_after=0)]
        )
        fallback = _FakeStage(sources=[_TupleSource([("fallback", ())])])
        adapter = FallbackTextGenerationAdapter(primary=primary, fallback=fallback)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        self.assertEqual([delta.text for delta in stream], ["fallback"])
        self.assertEqual(fallback.open_calls, 1)

    def test_fallback_post_delta_failure_does_not_start_fallback(self) -> None:
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
        with self.assertRaises(TextGenerationProviderError) as caught:
            next(stream)
        self.assertEqual(caught.exception.public_error_code, "provider_request_failed")
        self.assertEqual(fallback.open_calls, 0)

    def test_fallback_cancel_after_delta_does_not_start_fallback(self) -> None:
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
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.INTERRUPT))
        self.assertEqual(list(stream), [])
        self.assertEqual(fallback.open_calls, 0)

    def test_fallback_pre_cancel_does_not_open_any_child(self) -> None:
        primary = _FakeStage(sources=[_TupleSource([("primary", ())])])
        fallback = _FakeStage(sources=[_TupleSource([("fallback", ())])])
        adapter = FallbackTextGenerationAdapter(primary=primary, fallback=fallback)
        token = TextGenerationCancellationToken()
        token.request_cancel(TextGenerationCancelReason.HOST_REQUEST)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=token,
        )
        self.assertEqual(list(stream), [])
        self.assertEqual(primary.open_calls, 0)
        self.assertEqual(fallback.open_calls, 0)
        self.assertIs(stream.cancellation_token, token)

    def test_fallback_preserves_same_context_and_token_across_failover(self) -> None:
        primary = _FakeStage(sources=[_TupleSource([], fail_after=0)])
        fallback = _FakeStage(sources=[_TupleSource([("fallback", ())])])
        token = TextGenerationCancellationToken()
        stream = FallbackTextGenerationAdapter(
            primary=primary, fallback=fallback
        ).open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=token,
        )
        delta = next(stream)
        self.assertEqual(delta.context, self.context)
        self.assertIs(stream.cancellation_token, token)
        self.assertIs(primary.received[0][2], token)
        self.assertIs(fallback.received[0][2], token)

    def test_router_selects_route_once_and_preserves_context_token(self) -> None:
        chat = _FakeStage(sources=[_TupleSource([("chat", ())])])
        code = _FakeStage(sources=[_TupleSource([("code", ())])])
        calls = []

        def selector(request):
            calls.append(request.input_text)
            return "code"

        adapter = RouterTextGenerationAdapter(
            routes={"chat": chat, "code": code},
            route_selector=selector,
        )
        token = TextGenerationCancellationToken()
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn("write code"),
            cancellation_token=token,
        )
        self.assertEqual([delta.text for delta in stream], ["code"])
        self.assertEqual(calls, ["write code"])
        self.assertEqual(chat.open_calls, 0)
        self.assertEqual(code.open_calls, 1)
        self.assertIs(code.received[0][2], token)
        self.assertIs(stream.cancellation_token, token)
        self.assertIs(stream.capability, adapter.capability())

    def test_router_cancel_propagates_to_selected_child_token(self) -> None:
        chat = _FakeStage(
            sources=[_TupleSource([("one", ()), ("two", ())])]
        )
        adapter = RouterTextGenerationAdapter(
            routes={"chat": chat},
            route_selector=lambda request: "chat",
        )
        token = TextGenerationCancellationToken()
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=token,
        )
        self.assertEqual(next(stream).text, "one")
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.TURN_CANCELLED))
        self.assertTrue(token.cancel_requested)
        self.assertEqual(token.reason, TextGenerationCancelReason.TURN_CANCELLED)
        self.assertEqual(list(stream), [])

    def test_router_selector_failure_is_public_safe(self) -> None:
        stage = _FakeStage(sources=[_TupleSource([("unused", ())])])

        def selector(_request):
            raise RuntimeError("raw route payload private-key")

        adapter = RouterTextGenerationAdapter(
            routes={"chat": stage},
            route_selector=selector,
        )
        with self.assertRaises(TextGenerationProviderError) as caught:
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        self.assertEqual(caught.exception.public_error_code, "route_selection_failed")
        self.assertNotIn("private-key", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_router_capability_is_conservative_minimum(self) -> None:
        hard = _FakeStage(
            sources=[_TupleSource([("a", ())])],
            hard_cancel=True,
            cooperative=True,
        )
        soft = _FakeStage(
            sources=[_TupleSource([("b", ())])],
            hard_cancel=False,
            cooperative=False,
        )
        adapter = RouterTextGenerationAdapter(
            routes={"hard": hard, "soft": soft},
            route_selector=lambda request: "hard",
        )
        capability = adapter.capability()
        self.assertTrue(capability.streaming_supported)
        self.assertFalse(capability.cooperative_cancel_supported)
        self.assertFalse(capability.provider_hard_cancel_supported)

    def test_router_close_closes_duplicate_child_stage_once(self) -> None:
        stage = _FakeStage(sources=[_TupleSource([("unused", ())])])
        adapter = RouterTextGenerationAdapter(
            routes={"chat": stage, "code": stage},
            route_selector=lambda request: "chat",
        )
        adapter.close()
        adapter.close()
        self.assertEqual(stage.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
