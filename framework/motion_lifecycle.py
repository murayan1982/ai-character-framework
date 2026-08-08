"""Provider-neutral lifecycle-to-motion extension contract.

FW-RT6-8b Control A defines a stable explicit package for host/plugin motion
mapping.  It contains models and a safe hook invocation boundary only.  It does
not adopt the hook in ``RealtimeSession``, execute a motion stage, import a
provider SDK, connect to VTube Studio, or change an existing motion session.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from .identity import (
    EventSequence,
    GenerationId,
    SessionId,
    TurnId,
    normalize_session_id,
    normalize_turn_id,
)
from .lifecycle import TurnOutcome
from .motion import MotionRequest
from .public_safety import REDACTED_PATH, public_mapping, sanitize_public_value


class MotionLifecycleSignal(str, Enum):
    """Lifecycle notifications eligible for host/plugin motion mapping."""

    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"


_TRANSIENT_SIGNALS = frozenset(
    {
        MotionLifecycleSignal.LISTENING,
        MotionLifecycleSignal.THINKING,
        MotionLifecycleSignal.SPEAKING,
    }
)
_TERMINAL_OUTCOMES_BY_SIGNAL = {
    MotionLifecycleSignal.INTERRUPTED: frozenset(
        {TurnOutcome.INTERRUPTED, TurnOutcome.CANCELLED}
    ),
    MotionLifecycleSignal.COMPLETED: frozenset({TurnOutcome.COMPLETED}),
    MotionLifecycleSignal.FAILED: frozenset({TurnOutcome.FAILED}),
}


def _required_session_id(value: SessionId | str) -> SessionId | str:
    normalized = normalize_session_id(value)
    if normalized is None:
        raise ValueError("session_id must identify one realtime session")
    return normalized


def _required_turn_id(value: TurnId | str) -> TurnId | str:
    normalized = normalize_turn_id(value)
    if normalized is None:
        raise ValueError("turn_id must identify one admitted realtime turn")
    return normalized


def _required_generation_id(value: GenerationId | str) -> GenerationId:
    if isinstance(value, GenerationId):
        return value
    if not isinstance(value, str):
        raise TypeError("generation_id must be a GenerationId or serialized string")
    return GenerationId.parse(value)


def _safe_message(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("safe_message must be a string")
    sanitized = sanitize_public_value(value.strip())
    if not isinstance(sanitized, str) or sanitized == REDACTED_PATH:
        return "Motion lifecycle hook processing failed safely."
    return sanitized


@dataclass(frozen=True, slots=True)
class MotionLifecycleNotification:
    """One sequenced lifecycle signal with unified turn correlation.

    The notification is constructed from an already accepted canonical
    lifecycle event.  Transient signals have no terminal outcome.  Terminal
    signals retain the accepted ``TurnOutcome`` without redefining terminal
    values as ``RealtimePhase`` members.
    """

    signal: MotionLifecycleSignal | str
    session_id: SessionId | str
    turn_id: TurnId | str
    generation_id: GenerationId | str
    source_sequence: EventSequence | int
    outcome: TurnOutcome | str | None = None
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        signal = (
            self.signal
            if isinstance(self.signal, MotionLifecycleSignal)
            else MotionLifecycleSignal(str(self.signal))
        )
        outcome = self.outcome
        if outcome is not None and not isinstance(outcome, TurnOutcome):
            outcome = TurnOutcome(str(outcome))

        if signal in _TRANSIENT_SIGNALS:
            if outcome is not None:
                raise ValueError("transient motion lifecycle signals cannot have an outcome")
        elif outcome not in _TERMINAL_OUTCOMES_BY_SIGNAL[signal]:
            raise ValueError("terminal motion lifecycle signal does not match its outcome")

        object.__setattr__(self, "signal", signal)
        object.__setattr__(self, "session_id", _required_session_id(self.session_id))
        object.__setattr__(self, "turn_id", _required_turn_id(self.turn_id))
        object.__setattr__(
            self,
            "generation_id",
            _required_generation_id(self.generation_id),
        )
        object.__setattr__(
            self,
            "source_sequence",
            EventSequence.parse(self.source_sequence),
        )
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )


class MotionLifecycleHookOutcome(str, Enum):
    """Public-safe result of resolving one lifecycle hook notification."""

    MAPPED = "mapped"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MotionLifecycleHookResult:
    """Normalized result of one isolated lifecycle hook invocation."""

    outcome: MotionLifecycleHookOutcome | str
    notification: MotionLifecycleNotification
    request: MotionRequest | None = field(default=None, repr=False)
    safe_message: str = ""
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, MotionLifecycleHookOutcome)
            else MotionLifecycleHookOutcome(str(self.outcome))
        )
        if not isinstance(self.notification, MotionLifecycleNotification):
            raise TypeError("notification must be a MotionLifecycleNotification")
        if outcome is MotionLifecycleHookOutcome.MAPPED:
            if not isinstance(self.request, MotionRequest):
                raise ValueError("mapped hook result requires a MotionRequest")
            if (
                self.request.turn_id != self.notification.turn_id
                or self.request.generation_id != self.notification.generation_id
            ):
                raise ValueError(
                    "mapped hook request must match notification correlation"
                )
        elif self.request is not None:
            raise ValueError("skipped or failed hook result cannot contain a request")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "safe_message", _safe_message(self.safe_message))
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def is_mapped(self) -> bool:
        return self.outcome is MotionLifecycleHookOutcome.MAPPED


@runtime_checkable
class MotionLifecycleHook(Protocol):
    """Host/plugin mapping from a lifecycle signal to provider-neutral motion."""

    def __call__(
        self,
        notification: MotionLifecycleNotification,
    ) -> MotionRequest | None:
        ...


def _failed_hook_result(
    notification: MotionLifecycleNotification,
    *,
    reason: str,
) -> MotionLifecycleHookResult:
    return MotionLifecycleHookResult(
        outcome=MotionLifecycleHookOutcome.FAILED,
        notification=notification,
        safe_message="Motion lifecycle hook processing failed safely.",
        public_metadata={
            "boundary": "motion_lifecycle_hook",
            "reason": reason,
            "motion_executed": False,
            "conversation_terminal_changed": False,
        },
    )


def invoke_motion_lifecycle_hook(
    hook: MotionLifecycleHook,
    notification: MotionLifecycleNotification,
) -> MotionLifecycleHookResult:
    """Invoke and normalize one host/plugin lifecycle mapping safely.

    ``None`` means an intentional skip. Exceptions, malformed return values,
    partial correlation, and correlation mismatches become a public-safe failed
    hook result and never escape this boundary. A returned uncorrelated request
    is additively bound to the notification's existing turn/generation context.
    This function does not execute the request or decide adapter support.
    """

    if not isinstance(notification, MotionLifecycleNotification):
        raise TypeError("notification must be a MotionLifecycleNotification")
    if not callable(hook):
        raise TypeError("hook must be callable")

    try:
        request = hook(notification)
    except Exception:
        return _failed_hook_result(notification, reason="hook_exception")

    if request is None:
        return MotionLifecycleHookResult(
            outcome=MotionLifecycleHookOutcome.SKIPPED,
            notification=notification,
            safe_message="Motion lifecycle hook skipped this signal.",
            public_metadata={
                "boundary": "motion_lifecycle_hook",
                "reason": "no_motion_request",
                "motion_executed": False,
                "conversation_terminal_changed": False,
            },
        )
    if not isinstance(request, MotionRequest):
        return _failed_hook_result(notification, reason="invalid_hook_result")

    if request.turn_id is None and request.generation_id is None:
        try:
            request = replace(
                request,
                turn_id=notification.turn_id,
                generation_id=notification.generation_id,
            )
        except Exception:
            return _failed_hook_result(notification, reason="invalid_hook_result")
    elif (
        request.turn_id != notification.turn_id
        or request.generation_id != notification.generation_id
    ):
        return _failed_hook_result(notification, reason="correlation_mismatch")

    return MotionLifecycleHookResult(
        outcome=MotionLifecycleHookOutcome.MAPPED,
        notification=notification,
        request=request,
        safe_message="Motion lifecycle hook returned a provider-neutral request.",
        public_metadata={
            "boundary": "motion_lifecycle_hook",
            "reason": "provider_neutral_request",
            "motion_executed": False,
            "conversation_terminal_changed": False,
        },
    )


__all__ = [
    "MotionLifecycleSignal",
    "MotionLifecycleNotification",
    "MotionLifecycleHookOutcome",
    "MotionLifecycleHookResult",
    "MotionLifecycleHook",
    "invoke_motion_lifecycle_hook",
]
