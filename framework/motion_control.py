"""Provider-neutral motion cancellation and stop-reach result models.

FW-RT6-8c Control A defines typed public-safe facts only.  This package does
not track active requests, call ``MotionStage.cancel``, execute a
``STOP_MOTION`` intent, import a provider SDK, or change whole-turn interrupt
execution.  Runtime adoption remains a separately authorized control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .identity import (
    GenerationId,
    SessionId,
    TurnId,
    normalize_session_id,
    normalize_turn_id,
)
from .public_safety import REDACTED_PATH, public_mapping, sanitize_public_value


def _require_bool(value: object, *, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _normalize_generation_id(
    value: GenerationId | str | None,
) -> GenerationId | None:
    if value is None or isinstance(value, GenerationId):
        return value
    if not isinstance(value, str):
        raise TypeError("generation_id must be a GenerationId, string, or None")
    return GenerationId.parse(value)


def _normalize_request_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("request_id must be a string or None")
    normalized = value.strip()
    if not normalized:
        raise ValueError("request_id must not be blank")
    return normalized


def _normalize_safe_message(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("safe_message must be a string")
    sanitized = sanitize_public_value(value.strip())
    if not isinstance(sanitized, str):
        raise TypeError("safe_message must normalize to public-safe text")
    if sanitized == REDACTED_PATH:
        return "Motion control is unavailable."
    return sanitized


class MotionControlOutcome(str, Enum):
    """Typed outcome of one Framework motion-control attempt."""

    REQUESTED = "requested"
    COMPLETED = "completed"
    NOT_ACTIVE = "not_active"
    ALREADY_TERMINAL = "already_terminal"
    UNSUPPORTED = "unsupported"
    TIMED_OUT = "timed_out"
    ALREADY_CLOSED = "already_closed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MotionControlResult:
    """Public-safe request-cancel and provider-stop reach for one motion.

    ``cancel_*`` fields describe cancellation of one Framework-owned in-flight
    request.  ``stop_motion_*`` fields separately describe the explicit
    provider-neutral ``STOP_MOTION`` intent.  Neither family may infer success
    from the other.
    """

    outcome: MotionControlOutcome | str
    session_id: SessionId | str
    turn_id: TurnId | str | None = None
    generation_id: GenerationId | str | None = None
    request_id: str | None = None
    cancel_requested: bool = False
    cancel_accepted: bool = False
    cancel_completed: bool = False
    stop_motion_requested: bool = False
    stop_motion_supported: bool = False
    stop_motion_applied: bool = False
    future_delivery_suppressed: bool = False
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, MotionControlOutcome)
            else MotionControlOutcome(str(self.outcome))
        )
        session_id = normalize_session_id(self.session_id)
        turn_id = normalize_turn_id(self.turn_id)
        generation_id = _normalize_generation_id(self.generation_id)
        request_id = _normalize_request_id(self.request_id)
        if session_id is None:
            raise ValueError("session_id must identify one Framework session")
        if generation_id is not None and turn_id is None:
            raise ValueError("generation_id requires turn_id")

        cancel_requested = _require_bool(
            self.cancel_requested,
            field_name="cancel_requested",
        )
        cancel_accepted = _require_bool(
            self.cancel_accepted,
            field_name="cancel_accepted",
        )
        cancel_completed = _require_bool(
            self.cancel_completed,
            field_name="cancel_completed",
        )
        stop_motion_requested = _require_bool(
            self.stop_motion_requested,
            field_name="stop_motion_requested",
        )
        stop_motion_supported = _require_bool(
            self.stop_motion_supported,
            field_name="stop_motion_supported",
        )
        stop_motion_applied = _require_bool(
            self.stop_motion_applied,
            field_name="stop_motion_applied",
        )
        future_delivery_suppressed = _require_bool(
            self.future_delivery_suppressed,
            field_name="future_delivery_suppressed",
        )
        retryable = _require_bool(self.retryable, field_name="retryable")

        if cancel_accepted and not cancel_requested:
            raise ValueError("cancel_accepted requires cancel_requested")
        if cancel_completed and not cancel_accepted:
            raise ValueError("cancel_completed requires accepted cancellation")
        if future_delivery_suppressed and not cancel_requested:
            raise ValueError(
                "future_delivery_suppressed requires a cancellation request"
            )
        if stop_motion_applied and not (
            stop_motion_requested and stop_motion_supported
        ):
            raise ValueError(
                "stop_motion_applied requires requested and supported stop motion"
            )

        active_outcomes = {
            MotionControlOutcome.REQUESTED,
            MotionControlOutcome.COMPLETED,
            MotionControlOutcome.TIMED_OUT,
            MotionControlOutcome.FAILED,
        }
        if outcome in active_outcomes and (
            turn_id is None or generation_id is None or request_id is None
        ):
            raise ValueError(
                "active motion-control outcomes require turn, generation, and request IDs"
            )
        if outcome is MotionControlOutcome.REQUESTED and not (
            cancel_requested and cancel_accepted and not cancel_completed
        ):
            raise ValueError(
                "REQUESTED requires accepted but incomplete request cancellation"
            )
        if outcome is MotionControlOutcome.COMPLETED and not (
            cancel_completed or stop_motion_applied
        ):
            raise ValueError(
                "COMPLETED requires completed cancellation or applied stop motion"
            )
        if outcome is MotionControlOutcome.TIMED_OUT and not (
            cancel_requested and cancel_accepted and not cancel_completed
        ):
            raise ValueError(
                "TIMED_OUT requires accepted but incomplete request cancellation"
            )

        no_effect_outcomes = {
            MotionControlOutcome.NOT_ACTIVE,
            MotionControlOutcome.ALREADY_TERMINAL,
            MotionControlOutcome.UNSUPPORTED,
            MotionControlOutcome.ALREADY_CLOSED,
        }
        if outcome in no_effect_outcomes and any(
            (
                cancel_requested,
                cancel_accepted,
                cancel_completed,
                stop_motion_applied,
                future_delivery_suppressed,
            )
        ):
            raise ValueError(
                "non-effect motion-control outcomes must not claim control effects"
            )

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "turn_id", turn_id)
        object.__setattr__(self, "generation_id", generation_id)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "cancel_requested", cancel_requested)
        object.__setattr__(self, "cancel_accepted", cancel_accepted)
        object.__setattr__(self, "cancel_completed", cancel_completed)
        object.__setattr__(self, "stop_motion_requested", stop_motion_requested)
        object.__setattr__(self, "stop_motion_supported", stop_motion_supported)
        object.__setattr__(self, "stop_motion_applied", stop_motion_applied)
        object.__setattr__(
            self,
            "future_delivery_suppressed",
            future_delivery_suppressed,
        )
        object.__setattr__(self, "safe_message", _normalize_safe_message(self.safe_message))
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def effective(self) -> bool:
        """Whether Framework or an adapter truthfully reported an effect."""

        return any(
            (
                self.cancel_accepted,
                self.cancel_completed,
                self.stop_motion_applied,
                self.future_delivery_suppressed,
            )
        )

    @property
    def is_terminal(self) -> bool:
        """All motion-control attempts resolve to one typed result."""

        return True


__all__ = [
    "MotionControlOutcome",
    "MotionControlResult",
]
