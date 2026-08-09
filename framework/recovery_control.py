"""Provider-neutral recovery-action to reset-control-plan contract.

FW-RT6-10a Control A projects the existing root-public ``RecoveryAction`` into
one truthful, immutable control plan.  A plan classifies turn-only reset,
session reset, reconnect, close, and permanent failure without performing any
of those effects.

Runtime adoption remains Control B work.  In particular, this module does not
add ``RealtimeSession.reset()``, advance a generation, reset a provider,
reconnect a client, or close a session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .identity import GenerationId
from .lifecycle import RecoveryAction
from .public_safety import public_mapping


class RecoveryResetScope(str, Enum):
    """Explicit Framework-owned reset scope."""

    TURN_ONLY = "turn_only"
    SESSION = "session"


class RecoveryControlDisposition(str, Enum):
    """Truthful next control selected from one recovery action."""

    REUSE_SESSION = "reuse_session"
    RESET_TURN = "reset_turn"
    RESET_SESSION = "reset_session"
    RECONNECT_REQUIRED = "reconnect_required"
    CLOSE_REQUIRED = "close_required"
    PERMANENTLY_FAILED = "permanently_failed"


class RecoveryResetOutcome(str, Enum):
    """Typed result vocabulary for later reset execution adoption."""

    NOT_REQUIRED = "not_required"
    APPLIED = "applied"
    RECONNECT_REQUIRED = "reconnect_required"
    CLOSE_REQUIRED = "close_required"
    PERMANENTLY_FAILED = "permanently_failed"
    FAILED = "failed"


class RecoveryResetErrorCode(str, Enum):
    """Public-safe classification for a reset that could not be applied."""

    NONE = "none"
    SESSION_CLOSED = "session_closed"
    ACTIVE_OPERATION = "active_operation"
    GENERATION_MISMATCH = "generation_mismatch"
    RESET_UNSUPPORTED = "reset_unsupported"
    PROVIDER_RESET_FAILED = "provider_reset_failed"
    RESET_FAILED = "reset_failed"


_TURN_CONTEXT_LOSS = (
    "active_turn_provider_context",
    "in_flight_stage_context",
)
_SESSION_CONTEXT_LOSS = (
    "active_turn_provider_context",
    "provider_conversation_context",
    "provider_session_context",
    "in_flight_stage_context",
)


@dataclass(frozen=True, slots=True)
class RecoveryControlPlan:
    """Immutable, side-effect-free projection of one recovery action."""

    requested_action: RecoveryAction | str
    disposition: RecoveryControlDisposition | str
    reset_scope: RecoveryResetScope | str | None
    execute_reset: bool
    generation_advance_required: bool
    reconnect_required: bool
    close_required: bool
    permanently_failed: bool
    provider_context_loss: tuple[str, ...] = ()
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        action = (
            self.requested_action
            if isinstance(self.requested_action, RecoveryAction)
            else RecoveryAction(str(self.requested_action))
        )
        disposition = (
            self.disposition
            if isinstance(self.disposition, RecoveryControlDisposition)
            else RecoveryControlDisposition(str(self.disposition))
        )
        scope = self.reset_scope
        if scope is not None and not isinstance(scope, RecoveryResetScope):
            scope = RecoveryResetScope(str(scope))

        for field_name, value in (
            ("execute_reset", self.execute_reset),
            ("generation_advance_required", self.generation_advance_required),
            ("reconnect_required", self.reconnect_required),
            ("close_required", self.close_required),
            ("permanently_failed", self.permanently_failed),
        ):
            if type(value) is not bool:
                raise TypeError(f"{field_name} must be a boolean")

        expected = _plan_facts(action)
        actual = (
            disposition,
            scope,
            self.execute_reset,
            self.generation_advance_required,
            self.reconnect_required,
            self.close_required,
            self.permanently_failed,
            tuple(self.provider_context_loss),
        )
        if actual != expected:
            raise ValueError("recovery control facts do not match requested_action")

        object.__setattr__(self, "requested_action", action)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "reset_scope", scope)
        object.__setattr__(
            self,
            "provider_context_loss",
            tuple(self.provider_context_loss),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def decision_is_execution(self) -> bool:
        """Planning never performs the selected recovery control."""

        return False

    @property
    def side_effect_free(self) -> bool:
        """Control A models do not alter Framework or provider state."""

        return True


@dataclass(frozen=True, slots=True)
class RecoveryResetResult:
    """Typed result reserved for Control B reset execution."""

    plan: RecoveryControlPlan
    outcome: RecoveryResetOutcome | str
    error_code: RecoveryResetErrorCode | str = RecoveryResetErrorCode.NONE
    previous_generation_id: GenerationId | str | None = None
    current_generation_id: GenerationId | str | None = None
    generation_advanced: bool = False
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.plan, RecoveryControlPlan):
            raise TypeError("plan must be a RecoveryControlPlan")
        outcome = (
            self.outcome
            if isinstance(self.outcome, RecoveryResetOutcome)
            else RecoveryResetOutcome(str(self.outcome))
        )
        error_code = (
            self.error_code
            if isinstance(self.error_code, RecoveryResetErrorCode)
            else RecoveryResetErrorCode(str(self.error_code))
        )
        previous = _generation(self.previous_generation_id)
        current = _generation(self.current_generation_id)
        if type(self.generation_advanced) is not bool:
            raise TypeError("generation_advanced must be a boolean")
        if type(self.retryable) is not bool:
            raise TypeError("retryable must be a boolean")
        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")

        if outcome is RecoveryResetOutcome.APPLIED:
            if not self.plan.execute_reset:
                raise ValueError("only a reset plan can report applied")
            if error_code is not RecoveryResetErrorCode.NONE:
                raise ValueError("an applied reset cannot contain an error")
            if not self.generation_advanced:
                raise ValueError("an applied reset must advance generation")
            if previous is None or current is None or previous == current:
                raise ValueError("an applied reset requires distinct generations")
        elif outcome is RecoveryResetOutcome.FAILED:
            if not self.plan.execute_reset:
                raise ValueError("only a reset plan can report reset failure")
            if error_code is RecoveryResetErrorCode.NONE:
                raise ValueError("a failed reset requires a typed error code")
            if self.generation_advanced:
                raise ValueError("a failed reset cannot claim generation advance")
        else:
            expected_outcome = _non_reset_outcome(self.plan.disposition)
            if self.plan.execute_reset or outcome is not expected_outcome:
                raise ValueError("non-reset result does not match its plan")
            if error_code is not RecoveryResetErrorCode.NONE:
                raise ValueError("non-reset disposition cannot contain reset error")
            if self.generation_advanced or previous is not None or current is not None:
                raise ValueError("non-reset disposition cannot claim generation facts")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(self, "previous_generation_id", previous)
        object.__setattr__(self, "current_generation_id", current)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @classmethod
    def for_non_reset_plan(
        cls,
        plan: RecoveryControlPlan,
    ) -> "RecoveryResetResult":
        if not isinstance(plan, RecoveryControlPlan):
            raise TypeError("plan must be a RecoveryControlPlan")
        if plan.execute_reset:
            raise ValueError("an executing reset plan requires runtime execution")
        return cls(plan=plan, outcome=_non_reset_outcome(plan.disposition))

    @classmethod
    def applied(
        cls,
        plan: RecoveryControlPlan,
        *,
        previous_generation_id: GenerationId | str,
        current_generation_id: GenerationId | str,
    ) -> "RecoveryResetResult":
        return cls(
            plan=plan,
            outcome=RecoveryResetOutcome.APPLIED,
            previous_generation_id=previous_generation_id,
            current_generation_id=current_generation_id,
            generation_advanced=True,
        )

    @classmethod
    def failed(
        cls,
        plan: RecoveryControlPlan,
        *,
        error_code: RecoveryResetErrorCode | str,
        safe_message: str = "Realtime reset could not be applied safely.",
        retryable: bool = False,
    ) -> "RecoveryResetResult":
        return cls(
            plan=plan,
            outcome=RecoveryResetOutcome.FAILED,
            error_code=error_code,
            safe_message=safe_message,
            retryable=retryable,
        )


def _generation(value: GenerationId | str | None) -> GenerationId | None:
    if value is None:
        return None
    return value if isinstance(value, GenerationId) else GenerationId.parse(value)


def _plan_facts(
    action: RecoveryAction,
) -> tuple[
    RecoveryControlDisposition,
    RecoveryResetScope | None,
    bool,
    bool,
    bool,
    bool,
    bool,
    tuple[str, ...],
]:
    if action in {RecoveryAction.NONE, RecoveryAction.REUSE_SESSION}:
        return (
            RecoveryControlDisposition.REUSE_SESSION,
            None,
            False,
            False,
            False,
            False,
            False,
            (),
        )
    if action is RecoveryAction.RESET_TURN:
        return (
            RecoveryControlDisposition.RESET_TURN,
            RecoveryResetScope.TURN_ONLY,
            True,
            True,
            False,
            False,
            False,
            _TURN_CONTEXT_LOSS,
        )
    if action is RecoveryAction.RESET_SESSION:
        return (
            RecoveryControlDisposition.RESET_SESSION,
            RecoveryResetScope.SESSION,
            True,
            True,
            False,
            False,
            False,
            _SESSION_CONTEXT_LOSS,
        )
    if action is RecoveryAction.RECONNECT:
        return (
            RecoveryControlDisposition.RECONNECT_REQUIRED,
            None,
            False,
            False,
            True,
            False,
            False,
            (),
        )
    if action is RecoveryAction.CLOSE_SESSION:
        return (
            RecoveryControlDisposition.CLOSE_REQUIRED,
            None,
            False,
            False,
            False,
            True,
            False,
            (),
        )
    if action is RecoveryAction.PERMANENT_FAILURE:
        return (
            RecoveryControlDisposition.PERMANENTLY_FAILED,
            None,
            False,
            False,
            False,
            True,
            True,
            (),
        )
    raise AssertionError(f"unhandled recovery action: {action}")


def _non_reset_outcome(
    disposition: RecoveryControlDisposition,
) -> RecoveryResetOutcome:
    mapping = {
        RecoveryControlDisposition.REUSE_SESSION: RecoveryResetOutcome.NOT_REQUIRED,
        RecoveryControlDisposition.RECONNECT_REQUIRED: (
            RecoveryResetOutcome.RECONNECT_REQUIRED
        ),
        RecoveryControlDisposition.CLOSE_REQUIRED: RecoveryResetOutcome.CLOSE_REQUIRED,
        RecoveryControlDisposition.PERMANENTLY_FAILED: (
            RecoveryResetOutcome.PERMANENTLY_FAILED
        ),
    }
    try:
        return mapping[disposition]
    except KeyError:
        raise ValueError("reset plans require runtime execution") from None


def build_recovery_control_plan(
    action: RecoveryAction | str,
    *,
    public_metadata: Mapping[str, Any] | None = None,
) -> RecoveryControlPlan:
    """Build one truthful, non-executing plan from a recovery action."""

    resolved_action = (
        action if isinstance(action, RecoveryAction) else RecoveryAction(str(action))
    )
    (
        disposition,
        scope,
        execute_reset,
        generation_advance_required,
        reconnect_required,
        close_required,
        permanently_failed,
        provider_context_loss,
    ) = _plan_facts(resolved_action)
    return RecoveryControlPlan(
        requested_action=resolved_action,
        disposition=disposition,
        reset_scope=scope,
        execute_reset=execute_reset,
        generation_advance_required=generation_advance_required,
        reconnect_required=reconnect_required,
        close_required=close_required,
        permanently_failed=permanently_failed,
        provider_context_loss=provider_context_loss,
        public_metadata={
            **dict(public_metadata or {}),
            "boundary": "recovery_control",
            "requested_action": resolved_action.value,
            "disposition": disposition.value,
            "reset_scope": scope.value if scope is not None else None,
            "decision_is_execution": False,
        },
    )


__all__ = [
    "RecoveryResetScope",
    "RecoveryControlDisposition",
    "RecoveryResetOutcome",
    "RecoveryResetErrorCode",
    "RecoveryControlPlan",
    "RecoveryResetResult",
    "build_recovery_control_plan",
]
