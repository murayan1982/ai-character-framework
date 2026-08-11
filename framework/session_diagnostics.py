"""Provider-neutral immutable public diagnostics models.

This explicit package contains projection and validation only.  Runtime
snapshot ownership remains with the public session and is adopted separately.
The models intentionally retain no text, audio, provider payload, metadata,
exception, credential, callback, thread, client, or filesystem value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .identity import GenerationId, SessionId, TurnId
from .lifecycle import RealtimePhase, RecoveryAction, TurnOutcome
from .realtime import RealtimeErrorCode, RealtimeState, RealtimeTurnResult


def _public_id(value: Any, expected_type: type, field_name: str):
    if isinstance(value, expected_type):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a {expected_type.__name__} or string")
    return expected_type.parse(value)


def _optional_public_id(value: Any, expected_type: type, field_name: str):
    if value is None:
        return None
    return _public_id(value, expected_type, field_name)


def _count(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class SessionTerminalSnapshot:
    """Public-safe projection of one terminal realtime result."""

    session_id: SessionId | str
    turn_id: TurnId | str
    generation_id: GenerationId | str | None
    outcome: TurnOutcome | str
    public_error_code: RealtimeErrorCode | str
    retryable: bool
    recovery_action: RecoveryAction | str

    def __post_init__(self) -> None:
        if type(self.retryable) is not bool:
            raise TypeError("retryable must be a boolean")
        object.__setattr__(
            self,
            "session_id",
            _public_id(self.session_id, SessionId, "session_id"),
        )
        object.__setattr__(
            self,
            "turn_id",
            _public_id(self.turn_id, TurnId, "turn_id"),
        )
        object.__setattr__(
            self,
            "generation_id",
            _optional_public_id(
                self.generation_id,
                GenerationId,
                "generation_id",
            ),
        )
        object.__setattr__(
            self,
            "outcome",
            self.outcome
            if isinstance(self.outcome, TurnOutcome)
            else TurnOutcome(str(self.outcome)),
        )
        object.__setattr__(
            self,
            "public_error_code",
            self.public_error_code
            if isinstance(self.public_error_code, RealtimeErrorCode)
            else RealtimeErrorCode(str(self.public_error_code)),
        )
        object.__setattr__(
            self,
            "recovery_action",
            self.recovery_action
            if isinstance(self.recovery_action, RecoveryAction)
            else RecoveryAction(str(self.recovery_action)),
        )

    def as_dict(self) -> dict[str, str | bool | None]:
        """Return the exact JSON-friendly public-safe terminal surface."""

        return {
            "session_id": str(self.session_id),
            "turn_id": str(self.turn_id),
            "generation_id": (
                None if self.generation_id is None else str(self.generation_id)
            ),
            "outcome": self.outcome.value,
            "public_error_code": self.public_error_code.value,
            "retryable": self.retryable,
            "recovery_action": self.recovery_action.value,
        }


@dataclass(frozen=True, slots=True)
class SessionDiagnosticsSnapshot:
    """One coherent, immutable and provider-neutral operator snapshot."""

    session_id: SessionId | str
    state: RealtimeState | str
    phase: RealtimePhase | str | None
    is_closed: bool
    active_turn_id: TurnId | str | None
    active_generation_id: GenerationId | str | None
    queue_depth: int
    active_generation_count: int
    last_terminal_result: SessionTerminalSnapshot | None
    last_safe_error_code: RealtimeErrorCode | str
    stale_completion_count: int
    duplicate_terminal_count: int
    overflow_count: int

    def __post_init__(self) -> None:
        if type(self.is_closed) is not bool:
            raise TypeError("is_closed must be a boolean")
        session_id = _public_id(self.session_id, SessionId, "session_id")
        state = (
            self.state
            if isinstance(self.state, RealtimeState)
            else RealtimeState(str(self.state))
        )
        phase = self.phase
        if phase is not None and not isinstance(phase, RealtimePhase):
            phase = RealtimePhase(str(phase))
        active_turn_id = _optional_public_id(
            self.active_turn_id,
            TurnId,
            "active_turn_id",
        )
        active_generation_id = _optional_public_id(
            self.active_generation_id,
            GenerationId,
            "active_generation_id",
        )
        queue_depth = _count(self.queue_depth, "queue_depth")
        active_generation_count = _count(
            self.active_generation_count,
            "active_generation_count",
        )
        stale_completion_count = _count(
            self.stale_completion_count,
            "stale_completion_count",
        )
        duplicate_terminal_count = _count(
            self.duplicate_terminal_count,
            "duplicate_terminal_count",
        )
        overflow_count = _count(self.overflow_count, "overflow_count")
        if active_generation_count not in (0, 1):
            raise ValueError("active_generation_count must be 0 or 1")
        if (active_turn_id is None) != (active_generation_id is None):
            raise ValueError(
                "active_turn_id and active_generation_id must both be present or both be None"
            )
        expected_active_count = 0 if active_generation_id is None else 1
        if active_generation_count != expected_active_count:
            raise ValueError(
                "active_generation_count must match the active turn/generation context"
            )
        if self.is_closed and active_turn_id is not None:
            raise ValueError("closed diagnostics cannot retain an active context")
        if self.is_closed != (state is RealtimeState.CLOSED):
            raise ValueError("is_closed must match RealtimeState.CLOSED")
        terminal = self.last_terminal_result
        if terminal is not None and not isinstance(terminal, SessionTerminalSnapshot):
            raise TypeError(
                "last_terminal_result must be a SessionTerminalSnapshot or None"
            )
        if terminal is not None and terminal.session_id != session_id:
            raise ValueError("last_terminal_result session_id must match session_id")
        error_code = (
            self.last_safe_error_code
            if isinstance(self.last_safe_error_code, RealtimeErrorCode)
            else RealtimeErrorCode(str(self.last_safe_error_code))
        )
        expected_error = (
            RealtimeErrorCode.NONE
            if terminal is None
            else terminal.public_error_code
        )
        if error_code is not expected_error:
            raise ValueError(
                "last_safe_error_code must be derived from last_terminal_result"
            )

        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "active_turn_id", active_turn_id)
        object.__setattr__(self, "active_generation_id", active_generation_id)
        object.__setattr__(self, "queue_depth", queue_depth)
        object.__setattr__(self, "active_generation_count", active_generation_count)
        object.__setattr__(self, "last_safe_error_code", error_code)
        object.__setattr__(self, "stale_completion_count", stale_completion_count)
        object.__setattr__(self, "duplicate_terminal_count", duplicate_terminal_count)
        object.__setattr__(self, "overflow_count", overflow_count)

    def as_dict(self) -> dict[str, object]:
        """Return the exact JSON-friendly public-safe diagnostics surface."""

        return {
            "session_id": str(self.session_id),
            "state": self.state.value,
            "phase": None if self.phase is None else self.phase.value,
            "is_closed": self.is_closed,
            "active_turn_id": (
                None if self.active_turn_id is None else str(self.active_turn_id)
            ),
            "active_generation_id": (
                None
                if self.active_generation_id is None
                else str(self.active_generation_id)
            ),
            "queue_depth": self.queue_depth,
            "active_generation_count": self.active_generation_count,
            "last_terminal_result": (
                None
                if self.last_terminal_result is None
                else self.last_terminal_result.as_dict()
            ),
            "last_safe_error_code": self.last_safe_error_code.value,
            "stale_completion_count": self.stale_completion_count,
            "duplicate_terminal_count": self.duplicate_terminal_count,
            "overflow_count": self.overflow_count,
        }


def build_session_terminal_snapshot(
    result: RealtimeTurnResult | None,
) -> SessionTerminalSnapshot | None:
    """Project a terminal result without retaining any private-rich field."""

    if result is None:
        return None
    if not isinstance(result, RealtimeTurnResult):
        raise TypeError("result must be a RealtimeTurnResult or None")
    if result.session_id is None:
        raise ValueError("terminal result must contain a public session_id")
    return SessionTerminalSnapshot(
        session_id=result.session_id,
        turn_id=result.turn_id,
        generation_id=result.generation_id,
        outcome=result.outcome,
        public_error_code=result.public_error_code,
        retryable=result.retryable,
        recovery_action=result.recovery_action,
    )


def build_session_diagnostics_snapshot(
    *,
    session_id: SessionId | str,
    state: RealtimeState | str,
    phase: RealtimePhase | str | None,
    is_closed: bool,
    active_turn_id: TurnId | str | None = None,
    active_generation_id: GenerationId | str | None = None,
    queue_depth: int = 0,
    active_generation_count: int = 0,
    last_terminal_result: RealtimeTurnResult | SessionTerminalSnapshot | None = None,
    stale_completion_count: int = 0,
    duplicate_terminal_count: int = 0,
    overflow_count: int = 0,
) -> SessionDiagnosticsSnapshot:
    """Build a validated snapshot and derive its last safe error code."""

    terminal = last_terminal_result
    if isinstance(terminal, RealtimeTurnResult) or terminal is None:
        terminal = build_session_terminal_snapshot(terminal)
    elif not isinstance(terminal, SessionTerminalSnapshot):
        raise TypeError(
            "last_terminal_result must be a RealtimeTurnResult, "
            "SessionTerminalSnapshot, or None"
        )
    error_code = (
        RealtimeErrorCode.NONE
        if terminal is None
        else terminal.public_error_code
    )
    return SessionDiagnosticsSnapshot(
        session_id=session_id,
        state=state,
        phase=phase,
        is_closed=is_closed,
        active_turn_id=active_turn_id,
        active_generation_id=active_generation_id,
        queue_depth=queue_depth,
        active_generation_count=active_generation_count,
        last_terminal_result=terminal,
        last_safe_error_code=error_code,
        stale_completion_count=stale_completion_count,
        duplicate_terminal_count=duplicate_terminal_count,
        overflow_count=overflow_count,
    )


__all__ = [
    "SessionTerminalSnapshot",
    "SessionDiagnosticsSnapshot",
    "build_session_terminal_snapshot",
    "build_session_diagnostics_snapshot",
]
