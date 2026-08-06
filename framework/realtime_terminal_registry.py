"""Internal provider-neutral realtime terminal registry primitives.

The registry owns atomic first-terminal commitment for one future
``RealtimeSession``. It is intentionally not exported from the Framework root
in FW-RT6-2c Control A.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Generic, TypeVar

from .identity import TurnId, normalize_turn_id
from .lifecycle import (
    LifecycleTransitionError,
    LifecycleTransitionErrorCode,
    RecoveryAction,
    TurnOutcome,
    validate_terminal_transition,
)


ResultT = TypeVar("ResultT")
TurnKey = TurnId | str


class TerminalCommitStatus(str, Enum):
    """Classification of one terminal commit attempt."""

    FIRST_TERMINAL = "first_terminal"
    DUPLICATE_TERMINAL = "duplicate_terminal"
    TERMINAL_REGRESSION = "terminal_regression"


def _turn_key(value: TurnKey) -> TurnKey:
    resolved = normalize_turn_id(value)
    if resolved is None:
        raise ValueError("turn_id must not be None")
    return resolved


def _outcome(value: TurnOutcome | str) -> TurnOutcome:
    return value if isinstance(value, TurnOutcome) else TurnOutcome(str(value))


def _recovery_action(value: RecoveryAction | str) -> RecoveryAction:
    return (
        value
        if isinstance(value, RecoveryAction)
        else RecoveryAction(str(value))
    )


def _reason(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("reason must be a string")
    return value


@dataclass(frozen=True, slots=True)
class TerminalRecord(Generic[ResultT]):
    """Immutable first-terminal record retained for one turn."""

    turn_id: TurnKey
    outcome: TurnOutcome
    recovery_action: RecoveryAction
    reason: str
    result: ResultT | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "turn_id", _turn_key(self.turn_id))
        object.__setattr__(self, "outcome", _outcome(self.outcome))
        object.__setattr__(
            self,
            "recovery_action",
            _recovery_action(self.recovery_action),
        )
        object.__setattr__(self, "reason", _reason(self.reason))


@dataclass(frozen=True, slots=True)
class TerminalCommitDecision(Generic[ResultT]):
    """Immutable accepted/suppressed result of one commit attempt."""

    status: TerminalCommitStatus
    accepted: bool
    record: TerminalRecord[ResultT]
    attempted_outcome: TurnOutcome
    error_code: LifecycleTransitionErrorCode | None = None

    def __post_init__(self) -> None:
        status = (
            self.status
            if isinstance(self.status, TerminalCommitStatus)
            else TerminalCommitStatus(str(self.status))
        )
        attempted = _outcome(self.attempted_outcome)
        error_code = self.error_code
        if error_code is not None and not isinstance(
            error_code,
            LifecycleTransitionErrorCode,
        ):
            error_code = LifecycleTransitionErrorCode(str(error_code))

        if type(self.accepted) is not bool:
            raise TypeError("accepted must be a boolean")
        if self.accepted:
            if status is not TerminalCommitStatus.FIRST_TERMINAL:
                raise ValueError("accepted decision must be FIRST_TERMINAL")
            if error_code is not None:
                raise ValueError("accepted decision must not have an error code")
        else:
            expected = {
                TerminalCommitStatus.DUPLICATE_TERMINAL:
                    LifecycleTransitionErrorCode.DUPLICATE_TERMINAL,
                TerminalCommitStatus.TERMINAL_REGRESSION:
                    LifecycleTransitionErrorCode.TERMINAL_REGRESSION,
            }.get(status)
            if expected is None or error_code is not expected:
                raise ValueError(
                    "suppressed decision must retain its lifecycle error code"
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "attempted_outcome", attempted)
        object.__setattr__(self, "error_code", error_code)


@dataclass(frozen=True, slots=True)
class TerminalRegistryDiagnostics:
    """Immutable count-only terminal registry diagnostics."""

    terminal_commit_count: int
    duplicate_terminal_count: int
    terminal_regression_count: int
    late_non_terminal_count: int
    registry_size: int


class RealtimeTerminalRegistry(Generic[ResultT]):
    """Atomically retain the first terminal record for each turn."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[TurnKey, TerminalRecord[ResultT]] = {}
        self._terminal_commit_count = 0
        self._duplicate_terminal_count = 0
        self._terminal_regression_count = 0
        self._late_non_terminal_count = 0

    @property
    def records(self) -> tuple[TerminalRecord[ResultT], ...]:
        """Return immutable records in first-terminal commit order."""

        with self._lock:
            return tuple(self._records.values())

    @property
    def diagnostics(self) -> TerminalRegistryDiagnostics:
        """Return an immutable count-only diagnostic snapshot."""

        with self._lock:
            return TerminalRegistryDiagnostics(
                terminal_commit_count=self._terminal_commit_count,
                duplicate_terminal_count=self._duplicate_terminal_count,
                terminal_regression_count=self._terminal_regression_count,
                late_non_terminal_count=self._late_non_terminal_count,
                registry_size=len(self._records),
            )

    def get(self, turn_id: TurnKey) -> TerminalRecord[ResultT] | None:
        """Return the first terminal record for a turn, if present."""

        resolved_turn_id = _turn_key(turn_id)
        with self._lock:
            return self._records.get(resolved_turn_id)

    def is_terminal(self, turn_id: TurnKey) -> bool:
        """Return whether one turn already owns a terminal record."""

        return self.get(turn_id) is not None

    def admit_non_terminal(self, turn_id: TurnKey) -> bool:
        """Admit a non-terminal attempt unless the turn is already terminal."""

        resolved_turn_id = _turn_key(turn_id)
        with self._lock:
            if resolved_turn_id in self._records:
                self._late_non_terminal_count += 1
                return False
            return True

    def commit(
        self,
        turn_id: TurnKey,
        outcome: TurnOutcome | str,
        *,
        recovery_action: RecoveryAction | str = RecoveryAction.NONE,
        reason: str = "",
        result: ResultT | None = None,
    ) -> TerminalCommitDecision[ResultT]:
        """Atomically commit or suppress one terminal attempt."""

        resolved_turn_id = _turn_key(turn_id)
        resolved_outcome = _outcome(outcome)
        resolved_recovery = _recovery_action(recovery_action)
        resolved_reason = _reason(reason)

        with self._lock:
            existing = self._records.get(resolved_turn_id)
            try:
                validated = validate_terminal_transition(
                    existing.outcome if existing is not None else None,
                    resolved_outcome,
                )
            except LifecycleTransitionError as exc:
                if existing is None:
                    raise AssertionError(
                        "terminal validator rejected an empty registry slot"
                    ) from exc
                if exc.code is LifecycleTransitionErrorCode.DUPLICATE_TERMINAL:
                    self._duplicate_terminal_count += 1
                    return TerminalCommitDecision(
                        status=TerminalCommitStatus.DUPLICATE_TERMINAL,
                        accepted=False,
                        record=existing,
                        attempted_outcome=resolved_outcome,
                        error_code=exc.code,
                    )
                if exc.code is LifecycleTransitionErrorCode.TERMINAL_REGRESSION:
                    self._terminal_regression_count += 1
                    return TerminalCommitDecision(
                        status=TerminalCommitStatus.TERMINAL_REGRESSION,
                        accepted=False,
                        record=existing,
                        attempted_outcome=resolved_outcome,
                        error_code=exc.code,
                    )
                raise

            record = TerminalRecord(
                turn_id=resolved_turn_id,
                outcome=validated,
                recovery_action=resolved_recovery,
                reason=resolved_reason,
                result=result,
            )
            self._records[resolved_turn_id] = record
            self._terminal_commit_count += 1
            return TerminalCommitDecision(
                status=TerminalCommitStatus.FIRST_TERMINAL,
                accepted=True,
                record=record,
                attempted_outcome=validated,
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


__all__ = [
    "TerminalCommitStatus",
    "TerminalRecord",
    "TerminalCommitDecision",
    "TerminalRegistryDiagnostics",
    "RealtimeTerminalRegistry",
]
