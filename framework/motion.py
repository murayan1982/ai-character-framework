"""Public motion / Live2D / VTS adapter contracts.

This module contains provider-neutral public data types only. It must not import
Live2D, VTube Studio, websocket, model runtime, audio, microphone, or provider
SDK modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from .identity import SessionId, normalize_session_id


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


class MotionAdapterStatus(str, Enum):
    """Provider-neutral public motion adapter status."""

    DISABLED = "disabled"
    MOCK_AVAILABLE = "mock_available"
    NOT_CONFIGURED = "not_configured"
    TOKEN_MISSING = "token_missing"
    PROVIDER_EXECUTION_NOT_ALLOWED = "provider_execution_not_allowed"
    RUNTIME_NOT_INSTALLED = "runtime_not_installed"
    MODEL_NOT_SELECTED = "model_not_selected"
    CONFIGURED = "configured"
    NOT_IMPLEMENTED = "not_implemented"
    UNSUPPORTED_ADAPTER = "unsupported_adapter"
    CLOSED = "closed"


class MotionState(str, Enum):
    """Provider-neutral motion lifecycle state."""

    IDLE = "idle"
    PREPARING = "preparing"
    SPEAKING = "speaking"
    EXPRESSING = "expressing"
    GESTURING = "gesturing"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    CLOSED = "closed"
    UNAVAILABLE = "unavailable"


class MotionEventType(str, Enum):
    """Provider-neutral motion event type."""

    SESSION_CREATED = "motion.session.created"
    ADAPTER_PREFLIGHT_COMPLETED = "motion.adapter.preflight.completed"
    REQUESTED = "motion.requested"
    STARTED = "motion.started"
    COMPLETED = "motion.completed"
    INTERRUPTED = "motion.interrupted"
    FAILED = "motion.failed"
    UNSUPPORTED = "motion.unsupported"
    SESSION_CLOSED = "motion.session.closed"


class MotionErrorCode(str, Enum):
    """Provider-neutral motion public error code."""

    NONE = "none"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    NOT_CONFIGURED = "not_configured"
    TOKEN_MISSING = "token_missing"
    PROVIDER_EXECUTION_NOT_ALLOWED = "provider_execution_not_allowed"
    RUNTIME_NOT_INSTALLED = "runtime_not_installed"
    MODEL_NOT_SELECTED = "model_not_selected"
    NOT_IMPLEMENTED = "not_implemented"
    INTERRUPTED = "interrupted"
    SESSION_CLOSED = "session_closed"
    PROVIDER_ERROR = "provider_error"


class MotionIntent(str, Enum):
    """Provider-neutral public motion request intent."""

    EXPRESSION = "expression"
    EMOTION = "emotion"
    SPEAKING_STATE = "speaking_state"
    IDLE_MOTION = "idle_motion"
    GESTURE = "gesture"
    LOOK_AT = "look_at"
    STOP_MOTION = "stop_motion"
    RESET_EXPRESSION = "reset_expression"


class MotionOutcome(str, Enum):
    """Provider-neutral public motion result outcome."""

    COMPLETED = "completed"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    NOT_IMPLEMENTED = "not_implemented"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass(frozen=True)
class MotionCapability:
    """Provider-neutral public motion adapter capability snapshot."""

    adapter: str = "mock"
    adapter_status: MotionAdapterStatus | str = MotionAdapterStatus.DISABLED
    supports_motion_session: bool = True
    supports_mock_motion: bool = True
    supports_real_adapter: bool = False
    supports_expression: bool = False
    supports_emotion: bool = False
    supports_speaking_state: bool = False
    supports_idle_motion: bool = False
    supports_gesture: bool = False
    supports_look_at: bool = False
    supports_stop_motion: bool = False
    supports_reset_expression: bool = False
    safe_message: str = ""
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = (
            self.adapter_status
            if isinstance(self.adapter_status, MotionAdapterStatus)
            else MotionAdapterStatus(str(self.adapter_status))
        )
        object.__setattr__(self, "adapter_status", status)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    def supports_intent(self, intent: MotionIntent | str) -> bool:
        """Return support for one provider-neutral motion intent."""

        resolved = (
            intent
            if isinstance(intent, MotionIntent)
            else MotionIntent(str(intent))
        )
        return {
            MotionIntent.EXPRESSION: self.supports_expression,
            MotionIntent.EMOTION: self.supports_emotion,
            MotionIntent.SPEAKING_STATE: self.supports_speaking_state,
            MotionIntent.IDLE_MOTION: self.supports_idle_motion,
            MotionIntent.GESTURE: self.supports_gesture,
            MotionIntent.LOOK_AT: self.supports_look_at,
            MotionIntent.STOP_MOTION: self.supports_stop_motion,
            MotionIntent.RESET_EXPRESSION: self.supports_reset_expression,
        }[resolved]

    @classmethod
    def disabled(cls, *, adapter: str = "mock") -> "MotionCapability":
        return cls(
            adapter=adapter,
            adapter_status=MotionAdapterStatus.DISABLED,
            safe_message="Motion adapter is disabled.",
            public_metadata={"boundary": "motion", "reason": "disabled"},
        )

    @classmethod
    def mock_available(cls) -> "MotionCapability":
        return cls(
            adapter="mock",
            adapter_status=MotionAdapterStatus.MOCK_AVAILABLE,
            supports_expression=True,
            supports_emotion=True,
            supports_speaking_state=True,
            supports_idle_motion=True,
            supports_gesture=True,
            supports_look_at=True,
            supports_stop_motion=True,
            supports_reset_expression=True,
            safe_message="Mock motion adapter is available.",
            public_metadata={"boundary": "motion", "reason": "mock_available"},
        )


@dataclass(frozen=True)
class MotionRequest:
    """Provider-neutral public motion request."""

    intent: MotionIntent | str
    request_id: str = field(default_factory=lambda: uuid4().hex)
    expression: str | None = None
    emotion: str | None = None
    gesture: str | None = None
    speaking: bool | None = None
    intensity: float | None = None
    duration_ms: int | None = None
    character_id: str | None = None
    model_id: str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        intent = self.intent if isinstance(self.intent, MotionIntent) else MotionIntent(str(self.intent))
        if self.duration_ms is not None and self.duration_ms <= 0:
            raise ValueError("duration_ms must be positive when provided")
        if self.intensity is not None and not (0.0 <= self.intensity <= 1.0):
            raise ValueError("intensity must be between 0.0 and 1.0 when provided")
        object.__setattr__(self, "intent", intent)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @classmethod
    def expression_change(
        cls,
        expression: str,
        *,
        intensity: float | None = None,
        duration_ms: int | None = None,
        character_id: str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "MotionRequest":
        return cls(
            intent=MotionIntent.EXPRESSION,
            expression=expression,
            intensity=intensity,
            duration_ms=duration_ms,
            character_id=character_id,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def emotion_update(
        cls,
        emotion: str,
        *,
        intensity: float | None = None,
        character_id: str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "MotionRequest":
        return cls(
            intent=MotionIntent.EMOTION,
            emotion=emotion,
            intensity=intensity,
            character_id=character_id,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def speaking_state(
        cls,
        speaking: bool,
        *,
        character_id: str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "MotionRequest":
        return cls(
            intent=MotionIntent.SPEAKING_STATE,
            speaking=speaking,
            character_id=character_id,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def stop_motion(
        cls,
        *,
        character_id: str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "MotionRequest":
        return cls(
            intent=MotionIntent.STOP_MOTION,
            character_id=character_id,
            public_metadata=public_metadata or {},
        )


@dataclass(frozen=True)
class MotionResult:
    """Provider-neutral public motion result."""

    outcome: MotionOutcome | str
    state: MotionState | str = MotionState.IDLE
    adapter_status: MotionAdapterStatus | str = MotionAdapterStatus.DISABLED
    public_error_code: MotionErrorCode | str = MotionErrorCode.NONE
    safe_message: str = ""
    retryable: bool = False
    request_id: str | None = None
    session_id: SessionId | str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = self.outcome if isinstance(self.outcome, MotionOutcome) else MotionOutcome(str(self.outcome))
        state = self.state if isinstance(self.state, MotionState) else MotionState(str(self.state))
        status = (
            self.adapter_status
            if isinstance(self.adapter_status, MotionAdapterStatus)
            else MotionAdapterStatus(str(self.adapter_status))
        )
        error_code = (
            self.public_error_code
            if isinstance(self.public_error_code, MotionErrorCode)
            else MotionErrorCode(str(self.public_error_code))
        )
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "adapter_status", status)
        object.__setattr__(self, "public_error_code", error_code)
        object.__setattr__(self, "session_id", normalize_session_id(self.session_id))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @property
    def is_completed(self) -> bool:
        return self.outcome is MotionOutcome.COMPLETED

    @property
    def is_terminal(self) -> bool:
        return self.outcome in {
            MotionOutcome.COMPLETED,
            MotionOutcome.UNSUPPORTED,
            MotionOutcome.UNAVAILABLE,
            MotionOutcome.NOT_CONFIGURED,
            MotionOutcome.NOT_IMPLEMENTED,
            MotionOutcome.INTERRUPTED,
            MotionOutcome.FAILED,
            MotionOutcome.CLOSED,
        }

    @classmethod
    def completed(
        cls,
        *,
        request: MotionRequest | None = None,
        session_id: SessionId | str | None = None,
        state: MotionState | str = MotionState.IDLE,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "MotionResult":
        return cls(
            outcome=MotionOutcome.COMPLETED,
            state=state,
            adapter_status=MotionAdapterStatus.MOCK_AVAILABLE,
            request_id=request.request_id if request else None,
            session_id=session_id,
            public_metadata={"boundary": "motion", **dict(public_metadata or {})},
        )

    @classmethod
    def unavailable(
        cls,
        *,
        request: MotionRequest | None = None,
        adapter_status: MotionAdapterStatus | str = MotionAdapterStatus.DISABLED,
        public_error_code: MotionErrorCode | str = MotionErrorCode.UNAVAILABLE,
        safe_message: str = "Motion adapter is unavailable.",
        retryable: bool = False,
        session_id: SessionId | str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "MotionResult":
        return cls(
            outcome=MotionOutcome.UNAVAILABLE,
            state=MotionState.UNAVAILABLE,
            adapter_status=adapter_status,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            request_id=request.request_id if request else None,
            session_id=session_id,
            public_metadata={"boundary": "motion", **dict(public_metadata or {})},
        )

    @classmethod
    def not_implemented(
        cls,
        *,
        request: MotionRequest | None = None,
        session_id: SessionId | str | None = None,
        safe_message: str = "Motion adapter is not implemented yet.",
    ) -> "MotionResult":
        return cls(
            outcome=MotionOutcome.NOT_IMPLEMENTED,
            state=MotionState.UNAVAILABLE,
            adapter_status=MotionAdapterStatus.NOT_IMPLEMENTED,
            public_error_code=MotionErrorCode.NOT_IMPLEMENTED,
            safe_message=safe_message,
            retryable=False,
            request_id=request.request_id if request else None,
            session_id=session_id,
            public_metadata={"boundary": "motion", "reason": "not_implemented"},
        )

    @classmethod
    def closed(
        cls,
        *,
        request: MotionRequest | None = None,
        session_id: SessionId | str | None = None,
        safe_message: str = "Motion session is closed.",
    ) -> "MotionResult":
        return cls(
            outcome=MotionOutcome.CLOSED,
            state=MotionState.CLOSED,
            adapter_status=MotionAdapterStatus.CLOSED,
            public_error_code=MotionErrorCode.SESSION_CLOSED,
            safe_message=safe_message,
            retryable=False,
            request_id=request.request_id if request else None,
            session_id=session_id,
            public_metadata={"boundary": "motion", "reason": "session_closed"},
        )
