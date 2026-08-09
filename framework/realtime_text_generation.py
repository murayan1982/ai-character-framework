"""Provider-neutral cancel-aware text-generation model primitives for v6.

FW-RT6-5a defines the stable model, stream, and additive stage vocabulary
used by later provider adapters and session orchestration. Importing this module must not
load provider SDKs, execute providers, perform network access, inspect private
configuration, access a microphone, perform playback, or connect to VTube
Studio.

The module is an explicitly importable stable public package but is not added
to the ``framework`` root-public manifest in Control A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import threading
from typing import Iterator, Mapping, Protocol, Sequence, runtime_checkable

from .identity import GenerationId, SessionId, TurnId
from .public_safety import (
    classify_public_exception,
    public_mapping,
    sanitize_public_value,
)
from .realtime import RealtimeTurn
from .realtime_capabilities import TextGenerationCapability
from .realtime_generation_gate import (
    RealtimeGenerationGate,
    RealtimeStageCompletionEnvelope,
)
from .realtime_stage import RealtimeStageContext, RealtimeStageKind




class TextGenerationProviderError(RuntimeError):
    """Public-safe typed provider failure for cancel-aware text generation.

    Raw provider exception text, repr, payloads, request data, credentials, and
    private endpoint details are intentionally not retained.
    """

    __slots__ = (
        "public_error_code",
        "safe_message",
        "retryable",
        "public_metadata",
    )

    def __init__(
        self,
        *,
        public_error_code: str,
        safe_message: str,
        retryable: bool = False,
        public_metadata: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(public_error_code, str) or not public_error_code.strip():
            raise ValueError("public_error_code must be a non-empty string")
        if not isinstance(safe_message, str) or not safe_message.strip():
            raise ValueError("safe_message must be a non-empty string")
        safe = sanitize_public_value(safe_message.strip())
        if not isinstance(safe, str) or not safe.strip():
            safe = "Text-generation provider request failed."
        self.public_error_code = public_error_code.strip()
        self.safe_message = safe
        self.retryable = bool(retryable)
        self.public_metadata = public_mapping(public_metadata)
        RuntimeError.__init__(self, self.safe_message)

    @classmethod
    def from_exception(
        cls,
        error: BaseException,
        *,
        provider: str | None = None,
    ) -> "TextGenerationProviderError":
        """Map one provider failure without retaining raw exception detail."""

        classification = classify_public_exception(
            error,
            fallback_error_code="provider_request_failed",
            fallback_safe_message="Text-generation provider request failed.",
            fallback_retryable=True,
        )
        metadata = dict(classification.public_metadata)
        if provider is not None:
            metadata["provider"] = str(provider).strip().lower()
        return cls(
            public_error_code=classification.public_error_code,
            safe_message=classification.safe_message,
            retryable=classification.retryable,
            public_metadata=metadata,
        )


class TextGenerationCancelReason(str, Enum):
    """Stable cooperative-cancellation reason for one text-generation stream."""

    HOST_REQUEST = "host_request"
    INTERRUPT = "interrupt"
    TURN_CANCELLED = "turn_cancelled"
    SESSION_CLOSED = "session_closed"
    RESET = "reset"


class TextGenerationCancellationToken:
    """Thread-safe one-way cooperative cancellation token.

    The first accepted cancellation request fixes the reason permanently.
    Duplicate requests are idempotent and return ``False``. Acceptance of this
    token does not claim that an underlying provider transport was hard-cancelled.
    """

    __slots__ = ("_lock", "_reason")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reason: TextGenerationCancelReason | None = None

    @property
    def cancel_requested(self) -> bool:
        with self._lock:
            return self._reason is not None

    @property
    def reason(self) -> TextGenerationCancelReason | None:
        with self._lock:
            return self._reason

    def request_cancel(self, reason: TextGenerationCancelReason | str) -> bool:
        with self._lock:
            if self._reason is not None:
                return False
            resolved_reason = (
                reason
                if isinstance(reason, TextGenerationCancelReason)
                else TextGenerationCancelReason(str(reason))
            )
            self._reason = resolved_reason
            return True


@dataclass(frozen=True, slots=True)
class TextGenerationDeltaEnvelope:
    """Generation-correlated text delta delivered by a cancel-aware stream."""

    context: RealtimeStageContext
    delta_index: int
    text: str = field(repr=False)
    emotion_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if isinstance(self.delta_index, bool) or not isinstance(self.delta_index, int):
            raise TypeError("delta_index must be an integer")
        if self.delta_index < 0:
            raise ValueError("delta_index must be at least 0")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if isinstance(self.emotion_tags, str):
            raise TypeError("emotion_tags must be a sequence of strings")
        try:
            normalized_tags = tuple(self.emotion_tags)
        except TypeError as error:
            raise TypeError("emotion_tags must be a sequence of strings") from error
        if not all(isinstance(tag, str) for tag in normalized_tags):
            raise TypeError("emotion_tags must contain only strings")
        object.__setattr__(self, "emotion_tags", normalized_tags)

    @property
    def session_id(self) -> SessionId | str:
        return self.context.session_id

    @property
    def turn_id(self) -> TurnId | str:
        return self.context.turn_id

    @property
    def generation_id(self) -> GenerationId:
        return self.context.generation_id


class TextGenerationStreamCloseOutcome(str, Enum):
    """Stable public close/dispose classification for one stream handle."""

    CLOSED = "closed"
    ALREADY_CLOSED = "already_closed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TextGenerationStreamCloseResult:
    """Public-safe typed result of stream close/dispose cleanup."""

    outcome: TextGenerationStreamCloseOutcome | str
    safe_message: str = ""
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, TextGenerationStreamCloseOutcome)
            else TextGenerationStreamCloseOutcome(str(self.outcome))
        )
        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")
        safe_message = sanitize_public_value(self.safe_message)
        if not isinstance(safe_message, str):
            raise TypeError("safe_message must normalize to public-safe text")
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "safe_message", safe_message)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))


@dataclass(frozen=True, slots=True)
class TextGenerationCompletedTurn:
    """One atomic completed conversation-history commit unit."""

    context: RealtimeStageContext
    user_input: str = field(repr=False)
    assistant_output: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(self.user_input, str):
            raise TypeError("user_input must be a string")
        if not isinstance(self.assistant_output, str):
            raise TypeError("assistant_output must be a string")


@runtime_checkable
class TextGenerationHistorySink(Protocol):
    """Atomic sink for one completed user + assistant history pair."""

    def commit_completed_turn(self, turn: TextGenerationCompletedTurn) -> None:
        ...


@runtime_checkable
class TextGenerationStream(Protocol):
    """Provider-neutral cancel-aware text-generation stream handle."""

    @property
    def context(self) -> RealtimeStageContext:
        ...

    @property
    def capability(self) -> TextGenerationCapability:
        ...

    @property
    def cancellation_token(self) -> TextGenerationCancellationToken:
        ...

    def __iter__(self) -> Iterator[TextGenerationDeltaEnvelope]:
        ...

    def request_cancel(self, reason: TextGenerationCancelReason | str) -> bool:
        ...

    def close(self) -> TextGenerationStreamCloseResult:
        ...

    def dispose(self) -> TextGenerationStreamCloseResult:
        ...


@runtime_checkable
class CancelableTextGenerationStage(Protocol):
    """Additive cancel-aware text-generation stage protocol.

    This companion does not replace or mutate
    :class:`framework.realtime_stage.TextGenerationStage`.  It opens a
    generation-correlated stream handle and delegates cooperative cancellation
    to the supplied token / returned stream.
    """

    @property
    def stage_kind(self) -> RealtimeStageKind:
        ...

    def preflight(self) -> TextGenerationCapability:
        ...

    def capability(self) -> TextGenerationCapability:
        ...

    def open_stream(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
        cancellation_token: TextGenerationCancellationToken,
    ) -> TextGenerationStream:
        ...

    def close(self) -> None:
        ...


class ProviderNeutralTextGenerationStream:
    """Reference cancel-aware stream over a provider-neutral source iterator.

    The source yields legacy-compatible ``(text, emotion_tags)`` pairs. This
    wrapper owns correlation/indexing, cooperative future-delta suppression,
    at-most-once iterator cleanup, and exactly-once completed-history commit.
    An optional common generation gate atomically guards the final delta-state
    application before the envelope leaves the stream. It does not claim
    provider transport hard cancellation.
    """

    __slots__ = (
        "_context",
        "_capability",
        "_cancellation_token",
        "_source",
        "_user_input",
        "_history_sink",
        "_generation_gate",
        "_iteration_lock",
        "_state_lock",
        "_closed",
        "_completed",
        "_source_cleanup_attempted",
        "_history_committed",
        "_next_delta_index",
        "_assistant_parts",
    )

    def __init__(
        self,
        *,
        context: RealtimeStageContext,
        capability: TextGenerationCapability,
        source: Iterator[tuple[str, Sequence[str]]],
        user_input: str,
        cancellation_token: TextGenerationCancellationToken | None = None,
        history_sink: TextGenerationHistorySink | None = None,
        generation_gate: RealtimeGenerationGate | None = None,
    ) -> None:
        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(capability, TextGenerationCapability):
            raise TypeError("capability must be a TextGenerationCapability")
        if not isinstance(user_input, str):
            raise TypeError("user_input must be a string")
        if cancellation_token is not None and not isinstance(
            cancellation_token, TextGenerationCancellationToken
        ):
            raise TypeError(
                "cancellation_token must be a TextGenerationCancellationToken or None"
            )
        if not hasattr(source, "__next__"):
            raise TypeError("source must be an iterator")
        if history_sink is not None and not isinstance(history_sink, TextGenerationHistorySink):
            raise TypeError("history_sink must implement TextGenerationHistorySink")
        if generation_gate is not None and not isinstance(
            generation_gate,
            RealtimeGenerationGate,
        ):
            raise TypeError("generation_gate must be a RealtimeGenerationGate or None")

        self._context = context
        self._capability = capability
        self._cancellation_token = cancellation_token or TextGenerationCancellationToken()
        self._source = source
        self._user_input = user_input
        self._history_sink = history_sink
        self._generation_gate = generation_gate
        self._iteration_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._closed = False
        self._completed = False
        self._source_cleanup_attempted = False
        self._history_committed = False
        self._next_delta_index = 0
        self._assistant_parts: list[str] = []

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
    def closed(self) -> bool:
        with self._state_lock:
            return self._closed

    @property
    def completed(self) -> bool:
        with self._state_lock:
            return self._completed

    @property
    def history_committed(self) -> bool:
        with self._state_lock:
            return self._history_committed

    @property
    def delivered_delta_count(self) -> int:
        with self._state_lock:
            return self._next_delta_index

    def __iter__(self) -> "ProviderNeutralTextGenerationStream":
        return self

    @staticmethod
    def _normalize_source_delta(
        value: object,
    ) -> tuple[str, tuple[str, ...]]:
        if not isinstance(value, tuple) or len(value) != 2:
            raise TypeError("source delta must be a (text, emotion_tags) tuple")
        text, emotion_tags = value
        if not isinstance(text, str):
            raise TypeError("source delta text must be a string")
        if isinstance(emotion_tags, str):
            raise TypeError("source delta emotion_tags must be a sequence of strings")
        try:
            normalized_tags = tuple(emotion_tags)
        except TypeError as error:
            raise TypeError(
                "source delta emotion_tags must be a sequence of strings"
            ) from error
        if not all(isinstance(tag, str) for tag in normalized_tags):
            raise TypeError("source delta emotion_tags must contain only strings")
        return text, normalized_tags

    def _apply_generation_delta_locked(
        self,
        delta: TextGenerationDeltaEnvelope,
    ) -> None:
        """Apply one admitted delta while the stream state lock is held."""

        self._assistant_parts.append(delta.text)
        self._next_delta_index += 1

    def _cleanup_source_once(self) -> TextGenerationStreamCloseResult:
        with self._state_lock:
            if self._source_cleanup_attempted:
                return TextGenerationStreamCloseResult(
                    TextGenerationStreamCloseOutcome.ALREADY_CLOSED
                )
            self._source_cleanup_attempted = True

        close_method = getattr(self._source, "close", None)
        if close_method is None:
            return TextGenerationStreamCloseResult(
                TextGenerationStreamCloseOutcome.CLOSED
            )
        try:
            close_method()
        except Exception:
            return TextGenerationStreamCloseResult(
                TextGenerationStreamCloseOutcome.FAILED,
                safe_message="Text-generation stream cleanup failed.",
            )
        return TextGenerationStreamCloseResult(TextGenerationStreamCloseOutcome.CLOSED)

    def _commit_completed_history_once(self) -> None:
        sink = self._history_sink
        if sink is None:
            return
        with self._state_lock:
            if self._history_committed:
                return
            completed_turn = TextGenerationCompletedTurn(
                context=self._context,
                user_input=self._user_input,
                assistant_output="".join(self._assistant_parts),
            )
        try:
            sink.commit_completed_turn(completed_turn)
        except Exception as error:
            with self._state_lock:
                self._closed = True
            raise RuntimeError("Text-generation history commit failed.") from error
        with self._state_lock:
            self._history_committed = True

    def __next__(self) -> TextGenerationDeltaEnvelope:
        with self._iteration_lock:
            with self._state_lock:
                if self._closed or self._completed:
                    raise StopIteration
            if self._cancellation_token.cancel_requested:
                with self._state_lock:
                    self._closed = True
                self._cleanup_source_once()
                raise StopIteration

            try:
                raw_delta = next(self._source)
            except StopIteration:
                cleanup_result = self._cleanup_source_once()
                if cleanup_result.outcome is TextGenerationStreamCloseOutcome.FAILED:
                    with self._state_lock:
                        self._closed = True
                    raise RuntimeError("Text-generation stream cleanup failed.")
                self._commit_completed_history_once()
                with self._state_lock:
                    self._completed = True
                    self._closed = True
                raise
            except Exception:
                with self._state_lock:
                    self._closed = True
                self._cleanup_source_once()
                raise

            if self._cancellation_token.cancel_requested:
                with self._state_lock:
                    self._closed = True
                self._cleanup_source_once()
                raise StopIteration

            try:
                text, emotion_tags = self._normalize_source_delta(raw_delta)
            except Exception:
                with self._state_lock:
                    self._closed = True
                self._cleanup_source_once()
                raise

            delta: TextGenerationDeltaEnvelope | None = None
            with self._state_lock:
                if self._closed or self._cancellation_token.cancel_requested:
                    self._closed = True
                    suppress = True
                else:
                    suppress = False
                    delta_index = self._next_delta_index
                    delta = TextGenerationDeltaEnvelope(
                        context=self._context,
                        delta_index=delta_index,
                        text=text,
                        emotion_tags=emotion_tags,
                    )
                    generation_gate = self._generation_gate
                    if generation_gate is None:
                        self._next_delta_index += 1
                        self._assistant_parts.append(text)
                    else:
                        decision = generation_gate.apply_completion(
                            RealtimeStageCompletionEnvelope(
                                turn_id=self._context.turn_id,
                                generation_id=self._context.generation_id,
                                stage="text_generation_delta",
                                value=delta,
                            ),
                            deliver=self._apply_generation_delta_locked,
                        )
                        if not decision.accepted:
                            self._closed = True
                            suppress = True
            if suppress:
                self._cleanup_source_once()
                raise StopIteration

            if delta is None:
                raise AssertionError("accepted text delta must be constructed")
            return delta

    def request_cancel(self, reason: TextGenerationCancelReason | str) -> bool:
        with self._state_lock:
            if self._closed or self._completed:
                return False
        return self._cancellation_token.request_cancel(reason)

    def close(self) -> TextGenerationStreamCloseResult:
        with self._iteration_lock:
            with self._state_lock:
                if self._closed:
                    return TextGenerationStreamCloseResult(
                        TextGenerationStreamCloseOutcome.ALREADY_CLOSED
                    )
                self._closed = True
            return self._cleanup_source_once()

    def dispose(self) -> TextGenerationStreamCloseResult:
        return self.close()


__all__ = [
    "TextGenerationCancelReason",
    "TextGenerationCancellationToken",
    "TextGenerationDeltaEnvelope",
    "TextGenerationStreamCloseOutcome",
    "TextGenerationStreamCloseResult",
    "TextGenerationCompletedTurn",
    "TextGenerationHistorySink",
    "TextGenerationStream",
    "ProviderNeutralTextGenerationStream",
    "CancelableTextGenerationStage",
    "TextGenerationProviderError",
]
