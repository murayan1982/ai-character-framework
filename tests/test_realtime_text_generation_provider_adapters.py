from __future__ import annotations

from dataclasses import dataclass
import unittest

from framework.identity import GenerationId, SessionId, TurnId
from framework.realtime import RealtimeTurn
from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind
from framework.realtime_text_generation import (
    CancelableTextGenerationStage,
    TextGenerationCancelReason,
    TextGenerationCancellationToken,
    TextGenerationProviderError,
)
from framework.realtime_text_generation_provider_adapters import (
    OpenAITextGenerationAdapter,
    XAITextGenerationAdapter,
)


@dataclass
class _Delta:
    content: str | None


@dataclass
class _Choice:
    delta: _Delta


@dataclass
class _Chunk:
    choices: list[_Choice]


def _chunk(text: str | None) -> _Chunk:
    return _Chunk(choices=[_Choice(delta=_Delta(content=text))])


class _FakeProviderStream:
    def __init__(self, items, *, fail_after=None, close_error=None):
        self.items = list(items)
        self.index = 0
        self.fail_after = fail_after
        self.close_error = close_error
        self.close_calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.fail_after is not None and self.index >= self.fail_after:
            raise RuntimeError("raw provider body bearer-secret-123")
        if self.index >= len(self.items):
            raise StopIteration
        item = self.items[self.index]
        self.index += 1
        return item

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class _Completions:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        if self.owner.create_error is not None:
            raise self.owner.create_error
        stream = self.owner.stream_factory()
        self.owner.streams.append(stream)
        return stream


class _Chat:
    def __init__(self, owner):
        self.completions = _Completions(owner)


class _FakeClient:
    def __init__(self, stream_factory, *, create_error=None):
        self.stream_factory = stream_factory
        self.create_error = create_error
        self.calls = []
        self.streams = []
        self.chat = _Chat(self)


class ProviderAdapterTests(unittest.TestCase):
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

    def _openai(self, client, **kwargs):
        return OpenAITextGenerationAdapter(
            client=client,
            model="fake-openai",
            system_instruction="system",
            **kwargs,
        )

    def _xai(self, client, **kwargs):
        return XAITextGenerationAdapter(
            client=client,
            model="fake-xai",
            system_instruction="system",
            **kwargs,
        )

    def test_openai_adapter_matches_cancelable_stage_protocol(self) -> None:
        client = _FakeClient(lambda: _FakeProviderStream([_chunk("ok")]))
        adapter = self._openai(client)
        self.assertIsInstance(adapter, CancelableTextGenerationStage)
        self.assertIs(adapter.stage_kind, RealtimeStageKind.TEXT_GENERATION)
        self.assertTrue(adapter.capability().streaming_supported)
        self.assertTrue(adapter.capability().cooperative_cancel_supported)
        self.assertFalse(adapter.capability().provider_hard_cancel_supported)

    def test_xai_adapter_matches_cancelable_stage_protocol(self) -> None:
        client = _FakeClient(lambda: _FakeProviderStream([_chunk("ok")]))
        adapter = self._xai(client)
        self.assertIsInstance(adapter, CancelableTextGenerationStage)
        self.assertEqual(adapter.provider_name, "xai")
        self.assertFalse(adapter.capability().provider_hard_cancel_supported)

    def test_openai_normal_stream_is_correlated_and_transactional(self) -> None:
        streams = [
            [_chunk("hello "), _chunk("[happy]world")],
            [_chunk("again")],
        ]
        client = _FakeClient(lambda: _FakeProviderStream(streams.pop(0)))
        adapter = self._openai(client, temperature=0.25, max_tokens=64)
        token = TextGenerationCancellationToken()
        first = adapter.open_stream(
            context=self.context,
            request=self._turn("user-one"),
            cancellation_token=token,
        )
        deltas = list(first)
        self.assertEqual([d.text for d in deltas], ["hello ", "world"])
        self.assertEqual(deltas[1].emotion_tags, ("happy",))
        self.assertTrue(all(d.context == self.context for d in deltas))
        self.assertEqual([d.delta_index for d in deltas], [0, 1])
        self.assertEqual(
            client.calls[0]["messages"],
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user-one"},
            ],
        )
        self.assertEqual(client.calls[0]["temperature"], 0.25)
        self.assertEqual(client.calls[0]["max_tokens"], 64)

        context2 = RealtimeStageContext(
            session_id=self.context.session_id,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
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
            client.calls[1]["messages"],
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user-one"},
                {"role": "assistant", "content": "hello world"},
                {"role": "user", "content": "user-two"},
            ],
        )

    def test_xai_normal_stream_uses_same_transaction_contract(self) -> None:
        streams = [[_chunk("xai")], [_chunk("next")]]
        client = _FakeClient(lambda: _FakeProviderStream(streams.pop(0)))
        adapter = self._xai(client)
        list(
            adapter.open_stream(
                context=self.context,
                request=self._turn("first"),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        context2 = RealtimeStageContext(
            session_id=self.context.session_id,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
        list(
            adapter.open_stream(
                context=context2,
                request=RealtimeTurn(
                    turn_id=context2.turn_id,
                    session_id=context2.session_id,
                    input_text="second",
                ),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual(client.calls[1]["messages"][1:3], [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "xai"},
        ])

    def test_cancelled_openai_turn_does_not_commit_history(self) -> None:
        streams = [
            [_chunk("partial"), _chunk("never")],
            [_chunk("next")],
        ]
        client = _FakeClient(lambda: _FakeProviderStream(streams.pop(0)))
        adapter = self._openai(client)
        token = TextGenerationCancellationToken()
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn("cancel-me"),
            cancellation_token=token,
        )
        self.assertEqual(next(stream).text, "partial")
        self.assertTrue(token.request_cancel(TextGenerationCancelReason.INTERRUPT))
        self.assertEqual(list(stream), [])

        context2 = RealtimeStageContext(
            session_id=self.context.session_id,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
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
            client.calls[1]["messages"],
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "after-cancel"},
            ],
        )

    def test_provider_iteration_failure_does_not_commit_history(self) -> None:
        streams = [
            _FakeProviderStream([_chunk("partial")], fail_after=1),
            _FakeProviderStream([_chunk("next")]),
        ]
        client = _FakeClient(lambda: streams.pop(0))
        adapter = self._openai(client)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn("failed-user"),
            cancellation_token=TextGenerationCancellationToken(),
        )
        self.assertEqual(next(stream).text, "partial")
        with self.assertRaises(TextGenerationProviderError) as ctx:
            next(stream)
        self.assertEqual(ctx.exception.public_error_code, "provider_request_failed")
        self.assertNotIn("bearer-secret-123", str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)

        context2 = RealtimeStageContext(
            session_id=self.context.session_id,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
        list(
            adapter.open_stream(
                context=context2,
                request=RealtimeTurn(
                    turn_id=context2.turn_id,
                    session_id=context2.session_id,
                    input_text="retry",
                ),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual(client.calls[1]["messages"][1:], [
            {"role": "user", "content": "retry"}
        ])

    def test_create_timeout_is_safely_classified_without_raw_detail(self) -> None:
        client = _FakeClient(
            lambda: _FakeProviderStream([]),
            create_error=TimeoutError("private endpoint /home/user/key"),
        )
        adapter = self._openai(client)
        with self.assertRaises(TextGenerationProviderError) as ctx:
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        error = ctx.exception
        self.assertEqual(error.public_error_code, "timeout")
        self.assertTrue(error.retryable)
        self.assertEqual(error.safe_message, "The operation timed out.")
        self.assertNotIn("private endpoint", repr(error))
        self.assertIsNone(error.__cause__)

    def test_create_permission_failure_is_safely_classified(self) -> None:
        client = _FakeClient(
            lambda: _FakeProviderStream([]),
            create_error=PermissionError("api_key=private"),
        )
        adapter = self._xai(client)
        with self.assertRaises(TextGenerationProviderError) as ctx:
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        self.assertEqual(ctx.exception.public_error_code, "authentication_required")
        self.assertFalse(ctx.exception.retryable)
        self.assertNotIn("private", str(ctx.exception))

    def test_create_connection_failure_is_retryable_and_safe(self) -> None:
        client = _FakeClient(
            lambda: _FakeProviderStream([]),
            create_error=ConnectionError("https://private-host.invalid"),
        )
        adapter = self._openai(client)
        with self.assertRaises(TextGenerationProviderError) as ctx:
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        self.assertEqual(ctx.exception.public_error_code, "provider_unavailable")
        self.assertTrue(ctx.exception.retryable)
        self.assertNotIn("private-host", repr(ctx.exception))

    def test_generic_create_failure_uses_provider_request_failed(self) -> None:
        client = _FakeClient(
            lambda: _FakeProviderStream([]),
            create_error=RuntimeError("response body secret"),
        )
        adapter = self._xai(client)
        with self.assertRaises(TextGenerationProviderError) as ctx:
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        error = ctx.exception
        self.assertEqual(error.public_error_code, "provider_request_failed")
        self.assertTrue(error.retryable)
        self.assertEqual(error.public_metadata["provider"], "xai")
        self.assertNotIn("response body", repr(error))

    def test_invalid_provider_chunk_is_public_safe(self) -> None:
        client = _FakeClient(lambda: _FakeProviderStream([object()]))
        adapter = self._openai(client)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        with self.assertRaises(TextGenerationProviderError) as ctx:
            next(stream)
        self.assertNotIn("object", str(ctx.exception).lower())
        self.assertEqual(ctx.exception.public_metadata["provider"], "openai")

    def test_provider_none_delta_is_skipped(self) -> None:
        client = _FakeClient(
            lambda: _FakeProviderStream([_chunk(None), _chunk("visible")])
        )
        adapter = self._openai(client)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        self.assertEqual([delta.text for delta in stream], ["visible"])

    def test_emotion_tag_split_across_provider_chunks_is_cleaned(self) -> None:
        client = _FakeClient(
            lambda: _FakeProviderStream(
                [_chunk("hello [hap"), _chunk("py]world")]
            )
        )
        adapter = self._openai(client)
        deltas = list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertEqual([(d.text, d.emotion_tags) for d in deltas], [
            ("hello world", ("happy",))
        ])

    def test_close_stream_closes_underlying_provider_stream_once(self) -> None:
        provider_stream = _FakeProviderStream([_chunk("unused")])
        client = _FakeClient(lambda: provider_stream)
        adapter = self._openai(client)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        stream.close()
        stream.close()
        self.assertEqual(provider_stream.close_calls, 1)

    def test_adapter_close_closes_active_stream_and_is_idempotent(self) -> None:
        provider_stream = _FakeProviderStream([_chunk("unused")])
        client = _FakeClient(lambda: provider_stream)
        adapter = self._openai(client)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        adapter.close()
        adapter.close()
        self.assertTrue(stream.closed)
        self.assertEqual(provider_stream.close_calls, 1)

    def test_open_after_adapter_close_is_typed_rejection(self) -> None:
        client = _FakeClient(lambda: _FakeProviderStream([]))
        adapter = self._openai(client)
        adapter.close()
        with self.assertRaises(TextGenerationProviderError) as ctx:
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        self.assertEqual(ctx.exception.public_error_code, "stage_closed")
        self.assertEqual(client.calls, [])

    def test_reset_history_rejects_while_stream_active(self) -> None:
        client = _FakeClient(lambda: _FakeProviderStream([_chunk("active")]))
        adapter = self._openai(client)
        stream = adapter.open_stream(
            context=self.context,
            request=self._turn(),
            cancellation_token=TextGenerationCancellationToken(),
        )
        with self.assertRaisesRegex(RuntimeError, "cannot reset"):
            adapter.reset_history()
        stream.close()
        adapter.reset_history()

    def test_request_parameters_do_not_include_unset_optional_values(self) -> None:
        client = _FakeClient(lambda: _FakeProviderStream([]))
        adapter = self._openai(client)
        list(
            adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=TextGenerationCancellationToken(),
            )
        )
        self.assertNotIn("temperature", client.calls[0])
        self.assertNotIn("max_tokens", client.calls[0])
        self.assertTrue(client.calls[0]["stream"])

    def test_adapters_never_report_verified_provider_hard_cancel(self) -> None:
        for factory in (self._openai, self._xai):
            client = _FakeClient(lambda: _FakeProviderStream([_chunk("a")]))
            adapter = factory(client)
            token = TextGenerationCancellationToken()
            stream = adapter.open_stream(
                context=self.context,
                request=self._turn(),
                cancellation_token=token,
            )
            self.assertFalse(adapter.preflight().provider_hard_cancel_supported)
            self.assertEqual(next(stream).text, "a")
            self.assertTrue(token.request_cancel(TextGenerationCancelReason.INTERRUPT))
            self.assertFalse(stream.capability.provider_hard_cancel_supported)

    def test_text_generation_provider_error_never_retains_raw_exception(self) -> None:
        raw = RuntimeError("credential=secret provider-response-private")
        error = TextGenerationProviderError.from_exception(raw, provider="openai")
        self.assertEqual(error.public_error_code, "provider_request_failed")
        self.assertNotIn("secret", str(error))
        self.assertNotIn("private", repr(error))
        self.assertFalse(hasattr(error, "raw_error"))
        self.assertFalse(hasattr(error, "cause"))


if __name__ == "__main__":
    unittest.main()
