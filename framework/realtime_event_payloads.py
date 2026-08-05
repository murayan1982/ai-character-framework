"""Provider-neutral typed payload models for v6 realtime events.

The payloads in this module are immutable public data models. They never retain
provider SDK objects, raw provider responses, raw exceptions, credentials, or
local/private filesystem paths. Runtime event-envelope adoption is intentionally
outside FW-RT6-1c Control A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping, TypeAlias

from .identity import EventSequence
from .lifecycle import RecoveryAction, TurnOutcome
from .motion import MotionOutcome
from .output_control import InterruptOutcome, InterruptScope


class RealtimeEventPayloadKind(str, Enum):
    """Stable discriminator for one public realtime event payload."""

    LIFECYCLE = "lifecycle"
    TRANSCRIPT = "transcript"
    RESPONSE = "response"
    SYNTHESIS = "synthesis"
    AUDIO = "audio"
    MOTION = "motion"
    INTERRUPT = "interrupt"
    DIAGNOSTIC = "diagnostic"


def _require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    return value


def _require_optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name=field_name)


def _require_bool(value: object, *, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _normalize_non_negative_int(
    value: object,
    *,
    field_name: str,
    allow_none: bool = False,
) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _normalize_confidence(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("confidence must be a number or None")
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
    return confidence


def _looks_like_private_path_or_secret(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    if "\\" in normalized or "/" in normalized:
        return True
    if len(normalized) >= 2 and normalized[1] == ":":
        return True
    lowered = normalized.lower()
    return any(
        token in lowered
        for token in (
            "api_key",
            "apikey",
            "authorization",
            "credential",
            "password",
            "secret",
            "token",
        )
    )


def _normalize_artifact_ref(value: object) -> str | None:
    artifact_ref = _require_optional_string(value, field_name="artifact_ref")
    if artifact_ref is None:
        return None
    if not artifact_ref.strip():
        raise ValueError("artifact_ref must be a non-empty opaque string")
    if _looks_like_private_path_or_secret(artifact_ref):
        raise ValueError("artifact_ref must not expose a private path or credential")
    return artifact_ref


def _mapping(**values: object) -> Mapping[str, object]:
    return MappingProxyType(values)


@dataclass(frozen=True)
class LifecycleEventPayload:
    """Typed terminal/recovery context for lifecycle events."""

    outcome: TurnOutcome | str | None = None
    recovery_action: RecoveryAction | str = RecoveryAction.NONE
    reason: str = ""
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.LIFECYCLE,
    )

    def __post_init__(self) -> None:
        outcome = self.outcome
        if outcome is not None and not isinstance(outcome, TurnOutcome):
            outcome = TurnOutcome(str(outcome))
        recovery_action = (
            self.recovery_action
            if isinstance(self.recovery_action, RecoveryAction)
            else RecoveryAction(str(self.recovery_action))
        )
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "recovery_action", recovery_action)
        object.__setattr__(self, "reason", _require_string(self.reason, field_name="reason"))

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            outcome=self.outcome.value if self.outcome is not None else None,
            recovery_action=self.recovery_action.value,
            reason=self.reason,
        )


@dataclass(frozen=True)
class TranscriptEventPayload:
    """Typed transcript payload with an explicit partial/final distinction."""

    text: str
    is_final: bool
    confidence: float | None = None
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.TRANSCRIPT,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _require_string(self.text, field_name="text"))
        object.__setattr__(
            self,
            "is_final",
            _require_bool(self.is_final, field_name="is_final"),
        )
        object.__setattr__(self, "confidence", _normalize_confidence(self.confidence))

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            text=self.text,
            is_final=self.is_final,
            confidence=self.confidence,
        )


@dataclass(frozen=True)
class ResponseEventPayload:
    """Typed response payload with explicit delta/final semantics."""

    text: str
    delta_index: int | None = None
    is_final: bool = False
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.RESPONSE,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _require_string(self.text, field_name="text"))
        object.__setattr__(
            self,
            "delta_index",
            _normalize_non_negative_int(
                self.delta_index,
                field_name="delta_index",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "is_final",
            _require_bool(self.is_final, field_name="is_final"),
        )

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            text=self.text,
            delta_index=self.delta_index,
            is_final=self.is_final,
        )


@dataclass(frozen=True)
class SynthesisEventPayload:
    """Typed provider-neutral voice synthesis state."""

    request_state: str
    audio_format: str | None = None
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.SYNTHESIS,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_state",
            _require_string(self.request_state, field_name="request_state"),
        )
        object.__setattr__(
            self,
            "audio_format",
            _require_optional_string(self.audio_format, field_name="audio_format"),
        )

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            request_state=self.request_state,
            audio_format=self.audio_format,
        )


@dataclass(frozen=True)
class AudioEventPayload:
    """Typed audio handoff/invalidation state using an opaque artifact reference."""

    artifact_ref: str | None = None
    available: bool = False
    invalidated: bool = False
    host_stop_requested: bool = False
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.AUDIO,
    )

    def __post_init__(self) -> None:
        artifact_ref = _normalize_artifact_ref(self.artifact_ref)
        available = _require_bool(self.available, field_name="available")
        invalidated = _require_bool(self.invalidated, field_name="invalidated")
        host_stop_requested = _require_bool(
            self.host_stop_requested,
            field_name="host_stop_requested",
        )
        if available and invalidated:
            raise ValueError("audio payload cannot be available and invalidated together")
        if available and artifact_ref is None:
            raise ValueError("available audio requires an opaque artifact_ref")
        object.__setattr__(self, "artifact_ref", artifact_ref)
        object.__setattr__(self, "available", available)
        object.__setattr__(self, "invalidated", invalidated)
        object.__setattr__(self, "host_stop_requested", host_stop_requested)

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            artifact_ref=self.artifact_ref,
            available=self.available,
            invalidated=self.invalidated,
            host_stop_requested=self.host_stop_requested,
        )


@dataclass(frozen=True)
class MotionEventPayload:
    """Typed provider-neutral motion request/result payload."""

    request_id: str
    outcome: MotionOutcome | str | None = None
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.MOTION,
    )

    def __post_init__(self) -> None:
        request_id = _require_string(self.request_id, field_name="request_id")
        if not request_id.strip():
            raise ValueError("request_id must be non-empty")
        outcome = self.outcome
        if outcome is not None and not isinstance(outcome, MotionOutcome):
            outcome = MotionOutcome(str(outcome))
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "outcome", outcome)

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            request_id=self.request_id,
            outcome=self.outcome.value if self.outcome is not None else None,
        )


@dataclass(frozen=True)
class InterruptEventPayload:
    """Typed provider-neutral interrupt scope/result payload."""

    scope: InterruptScope | str
    outcome: InterruptOutcome | str
    reason: str = ""
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.INTERRUPT,
    )

    def __post_init__(self) -> None:
        scope = (
            self.scope
            if isinstance(self.scope, InterruptScope)
            else InterruptScope(str(self.scope))
        )
        outcome = (
            self.outcome
            if isinstance(self.outcome, InterruptOutcome)
            else InterruptOutcome(str(self.outcome))
        )
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "reason", _require_string(self.reason, field_name="reason"))

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            scope=self.scope.value,
            outcome=self.outcome.value,
            reason=self.reason,
        )


@dataclass(frozen=True)
class DiagnosticEventPayload:
    """Typed public-safe event drop/overflow diagnostic."""

    code: str
    drop_reason: str = ""
    dropped_sequence: EventSequence | int | None = None
    overflow_count: int = 0
    kind: RealtimeEventPayloadKind = field(
        init=False,
        default=RealtimeEventPayloadKind.DIAGNOSTIC,
    )

    def __post_init__(self) -> None:
        code = _require_string(self.code, field_name="code")
        if not code.strip():
            raise ValueError("code must be non-empty")
        dropped_sequence = self.dropped_sequence
        if dropped_sequence is not None:
            dropped_sequence = EventSequence.parse(dropped_sequence)
        overflow_count = _normalize_non_negative_int(
            self.overflow_count,
            field_name="overflow_count",
        )
        object.__setattr__(self, "code", code)
        object.__setattr__(
            self,
            "drop_reason",
            _require_string(self.drop_reason, field_name="drop_reason"),
        )
        object.__setattr__(self, "dropped_sequence", dropped_sequence)
        object.__setattr__(self, "overflow_count", overflow_count)

    def as_dict(self) -> Mapping[str, object]:
        return _mapping(
            kind=self.kind.value,
            code=self.code,
            drop_reason=self.drop_reason,
            dropped_sequence=(
                int(self.dropped_sequence)
                if self.dropped_sequence is not None
                else None
            ),
            overflow_count=self.overflow_count,
        )


RealtimeEventPayload: TypeAlias = (
    LifecycleEventPayload
    | TranscriptEventPayload
    | ResponseEventPayload
    | SynthesisEventPayload
    | AudioEventPayload
    | MotionEventPayload
    | InterruptEventPayload
    | DiagnosticEventPayload
)


__all__ = [
    "RealtimeEventPayloadKind",
    "LifecycleEventPayload",
    "TranscriptEventPayload",
    "ResponseEventPayload",
    "SynthesisEventPayload",
    "AudioEventPayload",
    "MotionEventPayload",
    "InterruptEventPayload",
    "DiagnosticEventPayload",
    "RealtimeEventPayload",
]
