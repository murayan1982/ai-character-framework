"""Provider adapters for the v6 cancel-aware text-generation boundary.

FW-RT6-5b Control A provides OpenAI-compatible OpenAI/xAI adapters using only
explicitly injected clients. Importing this module does not import provider
SDKs, inspect credentials, construct provider clients, or execute network
requests.
"""

from __future__ import annotations

import re
import threading
from typing import Any, Callable, Iterator, Mapping, Sequence

from .realtime import RealtimeTurn
from .realtime_capabilities import RuntimeCapabilityState, TextGenerationCapability
from .realtime_stage import RealtimeStageContext, RealtimeStageKind
from .realtime_text_generation import (
    CancelableTextGenerationStage,
    ProviderNeutralTextGenerationStream,
    TextGenerationCancelReason,
    TextGenerationCancellationToken,
    TextGenerationCompletedTurn,
    TextGenerationDeltaEnvelope,
    TextGenerationHistorySink,
    TextGenerationProviderError,
    TextGenerationStream,
    TextGenerationStreamCloseOutcome,
    TextGenerationStreamCloseResult,
)

_TAG_PATTERN = re.compile(r"\[([a-zA-Z0-9_]+)\]")


def _copy_messages(messages: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    return [
        {"role": str(message["role"]), "content": str(message["content"])}
        for message in messages
    ]


class _TransactionalMessageHistory(TextGenerationHistorySink):
    """Framework-owned committed user/assistant history for one adapter."""

    __slots__ = ("_lock", "_messages", "_committed_contexts")

    def __init__(self, *, system_instruction: str) -> None:
        if not isinstance(system_instruction, str):
            raise TypeError("system_instruction must be a string")
        self._lock = threading.Lock()
        self._messages: list[dict[str, str]] = []
        if system_instruction:
            self._messages.append({"role": "system", "content": system_instruction})
        self._committed_contexts: set[tuple[str, str, str]] = set()

    @staticmethod
    def _context_key(turn: TextGenerationCompletedTurn) -> tuple[str, str, str]:
        return (
            str(turn.context.session_id),
            str(turn.context.turn_id),
            str(turn.context.generation_id),
        )

    def snapshot_with_user(self, user_input: str) -> list[dict[str, str]]:
        if not isinstance(user_input, str):
            raise TypeError("user_input must be a string")
        with self._lock:
            messages = _copy_messages(self._messages)
        messages.append({"role": "user", "content": user_input})
        return messages

    def commit_completed_turn(self, turn: TextGenerationCompletedTurn) -> None:
        if not isinstance(turn, TextGenerationCompletedTurn):
            raise TypeError("turn must be a TextGenerationCompletedTurn")
        key = self._context_key(turn)
        with self._lock:
            if key in self._committed_contexts:
                return
            self._messages.append({"role": "user", "content": turn.user_input})
            self._messages.append(
                {"role": "assistant", "content": turn.assistant_output}
            )
            self._committed_contexts.add(key)

    def reset(self, *, system_instruction: str) -> None:
        with self._lock:
            self._messages = []
            if system_instruction:
                self._messages.append(
                    {"role": "system", "content": system_instruction}
                )
            self._committed_contexts.clear()


class _OpenAICompatibleDeltaSource:
    """Convert OpenAI-compatible SDK chunks to provider-neutral source deltas."""

    __slots__ = (
        "_provider",
        "_stream",
        "_buffer",
        "_closed",
        "_source_exhausted",
        "_flush_emitted",
    )

    def __init__(self, *, provider: str, stream: Iterator[object]) -> None:
        if not hasattr(stream, "__next__"):
            try:
                stream = iter(stream)
            except TypeError as error:
                raise TextGenerationProviderError.from_exception(
                    error, provider=provider
                ) from None
        self._provider = provider
        self._stream = stream
        self._buffer = ""
        self._closed = False
        self._source_exhausted = False
        self._flush_emitted = False

    def __iter__(self) -> "_OpenAICompatibleDeltaSource":
        return self

    @staticmethod
    def _chunk_text(chunk: object) -> str | None:
        try:
            if isinstance(chunk, Mapping):
                choices = chunk["choices"]
                first = choices[0]
                delta = first["delta"] if isinstance(first, Mapping) else first.delta
                content = delta.get("content") if isinstance(delta, Mapping) else delta.content
            else:
                first = chunk.choices[0]
                content = first.delta.content
        except Exception as error:
            raise TextGenerationProviderError.from_exception(error) from None
        if content is None:
            return None
        if not isinstance(content, str):
            raise TextGenerationProviderError(
                public_error_code="provider_response_invalid",
                safe_message="Text-generation provider returned an invalid response.",
                retryable=False,
                public_metadata={"error_category": "invalid_provider_response"},
            )
        return content

    @staticmethod
    def _clean_buffer(buffer: str) -> tuple[str, tuple[str, ...]]:
        emotions = tuple(_TAG_PATTERN.findall(buffer))
        clean_text = _TAG_PATTERN.sub("", buffer)
        return clean_text, emotions

    def __next__(self) -> tuple[str, tuple[str, ...]]:
        if self._closed:
            raise StopIteration

        while True:
            if self._source_exhausted:
                if self._buffer and not self._flush_emitted:
                    self._flush_emitted = True
                    buffer, self._buffer = self._buffer, ""
                    return self._clean_buffer(buffer)
                raise StopIteration

            try:
                chunk = next(self._stream)
            except StopIteration:
                self._source_exhausted = True
                continue
            except TextGenerationProviderError:
                raise
            except Exception as error:
                raise TextGenerationProviderError.from_exception(
                    error, provider=self._provider
                ) from None

            try:
                content = self._chunk_text(chunk)
            except TextGenerationProviderError as error:
                if "provider" not in error.public_metadata:
                    raise TextGenerationProviderError(
                        public_error_code=error.public_error_code,
                        safe_message=error.safe_message,
                        retryable=error.retryable,
                        public_metadata={
                            **dict(error.public_metadata),
                            "provider": self._provider,
                        },
                    ) from None
                raise
            if not content:
                continue

            self._buffer += content
            if "[" in self._buffer:
                if "]" in self._buffer:
                    buffer, self._buffer = self._buffer, ""
                    return self._clean_buffer(buffer)
                if len(self._buffer) > 100:
                    buffer, self._buffer = self._buffer, ""
                    return buffer, ()
                continue

            buffer, self._buffer = self._buffer, ""
            return buffer, ()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_method = getattr(self._stream, "close", None)
        if close_method is None:
            return
        try:
            close_method()
        except Exception as error:
            raise TextGenerationProviderError.from_exception(
                error, provider=self._provider
            ) from None


class _OpenAICompatibleTextGenerationAdapter(CancelableTextGenerationStage):
    """Shared injected-client adapter for OpenAI-compatible chat streaming."""

    __slots__ = (
        "_provider",
        "_client",
        "_model",
        "_system_instruction",
        "_temperature",
        "_max_tokens",
        "_history",
        "_lock",
        "_closed",
        "_streams",
        "_capability",
    )

    def __init__(
        self,
        *,
        provider: str,
        client: object,
        model: str,
        system_instruction: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        if client is None:
            raise ValueError("client must be injected explicitly")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(system_instruction, str):
            raise TypeError("system_instruction must be a string")
        if temperature is not None and isinstance(temperature, bool):
            raise TypeError("temperature must be a number or None")
        if max_tokens is not None and (
            isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1
        ):
            raise ValueError("max_tokens must be a positive integer or None")

        self._provider = provider
        self._client = client
        self._model = model.strip()
        self._system_instruction = system_instruction
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._history = _TransactionalMessageHistory(
            system_instruction=system_instruction
        )
        self._lock = threading.RLock()
        self._closed = False
        self._streams: list[ProviderNeutralTextGenerationStream] = []
        self._capability = TextGenerationCapability(
            runtime=RuntimeCapabilityState(
                configured=True,
                runtime_available=True,
                unavailable_reason=None,
                public_metadata={
                    "provider": provider,
                    "client_injected": True,
                },
            ),
            streaming_supported=True,
            cooperative_cancel_supported=True,
            provider_hard_cancel_supported=False,
            public_metadata={
                "provider": provider,
                "provider_hard_cancel_verified": False,
            },
        )

    @property
    def stage_kind(self) -> RealtimeStageKind:
        return RealtimeStageKind.TEXT_GENERATION

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model

    def preflight(self) -> TextGenerationCapability:
        return self._capability

    def capability(self) -> TextGenerationCapability:
        return self._capability

    def _request_stream(self, messages: list[dict[str, str]]) -> Iterator[object]:
        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens
        try:
            stream = self._client.chat.completions.create(**kwargs)
        except Exception as error:
            raise TextGenerationProviderError.from_exception(
                error, provider=self._provider
            ) from None
        try:
            return iter(stream)
        except Exception as error:
            raise TextGenerationProviderError.from_exception(
                error, provider=self._provider
            ) from None

    def open_stream(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
        cancellation_token: TextGenerationCancellationToken,
    ) -> TextGenerationStream:
        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(request, RealtimeTurn):
            raise TypeError("request must be a RealtimeTurn")
        if not isinstance(cancellation_token, TextGenerationCancellationToken):
            raise TypeError(
                "cancellation_token must be a TextGenerationCancellationToken"
            )

        with self._lock:
            if self._closed:
                raise TextGenerationProviderError(
                    public_error_code="stage_closed",
                    safe_message="Text-generation provider stage is closed.",
                    retryable=False,
                    public_metadata={"provider": self._provider},
                )
            self._streams = [stream for stream in self._streams if not stream.closed]
            messages = self._history.snapshot_with_user(request.input_text)

        provider_stream = self._request_stream(messages)
        source = _OpenAICompatibleDeltaSource(
            provider=self._provider,
            stream=provider_stream,
        )
        stream = ProviderNeutralTextGenerationStream(
            context=context,
            capability=self._capability,
            source=source,
            user_input=request.input_text,
            cancellation_token=cancellation_token,
            history_sink=self._history,
        )
        with self._lock:
            if self._closed:
                stream.close()
                raise TextGenerationProviderError(
                    public_error_code="stage_closed",
                    safe_message="Text-generation provider stage is closed.",
                    retryable=False,
                    public_metadata={"provider": self._provider},
                )
            self._streams.append(stream)
        return stream

    def reset_history(self) -> None:
        with self._lock:
            if any(not stream.closed for stream in self._streams):
                raise RuntimeError(
                    "Text-generation history cannot reset while a stream is active."
                )
            self._history.reset(system_instruction=self._system_instruction)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            streams = tuple(self._streams)
        for stream in streams:
            stream.close()


class OpenAITextGenerationAdapter(_OpenAICompatibleTextGenerationAdapter):
    """Cancel-aware OpenAI adapter over an explicitly injected client."""

    def __init__(
        self,
        *,
        client: object,
        model: str,
        system_instruction: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(
            provider="openai",
            client=client,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class XAITextGenerationAdapter(_OpenAICompatibleTextGenerationAdapter):
    """Cancel-aware xAI adapter over an explicitly injected compatible client."""

    def __init__(
        self,
        *,
        client: object,
        model: str,
        system_instruction: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(
            provider="xai",
            client=client,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        )




class _GeminiDeltaSource:
    """Convert injected Gemini-compatible chunks to provider-neutral deltas."""

    __slots__ = (
        "_provider",
        "_stream",
        "_buffer",
        "_closed",
        "_source_exhausted",
        "_flush_emitted",
    )

    def __init__(self, *, provider: str, stream: Iterator[object]) -> None:
        if not hasattr(stream, "__next__"):
            try:
                stream = iter(stream)
            except TypeError as error:
                raise TextGenerationProviderError.from_exception(
                    error, provider=provider
                ) from None
        self._provider = provider
        self._stream = stream
        self._buffer = ""
        self._closed = False
        self._source_exhausted = False
        self._flush_emitted = False

    def __iter__(self) -> "_GeminiDeltaSource":
        return self

    @staticmethod
    def _chunk_text(chunk: object) -> str | None:
        try:
            if isinstance(chunk, Mapping):
                content = chunk.get("text")
            else:
                content = chunk.text
        except Exception as error:
            raise TextGenerationProviderError.from_exception(error) from None
        if content is None:
            return None
        if not isinstance(content, str):
            raise TextGenerationProviderError(
                public_error_code="provider_response_invalid",
                safe_message="Text-generation provider returned an invalid response.",
                retryable=False,
                public_metadata={"error_category": "invalid_provider_response"},
            )
        return content

    def __next__(self) -> tuple[str, tuple[str, ...]]:
        if self._closed:
            raise StopIteration

        while True:
            if self._source_exhausted:
                if self._buffer and not self._flush_emitted:
                    self._flush_emitted = True
                    buffer, self._buffer = self._buffer, ""
                    return _OpenAICompatibleDeltaSource._clean_buffer(buffer)
                raise StopIteration

            try:
                chunk = next(self._stream)
            except StopIteration:
                self._source_exhausted = True
                continue
            except TextGenerationProviderError:
                raise
            except Exception as error:
                raise TextGenerationProviderError.from_exception(
                    error, provider=self._provider
                ) from None

            try:
                content = self._chunk_text(chunk)
            except TextGenerationProviderError as error:
                if "provider" not in error.public_metadata:
                    raise TextGenerationProviderError(
                        public_error_code=error.public_error_code,
                        safe_message=error.safe_message,
                        retryable=error.retryable,
                        public_metadata={
                            **dict(error.public_metadata),
                            "provider": self._provider,
                        },
                    ) from None
                raise
            if not content:
                continue

            self._buffer += content
            if "[" in self._buffer:
                if "]" in self._buffer:
                    buffer, self._buffer = self._buffer, ""
                    return _OpenAICompatibleDeltaSource._clean_buffer(buffer)
                if len(self._buffer) > 100:
                    buffer, self._buffer = self._buffer, ""
                    return buffer, ()
                continue

            buffer, self._buffer = self._buffer, ""
            return buffer, ()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_method = getattr(self._stream, "close", None)
        if close_method is None:
            return
        try:
            close_method()
        except Exception as error:
            raise TextGenerationProviderError.from_exception(
                error, provider=self._provider
            ) from None


class GeminiTextGenerationAdapter(CancelableTextGenerationStage):
    """Cancel-aware Gemini adapter using stateless injected model streaming."""

    __slots__ = (
        "_client",
        "_model",
        "_system_instruction",
        "_temperature",
        "_max_output_tokens",
        "_history",
        "_lock",
        "_closed",
        "_streams",
        "_capability",
    )

    def __init__(
        self,
        *,
        client: object,
        model: str,
        system_instruction: str = "",
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        if client is None:
            raise ValueError("client must be injected explicitly")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(system_instruction, str):
            raise TypeError("system_instruction must be a string")
        if temperature is not None and isinstance(temperature, bool):
            raise TypeError("temperature must be a number or None")
        if max_output_tokens is not None and (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or max_output_tokens < 1
        ):
            raise ValueError("max_output_tokens must be a positive integer or None")

        self._client = client
        self._model = model.strip()
        self._system_instruction = system_instruction
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._history = _TransactionalMessageHistory(
            system_instruction=system_instruction
        )
        self._lock = threading.RLock()
        self._closed = False
        self._streams: list[ProviderNeutralTextGenerationStream] = []
        self._capability = TextGenerationCapability(
            runtime=RuntimeCapabilityState(
                configured=True,
                runtime_available=True,
                unavailable_reason=None,
                public_metadata={
                    "provider": "google",
                    "client_injected": True,
                    "stateless_request_history": True,
                },
            ),
            streaming_supported=True,
            cooperative_cancel_supported=True,
            provider_hard_cancel_supported=False,
            public_metadata={
                "provider": "google",
                "provider_hard_cancel_verified": False,
                "provider_owned_chat_state": False,
            },
        )

    @property
    def stage_kind(self) -> RealtimeStageKind:
        return RealtimeStageKind.TEXT_GENERATION

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def model_name(self) -> str:
        return self._model

    def preflight(self) -> TextGenerationCapability:
        return self._capability

    def capability(self) -> TextGenerationCapability:
        return self._capability

    @staticmethod
    def _to_gemini_contents(
        messages: Sequence[Mapping[str, str]],
    ) -> list[dict[str, object]]:
        contents: list[dict[str, object]] = []
        for message in messages:
            role = str(message["role"])
            if role == "system":
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": str(message["content"])}],
                }
            )
        return contents

    def _request_stream(
        self,
        contents: list[dict[str, object]],
    ) -> Iterator[object]:
        config: dict[str, object] = {}
        if self._system_instruction:
            config["system_instruction"] = self._system_instruction
        if self._temperature is not None:
            config["temperature"] = self._temperature
        if self._max_output_tokens is not None:
            config["max_output_tokens"] = self._max_output_tokens

        try:
            stream = self._client.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=config,
            )
        except Exception as error:
            raise TextGenerationProviderError.from_exception(
                error, provider="google"
            ) from None
        try:
            return iter(stream)
        except Exception as error:
            raise TextGenerationProviderError.from_exception(
                error, provider="google"
            ) from None

    def open_stream(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
        cancellation_token: TextGenerationCancellationToken,
    ) -> TextGenerationStream:
        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(request, RealtimeTurn):
            raise TypeError("request must be a RealtimeTurn")
        if not isinstance(cancellation_token, TextGenerationCancellationToken):
            raise TypeError(
                "cancellation_token must be a TextGenerationCancellationToken"
            )

        with self._lock:
            if self._closed:
                raise TextGenerationProviderError(
                    public_error_code="stage_closed",
                    safe_message="Text-generation provider stage is closed.",
                    retryable=False,
                    public_metadata={"provider": "google"},
                )
            self._streams = [stream for stream in self._streams if not stream.closed]
            messages = self._history.snapshot_with_user(request.input_text)

        provider_stream = self._request_stream(self._to_gemini_contents(messages))
        source = _GeminiDeltaSource(provider="google", stream=provider_stream)
        stream = ProviderNeutralTextGenerationStream(
            context=context,
            capability=self._capability,
            source=source,
            user_input=request.input_text,
            cancellation_token=cancellation_token,
            history_sink=self._history,
        )
        with self._lock:
            if self._closed:
                stream.close()
                raise TextGenerationProviderError(
                    public_error_code="stage_closed",
                    safe_message="Text-generation provider stage is closed.",
                    retryable=False,
                    public_metadata={"provider": "google"},
                )
            self._streams.append(stream)
        return stream

    def reset_history(self) -> None:
        with self._lock:
            if any(not stream.closed for stream in self._streams):
                raise RuntimeError(
                    "Text-generation history cannot reset while a stream is active."
                )
            self._history.reset(system_instruction=self._system_instruction)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            streams = tuple(self._streams)
        for stream in streams:
            stream.close()


def _minimum_text_generation_capability(
    stages: Sequence[CancelableTextGenerationStage],
    *,
    provider: str,
) -> TextGenerationCapability:
    if not stages:
        raise ValueError("at least one text-generation stage is required")
    capabilities = tuple(stage.capability() for stage in stages)
    if not all(isinstance(capability, TextGenerationCapability) for capability in capabilities):
        raise TypeError("all stages must return TextGenerationCapability")

    runtime_states = tuple(capability.runtime for capability in capabilities)
    configured = all(state.configured for state in runtime_states)
    runtime_available = all(state.runtime_available for state in runtime_states)
    guarded = any(state.guarded for state in runtime_states)
    fake_runtime = all(state.fake_runtime for state in runtime_states)
    real_runtime = all(state.real_runtime for state in runtime_states)
    unavailable_reason = (
        None
        if configured and runtime_available and not guarded
        else "composite_runtime_not_guaranteed"
    )
    return TextGenerationCapability(
        runtime=RuntimeCapabilityState(
            configured=configured,
            runtime_available=runtime_available,
            guarded=guarded,
            fake_runtime=fake_runtime,
            real_runtime=real_runtime,
            unavailable_reason=unavailable_reason,
            public_metadata={
                "provider": provider,
                "candidate_count": len(capabilities),
            },
        ),
        streaming_supported=all(
            capability.streaming_supported for capability in capabilities
        ),
        cooperative_cancel_supported=all(
            capability.cooperative_cancel_supported for capability in capabilities
        ),
        provider_hard_cancel_supported=all(
            capability.provider_hard_cancel_supported for capability in capabilities
        ),
        public_metadata={
            "provider": provider,
            "provider_hard_cancel_verified": all(
                capability.provider_hard_cancel_supported
                for capability in capabilities
            ),
            "capability_mode": "conservative_minimum",
        },
    )


def _ensure_child_stream_contract(
    stream: TextGenerationStream,
    *,
    context: RealtimeStageContext,
    cancellation_token: TextGenerationCancellationToken,
) -> None:
    if not isinstance(stream, TextGenerationStream):
        raise TextGenerationProviderError(
            public_error_code="provider_response_invalid",
            safe_message="Text-generation stage returned an invalid stream.",
            retryable=False,
            public_metadata={"error_category": "invalid_stream"},
        )
    if stream.context != context:
        stream.close()
        raise TextGenerationProviderError(
            public_error_code="provider_response_invalid",
            safe_message="Text-generation stage returned an invalid stream context.",
            retryable=False,
            public_metadata={"error_category": "stream_context_mismatch"},
        )
    if stream.cancellation_token is not cancellation_token:
        stream.close()
        raise TextGenerationProviderError(
            public_error_code="provider_response_invalid",
            safe_message="Text-generation stage returned an invalid cancellation token.",
            retryable=False,
            public_metadata={"error_category": "stream_token_mismatch"},
        )


class _DelegatingTextGenerationStream(TextGenerationStream):
    """Expose one selected child stream under a composite stage capability."""

    __slots__ = (
        "_context",
        "_capability",
        "_cancellation_token",
        "_child",
        "_closed",
        "_expected_index",
        "_lock",
    )

    def __init__(
        self,
        *,
        context: RealtimeStageContext,
        capability: TextGenerationCapability,
        cancellation_token: TextGenerationCancellationToken,
        child: TextGenerationStream,
    ) -> None:
        _ensure_child_stream_contract(
            child,
            context=context,
            cancellation_token=cancellation_token,
        )
        self._context = context
        self._capability = capability
        self._cancellation_token = cancellation_token
        self._child = child
        self._closed = False
        self._expected_index = 0
        self._lock = threading.RLock()

    @property
    def context(self) -> RealtimeStageContext:
        return self._context

    @property
    def capability(self) -> TextGenerationCapability:
        return self._capability

    @property
    def cancellation_token(self) -> TextGenerationCancellationToken:
        return self._cancellation_token

    def __iter__(self) -> "_DelegatingTextGenerationStream":
        return self

    def __next__(self) -> TextGenerationDeltaEnvelope:
        with self._lock:
            if self._closed:
                raise StopIteration
            try:
                delta = next(self._child)
            except StopIteration:
                self._closed = True
                raise
            if not isinstance(delta, TextGenerationDeltaEnvelope):
                self._closed = True
                self._child.close()
                raise TextGenerationProviderError(
                    public_error_code="provider_response_invalid",
                    safe_message="Text-generation stage returned an invalid delta.",
                    retryable=False,
                    public_metadata={"error_category": "invalid_stream_delta"},
                )
            if delta.context != self._context or delta.delta_index != self._expected_index:
                self._closed = True
                self._child.close()
                raise TextGenerationProviderError(
                    public_error_code="provider_response_invalid",
                    safe_message="Text-generation stage returned an invalid correlated delta.",
                    retryable=False,
                    public_metadata={"error_category": "invalid_delta_correlation"},
                )
            self._expected_index += 1
            return delta

    def request_cancel(self, reason: TextGenerationCancelReason | str) -> bool:
        return self._child.request_cancel(reason)

    def close(self) -> TextGenerationStreamCloseResult:
        with self._lock:
            if self._closed:
                return TextGenerationStreamCloseResult(
                    TextGenerationStreamCloseOutcome.ALREADY_CLOSED
                )
            self._closed = True
            return self._child.close()

    def dispose(self) -> TextGenerationStreamCloseResult:
        return self.close()


class _FallbackTextGenerationStream(TextGenerationStream):
    """Switch once to fallback only when primary fails before any delivered delta."""

    __slots__ = (
        "_context",
        "_request",
        "_capability",
        "_cancellation_token",
        "_fallback_stage",
        "_active_stream",
        "_active_is_primary",
        "_fallback_started",
        "_delivered_delta_count",
        "_expected_index",
        "_closed",
        "_lock",
    )

    def __init__(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
        capability: TextGenerationCapability,
        cancellation_token: TextGenerationCancellationToken,
        fallback_stage: CancelableTextGenerationStage,
        active_stream: TextGenerationStream,
        active_is_primary: bool,
        fallback_started: bool,
    ) -> None:
        _ensure_child_stream_contract(
            active_stream,
            context=context,
            cancellation_token=cancellation_token,
        )
        self._context = context
        self._request = request
        self._capability = capability
        self._cancellation_token = cancellation_token
        self._fallback_stage = fallback_stage
        self._active_stream = active_stream
        self._active_is_primary = bool(active_is_primary)
        self._fallback_started = bool(fallback_started)
        self._delivered_delta_count = 0
        self._expected_index = 0
        self._closed = False
        self._lock = threading.RLock()

    @property
    def context(self) -> RealtimeStageContext:
        return self._context

    @property
    def capability(self) -> TextGenerationCapability:
        return self._capability

    @property
    def cancellation_token(self) -> TextGenerationCancellationToken:
        return self._cancellation_token

    @property
    def fallback_started(self) -> bool:
        return self._fallback_started

    def __iter__(self) -> "_FallbackTextGenerationStream":
        return self

    @staticmethod
    def _safe_error(error: BaseException) -> TextGenerationProviderError:
        if isinstance(error, TextGenerationProviderError):
            return error
        return TextGenerationProviderError.from_exception(error, provider="fallback")

    def _start_fallback(self) -> None:
        try:
            stream = self._fallback_stage.open_stream(
                context=self._context,
                request=self._request,
                cancellation_token=self._cancellation_token,
            )
        except Exception as error:
            raise self._safe_error(error) from None
        _ensure_child_stream_contract(
            stream,
            context=self._context,
            cancellation_token=self._cancellation_token,
        )
        self._active_stream = stream
        self._active_is_primary = False
        self._fallback_started = True
        self._expected_index = 0

    def __next__(self) -> TextGenerationDeltaEnvelope:
        with self._lock:
            while True:
                if self._closed:
                    raise StopIteration
                if self._cancellation_token.cancel_requested:
                    self._closed = True
                    self._active_stream.close()
                    raise StopIteration
                try:
                    delta = next(self._active_stream)
                except StopIteration:
                    self._closed = True
                    raise
                except Exception as error:
                    self._active_stream.close()
                    may_fallback = (
                        self._active_is_primary
                        and not self._fallback_started
                        and self._delivered_delta_count == 0
                        and not self._cancellation_token.cancel_requested
                    )
                    if may_fallback:
                        self._start_fallback()
                        continue
                    self._closed = True
                    raise self._safe_error(error) from None

                if not isinstance(delta, TextGenerationDeltaEnvelope):
                    self._closed = True
                    self._active_stream.close()
                    raise TextGenerationProviderError(
                        public_error_code="provider_response_invalid",
                        safe_message="Text-generation stage returned an invalid delta.",
                        retryable=False,
                        public_metadata={"provider": "fallback"},
                    )
                if delta.context != self._context or delta.delta_index != self._expected_index:
                    self._closed = True
                    self._active_stream.close()
                    raise TextGenerationProviderError(
                        public_error_code="provider_response_invalid",
                        safe_message="Text-generation stage returned an invalid correlated delta.",
                        retryable=False,
                        public_metadata={"provider": "fallback"},
                    )
                self._expected_index += 1
                self._delivered_delta_count += 1
                return delta

    def request_cancel(self, reason: TextGenerationCancelReason | str) -> bool:
        return self._active_stream.request_cancel(reason)

    def close(self) -> TextGenerationStreamCloseResult:
        with self._lock:
            if self._closed:
                return TextGenerationStreamCloseResult(
                    TextGenerationStreamCloseOutcome.ALREADY_CLOSED
                )
            self._closed = True
            return self._active_stream.close()

    def dispose(self) -> TextGenerationStreamCloseResult:
        return self.close()


def _cancelled_empty_stream(
    *,
    context: RealtimeStageContext,
    request: RealtimeTurn,
    capability: TextGenerationCapability,
    cancellation_token: TextGenerationCancellationToken,
) -> TextGenerationStream:
    return ProviderNeutralTextGenerationStream(
        context=context,
        capability=capability,
        source=iter(()),
        user_input=request.input_text,
        cancellation_token=cancellation_token,
        history_sink=None,
    )


class FallbackTextGenerationAdapter(CancelableTextGenerationStage):
    """Provider-neutral fallback with pre-delta-only failover."""

    __slots__ = ("_primary", "_fallback", "_capability", "_lock", "_closed")

    def __init__(
        self,
        *,
        primary: CancelableTextGenerationStage,
        fallback: CancelableTextGenerationStage,
    ) -> None:
        if not isinstance(primary, CancelableTextGenerationStage):
            raise TypeError("primary must implement CancelableTextGenerationStage")
        if not isinstance(fallback, CancelableTextGenerationStage):
            raise TypeError("fallback must implement CancelableTextGenerationStage")
        self._primary = primary
        self._fallback = fallback
        self._capability = _minimum_text_generation_capability(
            (primary, fallback),
            provider="fallback",
        )
        self._lock = threading.RLock()
        self._closed = False

    @property
    def stage_kind(self) -> RealtimeStageKind:
        return RealtimeStageKind.TEXT_GENERATION

    def preflight(self) -> TextGenerationCapability:
        return self._capability

    def capability(self) -> TextGenerationCapability:
        return self._capability

    def open_stream(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
        cancellation_token: TextGenerationCancellationToken,
    ) -> TextGenerationStream:
        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(request, RealtimeTurn):
            raise TypeError("request must be a RealtimeTurn")
        if not isinstance(cancellation_token, TextGenerationCancellationToken):
            raise TypeError(
                "cancellation_token must be a TextGenerationCancellationToken"
            )
        with self._lock:
            if self._closed:
                raise TextGenerationProviderError(
                    public_error_code="stage_closed",
                    safe_message="Text-generation fallback stage is closed.",
                    retryable=False,
                    public_metadata={"provider": "fallback"},
                )

        if cancellation_token.cancel_requested:
            return _cancelled_empty_stream(
                context=context,
                request=request,
                capability=self._capability,
                cancellation_token=cancellation_token,
            )

        try:
            primary_stream = self._primary.open_stream(
                context=context,
                request=request,
                cancellation_token=cancellation_token,
            )
        except Exception as error:
            if cancellation_token.cancel_requested:
                return _cancelled_empty_stream(
                    context=context,
                    request=request,
                    capability=self._capability,
                    cancellation_token=cancellation_token,
                )
            try:
                fallback_stream = self._fallback.open_stream(
                    context=context,
                    request=request,
                    cancellation_token=cancellation_token,
                )
            except Exception as fallback_error:
                if isinstance(fallback_error, TextGenerationProviderError):
                    raise fallback_error
                raise TextGenerationProviderError.from_exception(
                    fallback_error, provider="fallback"
                ) from None
            return _FallbackTextGenerationStream(
                context=context,
                request=request,
                capability=self._capability,
                cancellation_token=cancellation_token,
                fallback_stage=self._fallback,
                active_stream=fallback_stream,
                active_is_primary=False,
                fallback_started=True,
            )

        return _FallbackTextGenerationStream(
            context=context,
            request=request,
            capability=self._capability,
            cancellation_token=cancellation_token,
            fallback_stage=self._fallback,
            active_stream=primary_stream,
            active_is_primary=True,
            fallback_started=False,
        )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        errors: list[BaseException] = []
        for stage in (self._primary, self._fallback):
            try:
                stage.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise RuntimeError("Text-generation fallback stage cleanup failed.")


class RouterTextGenerationAdapter(CancelableTextGenerationStage):
    """Select one child route once and preserve one context/token for the stream."""

    __slots__ = ("_routes", "_route_selector", "_capability", "_lock", "_closed")

    def __init__(
        self,
        *,
        routes: Mapping[str, CancelableTextGenerationStage],
        route_selector: Callable[[RealtimeTurn], str],
    ) -> None:
        if not isinstance(routes, Mapping) or not routes:
            raise ValueError("routes must be a non-empty mapping")
        if not callable(route_selector):
            raise TypeError("route_selector must be callable")

        normalized: dict[str, CancelableTextGenerationStage] = {}
        for raw_name, stage in routes.items():
            name = str(raw_name).strip()
            if not name:
                raise ValueError("route names must be non-empty strings")
            if name in normalized:
                raise ValueError("route names must be unique")
            if not isinstance(stage, CancelableTextGenerationStage):
                raise TypeError("route values must implement CancelableTextGenerationStage")
            normalized[name] = stage

        self._routes = normalized
        self._route_selector = route_selector
        self._capability = _minimum_text_generation_capability(
            tuple(normalized.values()),
            provider="router",
        )
        self._lock = threading.RLock()
        self._closed = False

    @property
    def stage_kind(self) -> RealtimeStageKind:
        return RealtimeStageKind.TEXT_GENERATION

    def preflight(self) -> TextGenerationCapability:
        return self._capability

    def capability(self) -> TextGenerationCapability:
        return self._capability

    def open_stream(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
        cancellation_token: TextGenerationCancellationToken,
    ) -> TextGenerationStream:
        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(request, RealtimeTurn):
            raise TypeError("request must be a RealtimeTurn")
        if not isinstance(cancellation_token, TextGenerationCancellationToken):
            raise TypeError(
                "cancellation_token must be a TextGenerationCancellationToken"
            )
        with self._lock:
            if self._closed:
                raise TextGenerationProviderError(
                    public_error_code="stage_closed",
                    safe_message="Text-generation router stage is closed.",
                    retryable=False,
                    public_metadata={"provider": "router"},
                )

        if cancellation_token.cancel_requested:
            return _cancelled_empty_stream(
                context=context,
                request=request,
                capability=self._capability,
                cancellation_token=cancellation_token,
            )

        try:
            route = self._route_selector(request)
        except Exception:
            raise TextGenerationProviderError(
                public_error_code="route_selection_failed",
                safe_message="Text-generation route selection failed.",
                retryable=False,
                public_metadata={"provider": "router"},
            ) from None
        if not isinstance(route, str) or route not in self._routes:
            raise TextGenerationProviderError(
                public_error_code="route_unavailable",
                safe_message="The selected text-generation route is unavailable.",
                retryable=False,
                public_metadata={"provider": "router"},
            )

        stage = self._routes[route]
        try:
            child = stage.open_stream(
                context=context,
                request=request,
                cancellation_token=cancellation_token,
            )
        except TextGenerationProviderError:
            raise
        except Exception as error:
            raise TextGenerationProviderError.from_exception(
                error, provider="router"
            ) from None

        return _DelegatingTextGenerationStream(
            context=context,
            capability=self._capability,
            cancellation_token=cancellation_token,
            child=child,
        )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            stages = tuple(dict.fromkeys(id(stage) for stage in self._routes.values()))
        seen: set[int] = set()
        errors: list[BaseException] = []
        for stage in self._routes.values():
            identity = id(stage)
            if identity in seen:
                continue
            seen.add(identity)
            try:
                stage.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise RuntimeError("Text-generation router stage cleanup failed.")


__all__ = [
    "OpenAITextGenerationAdapter",
    "XAITextGenerationAdapter",
    "GeminiTextGenerationAdapter",
    "FallbackTextGenerationAdapter",
    "RouterTextGenerationAdapter",
]
