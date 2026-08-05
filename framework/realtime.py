"""Public realtime lifecycle / event contracts.

This module contains provider-neutral public data types only. It must not import
STT, LLM, TTS, motion, Live2D, VTube Studio, websocket, microphone, or provider
SDK modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .identity import (
    EventSequence,
    GenerationId,
    SessionId,
    TurnId,
    normalize_session_id,
    normalize_turn_id,
)
from .lifecycle import (
    LifecycleTransitionError,
    LifecycleTransitionErrorCode,
    RealtimePhase,
    RecoveryAction,
    TurnOutcome,
)
from .realtime_event_payloads import (
    AudioEventPayload,
    DiagnosticEventPayload,
    InterruptEventPayload,
    LifecycleEventPayload,
    MotionEventPayload,
    RealtimeEventPayload,
    ResponseEventPayload,
    SynthesisEventPayload,
    TranscriptEventPayload,
)


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


_REALTIME_PHASE_BY_STATE = {
    RealtimeState.IDLE: RealtimePhase.IDLE,
    RealtimeState.LISTENING: RealtimePhase.LISTENING,
    RealtimeState.TRANSCRIBING: RealtimePhase.TRANSCRIBING,
    RealtimeState.THINKING: RealtimePhase.THINKING,
    RealtimeState.SPEAKING: RealtimePhase.SPEAKING,
    RealtimeState.MOTION: RealtimePhase.MOTION,
}


def _normalize_realtime_phase(
    value: RealtimePhase | str | None,
    *,
    legacy_state: RealtimeState | str | None = None,
) -> RealtimePhase | None:
    if value is not None:
        return value if isinstance(value, RealtimePhase) else RealtimePhase(str(value))
    if legacy_state is None:
        return None
    state = (
        legacy_state
        if isinstance(legacy_state, RealtimeState)
        else RealtimeState(str(legacy_state))
    )
    return _REALTIME_PHASE_BY_STATE.get(state)


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

    # Canonical v6 event categories. Existing v5 members above remain stable.
    SESSION_STARTED = "realtime.session.started"
    TURN_CANCELLED = "realtime.turn.cancelled"
    TURN_REJECTED = "realtime.turn.rejected"
    LISTENING_STARTED = "realtime.listening.started"
    LISTENING_COMPLETED = "realtime.listening.completed"
    SPEECH_STARTED = "realtime.speech.started"
    SPEECH_ENDED = "realtime.speech.ended"
    TRANSCRIPT_PARTIAL = "realtime.transcript.partial"
    TRANSCRIPT_FINAL = "realtime.transcript.final"
    RESPONSE_STARTED = "realtime.response.started"
    RESPONSE_DELTA = "realtime.response.delta"
    RESPONSE_COMPLETED = "realtime.response.completed"
    SYNTHESIS_STARTED = "realtime.synthesis.started"
    SYNTHESIS_COMPLETED = "realtime.synthesis.completed"
    AUDIO_AVAILABLE = "realtime.audio.available"
    AUDIO_INVALIDATED = "realtime.audio.invalidated"
    MOTION_REQUESTED = "realtime.motion.requested"
    MOTION_FAILED = "realtime.motion.failed"
    STALE_RESULT_DROPPED = "realtime.stale_result.dropped"
    EVENT_OVERFLOW = "realtime.event.overflow"


_REALTIME_EVENT_PAYLOAD_TYPES = (
    LifecycleEventPayload,
    TranscriptEventPayload,
    ResponseEventPayload,
    SynthesisEventPayload,
    AudioEventPayload,
    MotionEventPayload,
    InterruptEventPayload,
    DiagnosticEventPayload,
)

_TERMINAL_REALTIME_EVENT_TYPES = frozenset(
    {
        RealtimeEventType.TURN_COMPLETED,
        RealtimeEventType.TURN_INTERRUPTED,
        RealtimeEventType.TURN_CANCELLED,
        RealtimeEventType.TURN_FAILED,
        RealtimeEventType.TURN_REJECTED,
        RealtimeEventType.SESSION_CLOSED,
    }
)


_V5_REALTIME_EVENT_TYPES = frozenset(
    {
        RealtimeEventType.SESSION_CREATED,
        RealtimeEventType.TURN_STARTED,
        RealtimeEventType.VOICE_INPUT_STARTED,
        RealtimeEventType.VOICE_INPUT_COMPLETED,
        RealtimeEventType.TEXT_CHAT_STARTED,
        RealtimeEventType.TEXT_CHAT_COMPLETED,
        RealtimeEventType.VOICE_OUTPUT_STARTED,
        RealtimeEventType.VOICE_OUTPUT_COMPLETED,
        RealtimeEventType.MOTION_STARTED,
        RealtimeEventType.MOTION_COMPLETED,
        RealtimeEventType.TURN_COMPLETED,
        RealtimeEventType.TURN_INTERRUPTED,
        RealtimeEventType.TURN_FAILED,
        RealtimeEventType.SESSION_CLOSED,
        RealtimeEventType.INTERRUPT_REQUESTED,
        RealtimeEventType.INTERRUPT_ACCEPTED,
        RealtimeEventType.INTERRUPT_COMPLETED,
        RealtimeEventType.INTERRUPT_UNSUPPORTED,
        RealtimeEventType.OUTPUT_FLUSH_REQUESTED,
        RealtimeEventType.OUTPUT_FLUSH_COMPLETED,
        RealtimeEventType.OUTPUT_FLUSH_UNSUPPORTED,
        RealtimeEventType.BARGE_IN_DETECTED,
        RealtimeEventType.BARGE_IN_ACCEPTED,
        RealtimeEventType.BARGE_IN_REJECTED,
    }
)

_V6_TO_V5_REALTIME_EVENT_TYPE = MappingProxyType(
    {
        RealtimeEventType.SESSION_STARTED: RealtimeEventType.SESSION_CREATED,
        RealtimeEventType.LISTENING_STARTED: RealtimeEventType.VOICE_INPUT_STARTED,
        RealtimeEventType.TRANSCRIPT_FINAL: RealtimeEventType.VOICE_INPUT_COMPLETED,
        RealtimeEventType.RESPONSE_STARTED: RealtimeEventType.TEXT_CHAT_STARTED,
        RealtimeEventType.RESPONSE_COMPLETED: RealtimeEventType.TEXT_CHAT_COMPLETED,
        RealtimeEventType.SYNTHESIS_STARTED: RealtimeEventType.VOICE_OUTPUT_STARTED,
        RealtimeEventType.SYNTHESIS_COMPLETED: RealtimeEventType.VOICE_OUTPUT_COMPLETED,
        RealtimeEventType.TURN_CANCELLED: RealtimeEventType.TURN_INTERRUPTED,
        RealtimeEventType.TURN_REJECTED: RealtimeEventType.TURN_FAILED,
    }
)

_RUNTIME_PAYLOAD_TYPE_BY_EVENT = MappingProxyType(
    {
        RealtimeEventType.SESSION_STARTED: LifecycleEventPayload,
        RealtimeEventType.SESSION_CLOSED: LifecycleEventPayload,
        RealtimeEventType.TURN_STARTED: LifecycleEventPayload,
        RealtimeEventType.TURN_COMPLETED: LifecycleEventPayload,
        RealtimeEventType.TURN_CANCELLED: LifecycleEventPayload,
        RealtimeEventType.TURN_REJECTED: LifecycleEventPayload,
        RealtimeEventType.TURN_FAILED: LifecycleEventPayload,
        RealtimeEventType.LISTENING_STARTED: LifecycleEventPayload,
        RealtimeEventType.LISTENING_COMPLETED: LifecycleEventPayload,
        RealtimeEventType.SPEECH_STARTED: LifecycleEventPayload,
        RealtimeEventType.SPEECH_ENDED: LifecycleEventPayload,
        RealtimeEventType.TRANSCRIPT_PARTIAL: TranscriptEventPayload,
        RealtimeEventType.TRANSCRIPT_FINAL: TranscriptEventPayload,
        RealtimeEventType.RESPONSE_STARTED: ResponseEventPayload,
        RealtimeEventType.RESPONSE_DELTA: ResponseEventPayload,
        RealtimeEventType.RESPONSE_COMPLETED: ResponseEventPayload,
        RealtimeEventType.SYNTHESIS_STARTED: SynthesisEventPayload,
        RealtimeEventType.SYNTHESIS_COMPLETED: SynthesisEventPayload,
        RealtimeEventType.AUDIO_AVAILABLE: AudioEventPayload,
        RealtimeEventType.AUDIO_INVALIDATED: AudioEventPayload,
        RealtimeEventType.MOTION_REQUESTED: MotionEventPayload,
        RealtimeEventType.MOTION_STARTED: MotionEventPayload,
        RealtimeEventType.MOTION_COMPLETED: MotionEventPayload,
        RealtimeEventType.MOTION_FAILED: MotionEventPayload,
        RealtimeEventType.INTERRUPT_REQUESTED: InterruptEventPayload,
        RealtimeEventType.INTERRUPT_ACCEPTED: InterruptEventPayload,
        RealtimeEventType.INTERRUPT_COMPLETED: InterruptEventPayload,
        RealtimeEventType.INTERRUPT_UNSUPPORTED: InterruptEventPayload,
        RealtimeEventType.BARGE_IN_DETECTED: InterruptEventPayload,
        RealtimeEventType.BARGE_IN_ACCEPTED: InterruptEventPayload,
        RealtimeEventType.BARGE_IN_REJECTED: InterruptEventPayload,
        RealtimeEventType.STALE_RESULT_DROPPED: DiagnosticEventPayload,
        RealtimeEventType.EVENT_OVERFLOW: DiagnosticEventPayload,
    }
)


def _normalize_event_sequence(
    value: EventSequence | int | None,
) -> EventSequence | None:
    if value is None:
        return None
    return EventSequence.parse(value)


def _normalize_generation_id(
    value: GenerationId | str | None,
) -> GenerationId | None:
    if value is None:
        return None
    if isinstance(value, GenerationId):
        return value
    if not isinstance(value, str):
        raise TypeError("generation_id must be a GenerationId, string, or None")
    return GenerationId.parse(value)


def _normalize_event_payload(
    value: RealtimeEventPayload | None,
) -> RealtimeEventPayload | None:
    if value is None:
        return None
    if not isinstance(value, _REALTIME_EVENT_PAYLOAD_TYPES):
        raise TypeError("payload must be a typed RealtimeEventPayload or None")
    return value


def _require_runtime_event_payload(
    event_type: RealtimeEventType | str,
    payload: RealtimeEventPayload | None,
) -> RealtimeEventPayload | None:
    """Validate the typed payload required by one runtime-emitted event category."""

    resolved_type = (
        event_type
        if isinstance(event_type, RealtimeEventType)
        else RealtimeEventType(str(event_type))
    )
    required_type = _RUNTIME_PAYLOAD_TYPE_BY_EVENT.get(resolved_type)
    if required_type is None:
        return _normalize_event_payload(payload)
    if payload is None:
        raise ValueError(
            f"{resolved_type.value} requires a typed {required_type.__name__} payload"
        )
    if not isinstance(payload, required_type):
        raise TypeError(
            f"{resolved_type.value} requires {required_type.__name__}, "
            f"not {type(payload).__name__}"
        )
    return payload


def _normalize_public_timestamp(
    value: float | int | None,
    *,
    field_name: str,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite non-negative number or None")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{field_name} must be a finite non-negative number")
    return normalized


def _normalize_terminal_flag(
    value: bool | None,
    *,
    event_type: RealtimeEventType,
) -> bool:
    inferred = event_type in _TERMINAL_REALTIME_EVENT_TYPES
    if value is None:
        return inferred
    if type(value) is not bool:
        raise TypeError("terminal must be a boolean or None")
    if value is not inferred:
        raise ValueError("terminal flag does not match realtime event type")
    return value


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
    CANCELLED = "cancelled"
    REJECTED = "rejected"


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
    sequence: EventSequence | int | None = None
    generation_id: GenerationId | str | None = None
    phase: RealtimePhase | str | None = None
    payload: RealtimeEventPayload | None = None
    terminal: bool | None = None
    timestamp: float | int | None = None
    monotonic_timestamp: float | int | None = None

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
        sequence = _normalize_event_sequence(self.sequence)
        generation_id = _normalize_generation_id(self.generation_id)
        phase = _normalize_realtime_phase(self.phase)
        payload = _normalize_event_payload(self.payload)
        terminal = _normalize_terminal_flag(self.terminal, event_type=event_type)
        timestamp = _normalize_public_timestamp(self.timestamp, field_name="timestamp")
        monotonic_timestamp = _normalize_public_timestamp(
            self.monotonic_timestamp,
            field_name="monotonic_timestamp",
        )

        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "session_id", normalize_session_id(self.session_id))
        object.__setattr__(self, "public_error_code", error_code)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))
        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(self, "generation_id", generation_id)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "terminal", terminal)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "monotonic_timestamp", monotonic_timestamp)

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

    def as_v6_dict(self) -> Mapping[str, Any]:
        """Return the immutable canonical v6 event-envelope mapping."""

        return MappingProxyType(
            {
                "type": self.type.value,
                "state": self.state.value,
                "previous_state": (
                    self.previous_state.value if self.previous_state else None
                ),
                "session_id": (
                    str(self.session_id) if self.session_id is not None else None
                ),
                "turn_id": str(self.turn_id) if self.turn_id is not None else None,
                "generation_id": (
                    str(self.generation_id)
                    if self.generation_id is not None
                    else None
                ),
                "sequence": (
                    int(self.sequence) if self.sequence is not None else None
                ),
                "phase": self.phase.value if self.phase is not None else None,
                "payload": (
                    self.payload.as_dict() if self.payload is not None else None
                ),
                "terminal": self.terminal,
                "timestamp": self.timestamp,
                "monotonic_timestamp": self.monotonic_timestamp,
                "boundary": self.boundary,
                "public_error_code": self.public_error_code.value,
                "safe_message": self.safe_message,
                "retryable": self.retryable,
                "public_metadata": self.public_metadata,
            }
        )


    def to_v5(self) -> RealtimeEvent | None:
        """Project this event to the explicit lossy v5 event vocabulary."""

        if self.type in _V5_REALTIME_EVENT_TYPES:
            return self
        mapped_type = _V6_TO_V5_REALTIME_EVENT_TYPE.get(self.type)
        if mapped_type is None:
            return None
        return replace(self, type=mapped_type)

    def as_v5_dict(self) -> Mapping[str, Any] | None:
        """Return the legacy ten-key mapping when a v5 projection exists."""

        mapped = self.to_v5()
        return mapped.as_dict() if mapped is not None else None


@dataclass(frozen=True)
class RealtimeTurn:
    """Provider-neutral public turn descriptor."""

    turn_id: TurnId | str = field(default_factory=TurnId.new)
    input_text: str = ""
    state: RealtimeState | str = RealtimeState.IDLE
    session_id: SessionId | str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)
    phase: RealtimePhase | str | None = None

    def __post_init__(self) -> None:
        state = self.state if isinstance(self.state, RealtimeState) else RealtimeState(str(self.state))
        phase = _normalize_realtime_phase(self.phase, legacy_state=state)
        if phase is None:
            raise LifecycleTransitionError(
                LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH
            )
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "session_id", normalize_session_id(self.session_id))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


_LEGACY_TERMINAL_OUTCOMES = {
    RealtimeState.COMPLETED: TurnOutcome.COMPLETED,
    RealtimeState.INTERRUPTED: TurnOutcome.INTERRUPTED,
    RealtimeState.FAILED: TurnOutcome.FAILED,
    RealtimeState.CLOSED: TurnOutcome.CLOSED,
}
_TRANSIENT_REALTIME_STATE_VALUES = frozenset(
    {
        RealtimeState.IDLE.value,
        RealtimeState.LISTENING.value,
        RealtimeState.TRANSCRIBING.value,
        RealtimeState.THINKING.value,
        RealtimeState.SPEAKING.value,
        RealtimeState.MOTION.value,
    }
)
_DEFAULT_RECOVERY_BY_OUTCOME = {
    TurnOutcome.COMPLETED: RecoveryAction.NONE,
    TurnOutcome.INTERRUPTED: RecoveryAction.RESET_TURN,
    TurnOutcome.CANCELLED: RecoveryAction.RESET_TURN,
    TurnOutcome.FAILED: RecoveryAction.RESET_SESSION,
    TurnOutcome.REJECTED: RecoveryAction.REUSE_SESSION,
    TurnOutcome.CLOSED: RecoveryAction.NONE,
}


def _normalize_turn_outcome(
    value: TurnOutcome | RealtimeState | str,
) -> TurnOutcome:
    if isinstance(value, TurnOutcome):
        return value
    if isinstance(value, RealtimeState):
        mapped = _LEGACY_TERMINAL_OUTCOMES.get(value)
        if mapped is not None:
            return mapped
        raise LifecycleTransitionError(
            LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH
        )

    text = str(value)
    if text in _TRANSIENT_REALTIME_STATE_VALUES:
        raise LifecycleTransitionError(
            LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH
        )
    return TurnOutcome(text)


def _normalize_recovery_action(
    value: RecoveryAction | str | None,
    *,
    outcome: TurnOutcome,
) -> RecoveryAction:
    if value is None:
        return _DEFAULT_RECOVERY_BY_OUTCOME[outcome]
    return value if isinstance(value, RecoveryAction) else RecoveryAction(str(value))


def _validate_recovery_contract(
    *,
    outcome: TurnOutcome,
    recovery_action: RecoveryAction,
    retryable: bool,
) -> None:
    if outcome in {TurnOutcome.COMPLETED, TurnOutcome.CLOSED} and recovery_action is not RecoveryAction.NONE:
        raise ValueError(
            "Completed or closed realtime turns cannot require a recovery action."
        )
    if retryable and recovery_action in {
        RecoveryAction.CLOSE_SESSION,
        RecoveryAction.PERMANENT_FAILURE,
    }:
        raise ValueError(
            "A retryable realtime turn cannot require session closure or permanent failure."
        )


@dataclass(frozen=True)
class RealtimeTurnResult:
    """Provider-neutral terminal result for one realtime turn."""

    turn_id: TurnId | str
    outcome: TurnOutcome | RealtimeState | str
    input_text: str = ""
    output_text: str = ""
    voice_input_result: Any | None = None
    text_chat_result: Any | None = None
    voice_output_result: Any | None = None
    motion_result: Any | None = None
    public_error_code: RealtimeErrorCode | str = RealtimeErrorCode.NONE
    safe_message: str = ""
    retryable: bool = False
    recovery_action: RecoveryAction | str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = _normalize_turn_outcome(self.outcome)
        recovery_action = _normalize_recovery_action(
            self.recovery_action,
            outcome=outcome,
        )
        _validate_recovery_contract(
            outcome=outcome,
            recovery_action=recovery_action,
            retryable=bool(self.retryable),
        )
        error_code = (
            self.public_error_code
            if isinstance(self.public_error_code, RealtimeErrorCode)
            else RealtimeErrorCode(str(self.public_error_code))
        )
        object.__setattr__(self, "turn_id", normalize_turn_id(self.turn_id))
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "recovery_action", recovery_action)
        object.__setattr__(self, "public_error_code", error_code)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @property
    def is_completed(self) -> bool:
        return self.outcome is TurnOutcome.COMPLETED

    @property
    def is_terminal(self) -> bool:
        return True

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
            outcome=TurnOutcome.COMPLETED,
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
            outcome=TurnOutcome.INTERRUPTED,
            public_error_code=RealtimeErrorCode.INTERRUPTED,
            safe_message=safe_message,
            retryable=True,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def cancelled(
        cls,
        *,
        turn_id: TurnId | str,
        safe_message: str = "Realtime turn was cancelled.",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "RealtimeTurnResult":
        return cls(
            turn_id=turn_id,
            outcome=TurnOutcome.CANCELLED,
            public_error_code=RealtimeErrorCode.CANCELLED,
            safe_message=safe_message,
            retryable=True,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def rejected(
        cls,
        *,
        turn_id: TurnId | str,
        safe_message: str = "Realtime turn was rejected before execution.",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "RealtimeTurnResult":
        return cls(
            turn_id=turn_id,
            outcome=TurnOutcome.REJECTED,
            public_error_code=RealtimeErrorCode.REJECTED,
            safe_message=safe_message,
            retryable=False,
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
        recovery_action: RecoveryAction | str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "RealtimeTurnResult":
        return cls(
            turn_id=turn_id,
            outcome=TurnOutcome.FAILED,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            recovery_action=recovery_action,
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
            outcome=TurnOutcome.CLOSED,
            public_error_code=RealtimeErrorCode.SESSION_CLOSED,
            safe_message=safe_message,
            retryable=False,
        )
