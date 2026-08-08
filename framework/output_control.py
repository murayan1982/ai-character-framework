"""Public interrupt / output control contracts.

This module contains provider-neutral public data types only. It must not import
LLM, TTS, audio playback, motion, Live2D, VTube Studio, websocket, microphone,
or provider SDK modules.
"""

from __future__ import annotations
from .public_safety import public_mapping as _recursive_public_mapping

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

from .identity import TurnId, normalize_turn_id

if TYPE_CHECKING:
    from .motion_control import MotionControlResult


_SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


def _public_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Delegate to the common recursive public-safety utility."""
    return _recursive_public_mapping(values)


class InterruptScope(str, Enum):
    """Provider-neutral interrupt scope."""

    CURRENT_TURN = "current_turn"
    LLM_STREAM = "llm_stream"
    TTS_QUEUE = "tts_queue"
    VOICE_OUTPUT = "voice_output"
    MOTION = "motion"
    ALL = "all"


class InterruptReason(str, Enum):
    """Provider-neutral interrupt reason."""

    USER_BARGE_IN = "user_barge_in"
    USER_CANCEL = "user_cancel"
    NEW_TURN_STARTED = "new_turn_started"
    SESSION_CLOSED = "session_closed"
    TIMEOUT = "timeout"
    HOST_APP_REQUEST = "host_app_request"
    PROVIDER_FAILURE = "provider_failure"


class InterruptOutcome(str, Enum):
    """Provider-neutral interrupt outcome."""

    ACCEPTED = "accepted"
    UNSUPPORTED = "unsupported"
    NO_ACTIVE_TURN = "no_active_turn"
    ALREADY_CLOSED = "already_closed"
    NOT_IMPLEMENTED = "not_implemented"
    FAILED = "failed"


class OutputFlushOutcome(str, Enum):
    """Provider-neutral output flush outcome."""

    FLUSHED = "flushed"
    NOTHING_TO_FLUSH = "nothing_to_flush"
    UNSUPPORTED = "unsupported"
    NOT_IMPLEMENTED = "not_implemented"
    FAILED = "failed"
    CLOSED = "closed"


class BargeInPolicyMode(str, Enum):
    """Provider-neutral barge-in policy mode."""

    DISABLED = "disabled"
    SOFT_INTERRUPT = "soft_interrupt"
    FLUSH_OUTPUT = "flush_output"
    HARD_CANCEL = "hard_cancel"
    TURN_TAKEOVER = "turn_takeover"


@dataclass(frozen=True)
class InterruptRequest:
    """Provider-neutral interrupt request."""

    scope: InterruptScope | str = InterruptScope.CURRENT_TURN
    reason: InterruptReason | str = InterruptReason.HOST_APP_REQUEST
    turn_id: TurnId | str | None = None
    flush_output: bool = False
    cancel_tts_queue: bool = False
    cancel_llm_stream: bool = False
    stop_motion: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        scope = self.scope if isinstance(self.scope, InterruptScope) else InterruptScope(str(self.scope))
        reason = self.reason if isinstance(self.reason, InterruptReason) else InterruptReason(str(self.reason))
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @classmethod
    def user_barge_in(
        cls,
        *,
        turn_id: TurnId | str | None = None,
        scope: InterruptScope | str = InterruptScope.ALL,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "InterruptRequest":
        """Create a standard user barge-in interrupt request."""

        return cls(
            scope=scope,
            reason=InterruptReason.USER_BARGE_IN,
            turn_id=turn_id,
            flush_output=True,
            cancel_tts_queue=True,
            cancel_llm_stream=True,
            stop_motion=True,
            public_metadata=public_metadata or {},
        )


@dataclass(frozen=True)
class InterruptResult:
    """Provider-neutral interrupt result."""

    outcome: InterruptOutcome | str
    scope: InterruptScope | str = InterruptScope.CURRENT_TURN
    reason: InterruptReason | str = InterruptReason.HOST_APP_REQUEST
    turn_id: TurnId | str | None = None
    safe_message: str = ""
    retryable: bool = False
    provider_cancel_supported: bool = False
    queue_flush_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)
    motion_result: "MotionControlResult | None" = None

    def __post_init__(self) -> None:
        outcome = self.outcome if isinstance(self.outcome, InterruptOutcome) else InterruptOutcome(str(self.outcome))
        scope = self.scope if isinstance(self.scope, InterruptScope) else InterruptScope(str(self.scope))
        reason = self.reason if isinstance(self.reason, InterruptReason) else InterruptReason(str(self.reason))
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))
        if self.motion_result is not None:
            from .motion_control import MotionControlResult

            if not isinstance(self.motion_result, MotionControlResult):
                raise TypeError("motion_result must be a MotionControlResult or None")
            if (
                self.turn_id is not None
                and self.motion_result.turn_id is not None
                and self.turn_id != self.motion_result.turn_id
            ):
                raise ValueError("motion_result turn_id must match interrupt turn_id")

    @property
    def accepted(self) -> bool:
        return self.outcome is InterruptOutcome.ACCEPTED

    @property
    def is_terminal(self) -> bool:
        return self.outcome in {
            InterruptOutcome.ACCEPTED,
            InterruptOutcome.UNSUPPORTED,
            InterruptOutcome.NO_ACTIVE_TURN,
            InterruptOutcome.ALREADY_CLOSED,
            InterruptOutcome.NOT_IMPLEMENTED,
            InterruptOutcome.FAILED,
        }

    @classmethod
    def not_implemented(
        cls,
        *,
        request: InterruptRequest | None = None,
        safe_message: str = "Interrupt control is not implemented yet.",
    ) -> "InterruptResult":
        request = request or InterruptRequest()
        return cls(
            outcome=InterruptOutcome.NOT_IMPLEMENTED,
            scope=request.scope,
            reason=request.reason,
            turn_id=request.turn_id,
            safe_message=safe_message,
            retryable=False,
            public_metadata={"boundary": "interrupt", "reason": "not_implemented"},
        )

    @classmethod
    def already_closed(
        cls,
        *,
        request: InterruptRequest | None = None,
        safe_message: str = "Session is already closed.",
    ) -> "InterruptResult":
        request = request or InterruptRequest(reason=InterruptReason.SESSION_CLOSED)
        return cls(
            outcome=InterruptOutcome.ALREADY_CLOSED,
            scope=request.scope,
            reason=request.reason,
            turn_id=request.turn_id,
            safe_message=safe_message,
            retryable=False,
            public_metadata={"boundary": "interrupt", "reason": "session_closed"},
        )

    @classmethod
    def no_active_turn(
        cls,
        *,
        request: InterruptRequest | None = None,
        safe_message: str = "There is no active realtime turn to interrupt.",
    ) -> "InterruptResult":
        request = request or InterruptRequest()
        return cls(
            outcome=InterruptOutcome.NO_ACTIVE_TURN,
            scope=request.scope,
            reason=request.reason,
            turn_id=request.turn_id,
            safe_message=safe_message,
            retryable=False,
            public_metadata={"boundary": "interrupt", "reason": "no_active_turn"},
        )


@dataclass(frozen=True)
class TTSQueueState:
    """Provider-neutral public TTS queue state."""

    queued_count: int = 0
    current_item_id: str | None = None
    is_playing: bool = False
    supports_flush: bool = False
    supports_provider_cancel: bool = False
    playback_stop_required: bool = False
    safe_message: str = ""
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.queued_count < 0:
            raise ValueError("queued_count must be non-negative")
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


@dataclass(frozen=True)
class OutputFlushRequest:
    """Provider-neutral output flush request."""

    scope: InterruptScope | str = InterruptScope.TTS_QUEUE
    turn_id: TurnId | str | None = None
    stop_playback: bool = True
    clear_queued_audio: bool = True
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        scope = self.scope if isinstance(self.scope, InterruptScope) else InterruptScope(str(self.scope))
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


@dataclass(frozen=True)
class OutputFlushResult:
    """Provider-neutral output flush result."""

    outcome: OutputFlushOutcome | str
    queue_state: TTSQueueState = field(default_factory=TTSQueueState)
    turn_id: TurnId | str | None = None
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = self.outcome if isinstance(self.outcome, OutputFlushOutcome) else OutputFlushOutcome(str(self.outcome))
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @property
    def flushed(self) -> bool:
        return self.outcome is OutputFlushOutcome.FLUSHED

    @classmethod
    def not_implemented(
        cls,
        *,
        request: OutputFlushRequest | None = None,
        safe_message: str = "Output flush is not implemented yet.",
    ) -> "OutputFlushResult":
        return cls(
            outcome=OutputFlushOutcome.NOT_IMPLEMENTED,
            turn_id=request.turn_id if request else None,
            safe_message=safe_message,
            retryable=False,
            public_metadata={"boundary": "output_flush", "reason": "not_implemented"},
        )

    @classmethod
    def nothing_to_flush(
        cls,
        *,
        request: OutputFlushRequest | None = None,
        safe_message: str = "There is no queued output to flush.",
    ) -> "OutputFlushResult":
        return cls(
            outcome=OutputFlushOutcome.NOTHING_TO_FLUSH,
            turn_id=request.turn_id if request else None,
            safe_message=safe_message,
            retryable=False,
            public_metadata={"boundary": "output_flush", "reason": "nothing_to_flush"},
        )

    @classmethod
    def closed(
        cls,
        *,
        request: OutputFlushRequest | None = None,
        safe_message: str = "Session is already closed.",
    ) -> "OutputFlushResult":
        return cls(
            outcome=OutputFlushOutcome.CLOSED,
            turn_id=request.turn_id if request else None,
            safe_message=safe_message,
            retryable=False,
            public_metadata={"boundary": "output_flush", "reason": "session_closed"},
        )


@dataclass(frozen=True)
class BargeInPolicy:
    """Provider-neutral barge-in policy."""

    mode: BargeInPolicyMode | str = BargeInPolicyMode.DISABLED
    interrupt_scope: InterruptScope | str = InterruptScope.ALL
    flush_output: bool = False
    cancel_current_turn: bool = False
    allow_turn_takeover: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mode = self.mode if isinstance(self.mode, BargeInPolicyMode) else BargeInPolicyMode(str(self.mode))
        scope = self.interrupt_scope if isinstance(self.interrupt_scope, InterruptScope) else InterruptScope(str(self.interrupt_scope))
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "interrupt_scope", scope)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @classmethod
    def disabled(cls) -> "BargeInPolicy":
        return cls(mode=BargeInPolicyMode.DISABLED)

    @classmethod
    def soft_interrupt(cls) -> "BargeInPolicy":
        return cls(mode=BargeInPolicyMode.SOFT_INTERRUPT, interrupt_scope=InterruptScope.CURRENT_TURN)

    @classmethod
    def flush_output(cls) -> "BargeInPolicy":
        return cls(
            mode=BargeInPolicyMode.FLUSH_OUTPUT,
            interrupt_scope=InterruptScope.TTS_QUEUE,
            flush_output=True,
        )

    @classmethod
    def hard_cancel(cls) -> "BargeInPolicy":
        return cls(
            mode=BargeInPolicyMode.HARD_CANCEL,
            interrupt_scope=InterruptScope.ALL,
            flush_output=True,
            cancel_current_turn=True,
        )

    @classmethod
    def turn_takeover(cls) -> "BargeInPolicy":
        return cls(
            mode=BargeInPolicyMode.TURN_TAKEOVER,
            interrupt_scope=InterruptScope.ALL,
            flush_output=True,
            cancel_current_turn=True,
            allow_turn_takeover=True,
        )


@dataclass(frozen=True)
class BargeInDecision:
    """Provider-neutral barge-in decision."""

    accepted: bool
    policy: BargeInPolicy = field(default_factory=BargeInPolicy.disabled)
    interrupt_request: InterruptRequest | None = None
    should_stop_output: bool = False
    should_flush_queue: bool = False
    should_cancel_current_turn: bool = False
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @classmethod
    def rejected(
        cls,
        *,
        policy: BargeInPolicy | None = None,
        safe_message: str = "Barge-in is disabled.",
    ) -> "BargeInDecision":
        return cls(
            accepted=False,
            policy=policy or BargeInPolicy.disabled(),
            safe_message=safe_message,
            retryable=False,
            public_metadata={"boundary": "barge_in", "reason": "rejected"},
        )

    @classmethod
    def accepted_for_policy(
        cls,
        policy: BargeInPolicy,
        *,
        turn_id: TurnId | str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "BargeInDecision":
        request = InterruptRequest.user_barge_in(
            turn_id=turn_id,
            scope=policy.interrupt_scope,
            public_metadata=public_metadata or {},
        )
        return cls(
            accepted=True,
            policy=policy,
            interrupt_request=request,
            should_stop_output=policy.flush_output or policy.cancel_current_turn,
            should_flush_queue=policy.flush_output,
            should_cancel_current_turn=policy.cancel_current_turn,
            safe_message="Barge-in accepted by public policy.",
            retryable=False,
            public_metadata={
                "boundary": "barge_in",
                "policy_mode": policy.mode.value,
                **dict(public_metadata or {}),
            },
        )
