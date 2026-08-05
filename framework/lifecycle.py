"""Provider-neutral public lifecycle primitives for v6 realtime control.

This module separates transient realtime phase, terminal turn outcome, recovery
action, and public-safe transition failures. It must remain free of provider,
network, microphone, playback, VTS, and runtime orchestration imports.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class RealtimePhase(str, Enum):
    """Transient, non-terminal phase of one realtime session or turn."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    MOTION = "motion"
    RECOVERING = "recovering"


class TurnOutcome(str, Enum):
    """Terminal outcome of one admitted or rejected realtime turn."""

    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REJECTED = "rejected"
    CLOSED = "closed"


class RecoveryAction(str, Enum):
    """Provider-neutral recovery action after a terminal result or failure."""

    NONE = "none"
    REUSE_SESSION = "reuse_session"
    RESET_TURN = "reset_turn"
    RESET_SESSION = "reset_session"
    RECONNECT = "reconnect"
    CLOSE_SESSION = "close_session"
    PERMANENT_FAILURE = "permanent_failure"


class LifecycleTransitionErrorCode(str, Enum):
    """Stable public classification for lifecycle transition failures."""

    INVALID_PHASE_TRANSITION = "invalid_phase_transition"
    PHASE_OUTCOME_MISMATCH = "phase_outcome_mismatch"
    DUPLICATE_TERMINAL = "duplicate_terminal"
    TERMINAL_REGRESSION = "terminal_regression"
    SESSION_CLOSED = "session_closed"


_SAFE_MESSAGES = MappingProxyType(
    {
        LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION: (
            "The requested realtime phase transition is not allowed."
        ),
        LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH: (
            "A transient realtime phase cannot be used as a terminal turn outcome."
        ),
        LifecycleTransitionErrorCode.DUPLICATE_TERMINAL: (
            "A terminal turn outcome was already recorded."
        ),
        LifecycleTransitionErrorCode.TERMINAL_REGRESSION: (
            "A terminal turn outcome cannot transition to another terminal outcome."
        ),
        LifecycleTransitionErrorCode.SESSION_CLOSED: (
            "The realtime session is closed."
        ),
    }
)


class LifecycleTransitionError(ValueError):
    """Public-safe typed lifecycle transition failure."""

    def __init__(
        self,
        code: LifecycleTransitionErrorCode | str,
        *,
        from_phase: RealtimePhase | str | None = None,
        to_phase: RealtimePhase | str | None = None,
        existing_outcome: TurnOutcome | str | None = None,
        attempted_outcome: TurnOutcome | str | None = None,
    ) -> None:
        resolved_code = (
            code
            if isinstance(code, LifecycleTransitionErrorCode)
            else LifecycleTransitionErrorCode(str(code))
        )
        resolved_from = _optional_phase(from_phase)
        resolved_to = _optional_phase(to_phase)
        resolved_existing = _optional_outcome(existing_outcome)
        resolved_attempted = _optional_outcome(attempted_outcome)
        safe_message = _SAFE_MESSAGES[resolved_code]

        self.code = resolved_code
        self.from_phase = resolved_from
        self.to_phase = resolved_to
        self.existing_outcome = resolved_existing
        self.attempted_outcome = resolved_attempted
        self.safe_message = safe_message
        super().__init__(safe_message)


_PHASE_TRANSITIONS = MappingProxyType(
    {
        RealtimePhase.IDLE: frozenset(
            {
                RealtimePhase.LISTENING,
                RealtimePhase.TRANSCRIBING,
                RealtimePhase.THINKING,
                RealtimePhase.SPEAKING,
                RealtimePhase.MOTION,
            }
        ),
        RealtimePhase.LISTENING: frozenset(
            {
                RealtimePhase.TRANSCRIBING,
                RealtimePhase.THINKING,
                RealtimePhase.RECOVERING,
                RealtimePhase.IDLE,
            }
        ),
        RealtimePhase.TRANSCRIBING: frozenset(
            {
                RealtimePhase.THINKING,
                RealtimePhase.RECOVERING,
                RealtimePhase.IDLE,
            }
        ),
        RealtimePhase.THINKING: frozenset(
            {
                RealtimePhase.SPEAKING,
                RealtimePhase.MOTION,
                RealtimePhase.RECOVERING,
                RealtimePhase.IDLE,
            }
        ),
        RealtimePhase.SPEAKING: frozenset(
            {
                RealtimePhase.MOTION,
                RealtimePhase.RECOVERING,
                RealtimePhase.IDLE,
            }
        ),
        RealtimePhase.MOTION: frozenset(
            {
                RealtimePhase.SPEAKING,
                RealtimePhase.RECOVERING,
                RealtimePhase.IDLE,
            }
        ),
        RealtimePhase.RECOVERING: frozenset({RealtimePhase.IDLE}),
    }
)


def _phase(value: RealtimePhase | str) -> RealtimePhase:
    return value if isinstance(value, RealtimePhase) else RealtimePhase(str(value))


def _outcome(value: TurnOutcome | str) -> TurnOutcome:
    return value if isinstance(value, TurnOutcome) else TurnOutcome(str(value))


def _optional_phase(
    value: RealtimePhase | str | None,
) -> RealtimePhase | None:
    return None if value is None else _phase(value)


def _optional_outcome(
    value: TurnOutcome | str | None,
) -> TurnOutcome | None:
    return None if value is None else _outcome(value)


def validate_phase_transition(
    previous: RealtimePhase | str,
    next_phase: RealtimePhase | str,
) -> RealtimePhase:
    """Validate one transient phase transition and return its normalized target.

    Repeating the current phase is an idempotent no-op. Session closure is not a
    phase and is therefore represented by the session lifecycle boundary rather
    than this matrix.
    """

    resolved_previous = _phase(previous)
    resolved_next = _phase(next_phase)
    if resolved_previous is resolved_next:
        return resolved_next
    if resolved_next in _PHASE_TRANSITIONS[resolved_previous]:
        return resolved_next
    raise LifecycleTransitionError(
        LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION,
        from_phase=resolved_previous,
        to_phase=resolved_next,
    )


def validate_terminal_transition(
    existing: TurnOutcome | str | None,
    attempted: TurnOutcome | str,
) -> TurnOutcome:
    """Validate first-terminal ownership without implementing a registry."""

    resolved_existing = _optional_outcome(existing)
    resolved_attempted = _outcome(attempted)
    if resolved_existing is None:
        return resolved_attempted
    if resolved_existing is resolved_attempted:
        raise LifecycleTransitionError(
            LifecycleTransitionErrorCode.DUPLICATE_TERMINAL,
            existing_outcome=resolved_existing,
            attempted_outcome=resolved_attempted,
        )
    raise LifecycleTransitionError(
        LifecycleTransitionErrorCode.TERMINAL_REGRESSION,
        existing_outcome=resolved_existing,
        attempted_outcome=resolved_attempted,
    )


__all__ = [
    "RealtimePhase",
    "TurnOutcome",
    "RecoveryAction",
    "LifecycleTransitionErrorCode",
    "LifecycleTransitionError",
]
