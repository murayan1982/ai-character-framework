"""Provider-neutral whole-turn interrupt coordination result models.

FW-RT6-9a Control A defines public-safe subsystem reach and aggregate facts
only.  It does not track active stages, invoke a stage ``cancel`` method,
invalidate an artifact, wait for completion, or change
``RealtimeSession.interrupt`` execution.  Runtime adoption remains a
separately authorized control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Iterable, Mapping

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


def _normalize_timeout(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout_seconds must be a number or None")
    normalized = float(value)
    if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError("timeout_seconds must be finite and greater than zero")
    return normalized


def _normalize_safe_message(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("safe_message must be a string")
    sanitized = sanitize_public_value(value.strip())
    if not isinstance(sanitized, str):
        raise TypeError("safe_message must normalize to public-safe text")
    if sanitized == REDACTED_PATH:
        return "Interrupt coordination is unavailable."
    return sanitized


class InterruptSubsystem(str, Enum):
    """Stable provider-neutral targets of one whole-turn interrupt."""

    TEXT_GENERATION = "text_generation"
    TTS_GENERATION = "tts_generation"
    TTS_QUEUE = "tts_queue"
    AUDIO_ARTIFACT = "audio_artifact"
    MOTION = "motion"


class InterruptSubsystemOutcome(str, Enum):
    """Outcome reported by one targeted interrupt subsystem."""

    COMPLETED = "completed"
    REQUESTED = "requested"
    NOT_ACTIVE = "not_active"
    ALREADY_TERMINAL = "already_terminal"
    UNSUPPORTED = "unsupported"
    TIMED_OUT = "timed_out"
    ALREADY_CLOSED = "already_closed"
    FAILED = "failed"


class InterruptAggregateOutcome(str, Enum):
    """Truthful aggregate of all targeted subsystem results."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    REQUESTED = "requested"
    NO_ACTIVE_TURN = "no_active_turn"
    ALREADY_TERMINAL = "already_terminal"
    UNSUPPORTED = "unsupported"
    TIMED_OUT = "timed_out"
    ALREADY_CLOSED = "already_closed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class InterruptSubsystemResult:
    """Public-safe reach and effect facts for one interrupt subsystem.

    Cooperative cancellation, provider hard cancellation, and suppression of
    future Framework delivery are independent facts.  None may be inferred
    from another.
    """

    subsystem: InterruptSubsystem | str
    outcome: InterruptSubsystemOutcome | str
    session_id: SessionId | str
    turn_id: TurnId | str | None = None
    generation_id: GenerationId | str | None = None
    target_reached: bool = False
    cooperative_cancel_requested: bool = False
    cooperative_cancel_accepted: bool = False
    cooperative_cancel_completed: bool = False
    provider_hard_cancel_supported: bool = False
    provider_hard_cancel_applied: bool = False
    future_delivery_suppressed: bool = False
    affected_count: int = 0
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        subsystem = (
            self.subsystem
            if isinstance(self.subsystem, InterruptSubsystem)
            else InterruptSubsystem(str(self.subsystem))
        )
        outcome = (
            self.outcome
            if isinstance(self.outcome, InterruptSubsystemOutcome)
            else InterruptSubsystemOutcome(str(self.outcome))
        )
        session_id = normalize_session_id(self.session_id)
        turn_id = normalize_turn_id(self.turn_id)
        generation_id = _normalize_generation_id(self.generation_id)
        if session_id is None:
            raise ValueError("session_id must identify one Framework session")
        if generation_id is not None and turn_id is None:
            raise ValueError("generation_id requires turn_id")

        bool_fields = {
            "target_reached": self.target_reached,
            "cooperative_cancel_requested": self.cooperative_cancel_requested,
            "cooperative_cancel_accepted": self.cooperative_cancel_accepted,
            "cooperative_cancel_completed": self.cooperative_cancel_completed,
            "provider_hard_cancel_supported": self.provider_hard_cancel_supported,
            "provider_hard_cancel_applied": self.provider_hard_cancel_applied,
            "future_delivery_suppressed": self.future_delivery_suppressed,
            "retryable": self.retryable,
        }
        normalized_bools = {
            name: _require_bool(value, field_name=name)
            for name, value in bool_fields.items()
        }
        if isinstance(self.affected_count, bool) or not isinstance(
            self.affected_count, int
        ):
            raise TypeError("affected_count must be an integer")
        if self.affected_count < 0:
            raise ValueError("affected_count must be non-negative")

        reached = normalized_bools["target_reached"]
        requested = normalized_bools["cooperative_cancel_requested"]
        accepted = normalized_bools["cooperative_cancel_accepted"]
        completed = normalized_bools["cooperative_cancel_completed"]
        hard_supported = normalized_bools["provider_hard_cancel_supported"]
        hard_applied = normalized_bools["provider_hard_cancel_applied"]
        suppressed = normalized_bools["future_delivery_suppressed"]

        if accepted and not requested:
            raise ValueError(
                "cooperative_cancel_accepted requires a cancellation request"
            )
        if completed and not accepted:
            raise ValueError(
                "cooperative_cancel_completed requires accepted cancellation"
            )
        if hard_applied and not hard_supported:
            raise ValueError(
                "provider_hard_cancel_applied requires advertised support"
            )
        if any((accepted, completed, hard_applied, suppressed, self.affected_count)) and not reached:
            raise ValueError("reported interrupt effects require target_reached")

        active_outcomes = {
            InterruptSubsystemOutcome.COMPLETED,
            InterruptSubsystemOutcome.REQUESTED,
            InterruptSubsystemOutcome.TIMED_OUT,
            InterruptSubsystemOutcome.FAILED,
        }
        if outcome in active_outcomes and (not reached or turn_id is None):
            raise ValueError(
                "active subsystem outcomes require a reached target and turn_id"
            )
        if outcome is InterruptSubsystemOutcome.REQUESTED and not (
            requested and accepted and not completed
        ):
            raise ValueError(
                "REQUESTED requires accepted but incomplete cooperative cancellation"
            )
        if outcome is InterruptSubsystemOutcome.TIMED_OUT and not (
            requested and accepted and not completed
        ):
            raise ValueError(
                "TIMED_OUT requires accepted but incomplete cooperative cancellation"
            )
        if outcome is InterruptSubsystemOutcome.COMPLETED and not any(
            (completed, hard_applied, suppressed, self.affected_count > 0)
        ):
            raise ValueError("COMPLETED requires one truthful completed effect")

        no_effect_outcomes = {
            InterruptSubsystemOutcome.NOT_ACTIVE,
            InterruptSubsystemOutcome.ALREADY_TERMINAL,
            InterruptSubsystemOutcome.UNSUPPORTED,
            InterruptSubsystemOutcome.ALREADY_CLOSED,
        }
        if outcome in no_effect_outcomes and any(
            (accepted, completed, hard_applied, suppressed, self.affected_count)
        ):
            raise ValueError(
                "non-effect subsystem outcomes must not claim interrupt effects"
            )
        if outcome is InterruptSubsystemOutcome.UNSUPPORTED and hard_supported:
            raise ValueError("UNSUPPORTED must not advertise provider hard cancel")
        if outcome is InterruptSubsystemOutcome.ALREADY_CLOSED and reached:
            raise ValueError("ALREADY_CLOSED must not claim target reach")

        object.__setattr__(self, "subsystem", subsystem)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "turn_id", turn_id)
        object.__setattr__(self, "generation_id", generation_id)
        for name, value in normalized_bools.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "safe_message", _normalize_safe_message(self.safe_message))
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def effective(self) -> bool:
        """Whether this subsystem truthfully reports an interrupt effect."""

        return any(
            (
                self.cooperative_cancel_accepted,
                self.cooperative_cancel_completed,
                self.provider_hard_cancel_applied,
                self.future_delivery_suppressed,
                self.affected_count > 0,
            )
        )

    @property
    def is_terminal(self) -> bool:
        """Whether this subsystem attempt has a terminal observation."""

        return self.outcome is not InterruptSubsystemOutcome.REQUESTED


def _derive_aggregate_outcome(
    results: tuple[InterruptSubsystemResult, ...],
) -> InterruptAggregateOutcome:
    if not results:
        raise ValueError("subsystem_results must contain at least one target")
    outcomes = {result.outcome for result in results}
    if len(outcomes) != 1:
        return InterruptAggregateOutcome.PARTIAL
    only = next(iter(outcomes))
    return {
        InterruptSubsystemOutcome.COMPLETED: InterruptAggregateOutcome.COMPLETED,
        InterruptSubsystemOutcome.REQUESTED: InterruptAggregateOutcome.REQUESTED,
        InterruptSubsystemOutcome.NOT_ACTIVE: InterruptAggregateOutcome.NO_ACTIVE_TURN,
        InterruptSubsystemOutcome.ALREADY_TERMINAL: InterruptAggregateOutcome.ALREADY_TERMINAL,
        InterruptSubsystemOutcome.UNSUPPORTED: InterruptAggregateOutcome.UNSUPPORTED,
        InterruptSubsystemOutcome.TIMED_OUT: InterruptAggregateOutcome.TIMED_OUT,
        InterruptSubsystemOutcome.ALREADY_CLOSED: InterruptAggregateOutcome.ALREADY_CLOSED,
        InterruptSubsystemOutcome.FAILED: InterruptAggregateOutcome.FAILED,
    }[only]


@dataclass(frozen=True, slots=True)
class InterruptAggregateResult:
    """Validated aggregate of all explicitly targeted subsystem results."""

    outcome: InterruptAggregateOutcome | str
    session_id: SessionId | str
    turn_id: TurnId | str | None
    subsystem_results: tuple[InterruptSubsystemResult, ...]
    timeout_seconds: float | None = None
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, InterruptAggregateOutcome)
            else InterruptAggregateOutcome(str(self.outcome))
        )
        session_id = normalize_session_id(self.session_id)
        turn_id = normalize_turn_id(self.turn_id)
        if session_id is None:
            raise ValueError("session_id must identify one Framework session")
        try:
            results = tuple(self.subsystem_results)
        except TypeError as exc:
            raise TypeError("subsystem_results must be an iterable of results") from exc
        if not all(isinstance(item, InterruptSubsystemResult) for item in results):
            raise TypeError(
                "subsystem_results must contain InterruptSubsystemResult values"
            )
        subsystems = tuple(item.subsystem for item in results)
        if len(set(subsystems)) != len(subsystems):
            raise ValueError("subsystem_results must contain unique subsystems")
        for result in results:
            if result.session_id != session_id:
                raise ValueError("subsystem result session_id must match aggregate")
            if turn_id is not None and result.turn_id is not None and result.turn_id != turn_id:
                raise ValueError("subsystem result turn_id must match aggregate")
        expected = _derive_aggregate_outcome(results)
        if outcome is not expected:
            raise ValueError(
                f"aggregate outcome must be derived as {expected.value}"
            )

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "turn_id", turn_id)
        object.__setattr__(self, "subsystem_results", results)
        object.__setattr__(self, "timeout_seconds", _normalize_timeout(self.timeout_seconds))
        object.__setattr__(self, "safe_message", _normalize_safe_message(self.safe_message))
        object.__setattr__(
            self,
            "retryable",
            _require_bool(self.retryable, field_name="retryable"),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @classmethod
    def from_results(
        cls,
        *,
        session_id: SessionId | str,
        turn_id: TurnId | str | None,
        subsystem_results: Iterable[InterruptSubsystemResult],
        timeout_seconds: float | None = None,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, object] | None = None,
    ) -> "InterruptAggregateResult":
        """Build an aggregate whose outcome cannot be caller-overclaimed."""

        results = tuple(subsystem_results)
        return cls(
            outcome=_derive_aggregate_outcome(results),
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=results,
            timeout_seconds=timeout_seconds,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
        )

    @property
    def partial(self) -> bool:
        return self.outcome is InterruptAggregateOutcome.PARTIAL

    @property
    def is_terminal(self) -> bool:
        return all(result.is_terminal for result in self.subsystem_results)

    @property
    def completed_count(self) -> int:
        return sum(
            result.outcome is InterruptSubsystemOutcome.COMPLETED
            for result in self.subsystem_results
        )

    @property
    def timed_out_count(self) -> int:
        return sum(
            result.outcome is InterruptSubsystemOutcome.TIMED_OUT
            for result in self.subsystem_results
        )


__all__ = [
    "InterruptAggregateOutcome",
    "InterruptAggregateResult",
    "InterruptSubsystem",
    "InterruptSubsystemOutcome",
    "InterruptSubsystemResult",
]
