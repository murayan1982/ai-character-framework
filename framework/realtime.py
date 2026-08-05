"""Public realtime lifecycle / event contracts.

This module contains provider-neutral public data types only. It must not import
STT, LLM, TTS, motion, Live2D, VTube Studio, websocket, microphone, or provider
SDK modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .identity import SessionId, TurnId, normalize_session_id, normalize_turn_id


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
    """Return a shallow immutable public-safe metadata mapping."""

    if not values:
        return MappingProxyType({})

    safe: dict[str, Any] = {}
    for key, value in values.items():
        text_key = str(key)
        lower_key = text_key.lower()
        if any(fragment in lower_key for fragment in _SECRET_KEY_FRAGMENTS):
            safe[text_key] = "<redacted>"
        else:
            safe[text_key] = value
    return MappingProxyType(safe)


class RealtimeState(str, Enum):
    """Provider-neutral realtime lifecycle state."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    MOTION = "motion"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    COMPLETED = "completed"
    CLOSED = "closed"


class RealtimeEventType(str, Enum):
    """Provider-neutral realtime event type."""

    SESSION_CREATED = "realtime.session.created"
    TURN_STARTED = "realtime.turn.started"
    VOICE_INPUT_STARTED = "realtime.voice_input.started"
    VOICE_INPUT_COMPLETED = "realtime.voice_input.completed"
    TEXT_CHAT_STARTED = "realtime.text_chat.started"
    TEXT_CHAT_COMPLETED = "realtime.text_chat.completed"
    VOICE_OUTPUT_STARTED = "realtime.voice_output.started"
    VOICE_OUTPUT_COMPLETED = "realtime.voice_output.completed"
    MOTION_STARTED = "realtime.motion.started"
    MOTION_COMPLETED = "realtime.motion.completed"
    TURN_COMPLETED = "realtime.turn.completed"
    TURN_INTERRUPTED = "realtime.turn.interrupted"
    TURN_FAILED = "realtime.turn.failed"
    SESSION_CLOSED = "realtime.session.closed"
    INTERRUPT_REQUESTED = "realtime.interrupt.requested"
    INTERRUPT_ACCEPTED = "realtime.interrupt.accepted"
    INTERRUPT_COMPLETED = "realtime.interrupt.completed"
    INTERRUPT_UNSUPPORTED = "realtime.interrupt.unsupported"
    OUTPUT_FLUSH_REQUESTED = "realtime.output.flush.requested"
    OUTPUT_FLUSH_COMPLETED = "realtime.output.flush.completed"
    OUTPUT_FLUSH_UNSUPPORTED = "realtime.output.flush.unsupported"
    BARGE_IN_DETECTED = "realtime.barge_in.detected"
    BARGE_IN_ACCEPTED = "realtime.barge_in.accepted"
    BARGE_IN_REJECTED = "realtime.barge_in.rejected"


class RealtimeErrorCode(str, Enum):
    """Provider-neutral realtime public error code."""

    NONE = "none"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    INTERRUPTED = "interrupted"
    SESSION_CLOSED = "session_closed"
    INVALID_REQUEST = "invalid_request"
    STAGE_FAILED = "stage_failed"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class RealtimeEvent:
    """Provider-neutral app-facing realtime event."""

    type: RealtimeEventType | str
    state: RealtimeState | str
    previous_state: RealtimeState | str | None = None
    turn_id: TurnId | str | None = None
    session_id: SessionId | str | None = None
    boundary: str = "realtime"
    public_error_code: RealtimeErrorCode | str = RealtimeErrorCode.NONE
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_type = self.type if isinstance(self.type, RealtimeEventType) else RealtimeEventType(str(self.type))
        state = self.state if isinstance(self.state, RealtimeState) else RealtimeState(str(self.state))
        previous_state = self.previous_state
        if previous_state is not None and not isinstance(previous_state, RealtimeState):
            previous_state = RealtimeState(str(previous_state))
        error_code = (
            self.public_error_code
            if isinstance(self.public_error_code, RealtimeErrorCode)
            else RealtimeErrorCode(str(self.public_error_code))
        )

        object.__setattr__(self, "type", event_type)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "previous_state", previous_state)
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "session_id", normalize_session_id(self.session_id))
        object.__setattr__(self, "public_error_code", error_code)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, Any]:
        """Return an immutable public-safe event mapping for host-app callbacks."""

        return MappingProxyType(
            {
                "type": self.type.value,
                "state": self.state.value,
                "previous_state": self.previous_state.value if self.previous_state else None,
                "turn_id": str(self.turn_id) if self.turn_id is not None else None,
                "session_id": (
                    str(self.session_id) if self.session_id is not None else None
                ),
                "boundary": self.boundary,
                "public_error_code": self.public_error_code.value,
                "safe_message": self.safe_message,
                "retryable": self.retryable,
                "public_metadata": self.public_metadata,
            }
        )


@dataclass(frozen=True)
class RealtimeTurn:
    """Provider-neutral public turn descriptor."""

    turn_id: TurnId | str = field(default_factory=TurnId.new)
    input_text: str = ""
    state: RealtimeState | str = RealtimeState.IDLE
    session_id: SessionId | str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        state = self.state if isinstance(self.state, RealtimeState) else RealtimeState(str(self.state))
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "session_id", normalize_session_id(self.session_id))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


@dataclass(frozen=True)
class RealtimeTurnResult:
    """Provider-neutral public realtime turn result."""

    turn_id: TurnId | str
    outcome: RealtimeState | str
    input_text: str = ""
    output_text: str = ""
    voice_input_result: Any | None = None
    text_chat_result: Any | None = None
    voice_output_result: Any | None = None
    motion_result: Any | None = None
    public_error_code: RealtimeErrorCode | str = RealtimeErrorCode.NONE
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = self.outcome if isinstance(self.outcome, RealtimeState) else RealtimeState(str(self.outcome))
        error_code = (
            self.public_error_code
            if isinstance(self.public_error_code, RealtimeErrorCode)
            else RealtimeErrorCode(str(self.public_error_code))
        )
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "public_error_code", error_code)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @property
    def is_completed(self) -> bool:
        return self.outcome is RealtimeState.COMPLETED

    @property
    def is_terminal(self) -> bool:
        return self.outcome in {
            RealtimeState.COMPLETED,
            RealtimeState.INTERRUPTED,
            RealtimeState.FAILED,
            RealtimeState.CLOSED,
        }

    @classmethod
    def completed(
        cls,
        *,
        turn_id: TurnId | str,
        input_text: str = "",
        output_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "RealtimeTurnResult":
        return cls(
            turn_id=turn_id,
            outcome=RealtimeState.COMPLETED,
            input_text=input_text,
            output_text=output_text,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def interrupted(
        cls,
        *,
        turn_id: TurnId | str,
        safe_message: str = "Realtime turn was interrupted.",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "RealtimeTurnResult":
        return cls(
            turn_id=turn_id,
            outcome=RealtimeState.INTERRUPTED,
            public_error_code=RealtimeErrorCode.INTERRUPTED,
            safe_message=safe_message,
            retryable=True,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def failed(
        cls,
        *,
        turn_id: TurnId | str,
        public_error_code: RealtimeErrorCode | str = RealtimeErrorCode.STAGE_FAILED,
        safe_message: str = "Realtime turn failed.",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "RealtimeTurnResult":
        return cls(
            turn_id=turn_id,
            outcome=RealtimeState.FAILED,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def closed(
        cls,
        *,
        turn_id: TurnId | str,
        safe_message: str = "Realtime session is closed.",
    ) -> "RealtimeTurnResult":
        return cls(
            turn_id=turn_id,
            outcome=RealtimeState.CLOSED,
            public_error_code=RealtimeErrorCode.SESSION_CLOSED,
            safe_message=safe_message,
            retryable=False,
        )
