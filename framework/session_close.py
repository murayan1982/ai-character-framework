"""Provider-neutral session close/dispose planning and result contract.

FW-RT6-10b Control A defines one immutable vocabulary shared by the later
public-session close adoption.  It describes active-turn terminalization,
callback-hub sealing, stage/provider cleanup, and execution-bridge shutdown
without performing any of those effects.

Runtime adoption remains Control B work.  This module does not close a public
session, invoke a stage or provider client, emit an event, advance a generation,
stop a thread, or create a second lifecycle owner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from types import MappingProxyType
from threading import Event, Lock, Thread
import time
from typing import Any, Callable, Iterable, Mapping

from .public_safety import public_mapping


class SessionCleanupTarget(str, Enum):
    """Provider-neutral target recorded by one close operation."""

    ACTIVE_TURN = "active_turn"
    STAGE = "stage"
    PROVIDER_CLIENT = "provider_client"
    CALLBACK_HUB = "callback_hub"
    EXECUTION_BRIDGE = "execution_bridge"


class SessionCleanupOutcome(str, Enum):
    """Truthful result of one cleanup target."""

    NOT_REQUIRED = "not_required"
    COMPLETED = "completed"
    ALREADY_CLOSED = "already_closed"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class SessionCloseOutcome(str, Enum):
    """Aggregate result of one idempotent public-session close request."""

    CLOSED = "closed"
    ALREADY_CLOSED = "already_closed"
    CLOSED_WITH_CLEANUP_FAILURES = "closed_with_cleanup_failures"


_TARGET_ORDER = (
    SessionCleanupTarget.ACTIVE_TURN,
    SessionCleanupTarget.STAGE,
    SessionCleanupTarget.PROVIDER_CLIENT,
    SessionCleanupTarget.CALLBACK_HUB,
    SessionCleanupTarget.EXECUTION_BRIDGE,
)
_SUCCESSFUL_CLEANUP_OUTCOMES = {
    SessionCleanupOutcome.COMPLETED,
    SessionCleanupOutcome.ALREADY_CLOSED,
}
_UNSUCCESSFUL_CLEANUP_OUTCOMES = {
    SessionCleanupOutcome.TIMED_OUT,
    SessionCleanupOutcome.FAILED,
}


def _positive_timeout(value: float, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"{field_name} must be a finite positive number")
    return resolved


@dataclass(frozen=True, slots=True)
class SessionClosePlan:
    """Side-effect-free facts required by one later session-owned close."""

    active_turn_terminal_required: bool = False
    stage_cleanup_required: bool = False
    provider_client_cleanup_required: bool = False
    callback_hub_close_required: bool = False
    execution_bridge_shutdown_required: bool = False
    stage_cleanup_timeout_seconds: float = 2.0
    provider_cleanup_timeout_seconds: float = 2.0
    bridge_shutdown_timeout_seconds: float = 2.0
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "active_turn_terminal_required",
            "stage_cleanup_required",
            "provider_client_cleanup_required",
            "callback_hub_close_required",
            "execution_bridge_shutdown_required",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a boolean")

        object.__setattr__(
            self,
            "stage_cleanup_timeout_seconds",
            _positive_timeout(
                self.stage_cleanup_timeout_seconds,
                field_name="stage_cleanup_timeout_seconds",
            ),
        )
        object.__setattr__(
            self,
            "provider_cleanup_timeout_seconds",
            _positive_timeout(
                self.provider_cleanup_timeout_seconds,
                field_name="provider_cleanup_timeout_seconds",
            ),
        )
        object.__setattr__(
            self,
            "bridge_shutdown_timeout_seconds",
            _positive_timeout(
                self.bridge_shutdown_timeout_seconds,
                field_name="bridge_shutdown_timeout_seconds",
            ),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def required_targets(self) -> tuple[SessionCleanupTarget, ...]:
        """Return required targets in the canonical close-observation order."""

        required = {
            SessionCleanupTarget.ACTIVE_TURN:
                self.active_turn_terminal_required,
            SessionCleanupTarget.STAGE: self.stage_cleanup_required,
            SessionCleanupTarget.PROVIDER_CLIENT:
                self.provider_client_cleanup_required,
            SessionCleanupTarget.CALLBACK_HUB:
                self.callback_hub_close_required,
            SessionCleanupTarget.EXECUTION_BRIDGE:
                self.execution_bridge_shutdown_required,
        }
        return tuple(target for target in _TARGET_ORDER if required[target])

    @property
    def decision_is_execution(self) -> bool:
        """Planning never performs session or resource cleanup."""

        return False

    @property
    def side_effect_free(self) -> bool:
        """Control A models cannot alter Framework or provider state."""

        return True


@dataclass(frozen=True, slots=True)
class SessionCleanupResult:
    """Public-safe typed observation for one cleanup target."""

    target: SessionCleanupTarget | str
    outcome: SessionCleanupOutcome | str
    safe_message: str = ""
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        target = (
            self.target
            if isinstance(self.target, SessionCleanupTarget)
            else SessionCleanupTarget(str(self.target))
        )
        outcome = (
            self.outcome
            if isinstance(self.outcome, SessionCleanupOutcome)
            else SessionCleanupOutcome(str(self.outcome))
        )
        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")
        if outcome in _UNSUCCESSFUL_CLEANUP_OUTCOMES and not self.safe_message:
            raise ValueError("failed or timed-out cleanup requires a safe message")

        object.__setattr__(self, "target", target)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def attempted(self) -> bool:
        return self.outcome is not SessionCleanupOutcome.NOT_REQUIRED

    @property
    def successful(self) -> bool:
        return self.outcome in _SUCCESSFUL_CLEANUP_OUTCOMES

    @property
    def timed_out(self) -> bool:
        return self.outcome is SessionCleanupOutcome.TIMED_OUT

    @property
    def failed(self) -> bool:
        return self.outcome is SessionCleanupOutcome.FAILED

    @classmethod
    def not_required(
        cls,
        target: SessionCleanupTarget | str,
    ) -> "SessionCleanupResult":
        return cls(target=target, outcome=SessionCleanupOutcome.NOT_REQUIRED)

    @classmethod
    def completed(
        cls,
        target: SessionCleanupTarget | str,
    ) -> "SessionCleanupResult":
        return cls(target=target, outcome=SessionCleanupOutcome.COMPLETED)

    @classmethod
    def already_closed(
        cls,
        target: SessionCleanupTarget | str,
    ) -> "SessionCleanupResult":
        return cls(target=target, outcome=SessionCleanupOutcome.ALREADY_CLOSED)

    @classmethod
    def timed_out_result(
        cls,
        target: SessionCleanupTarget | str,
        *,
        safe_message: str = "Session resource cleanup timed out.",
    ) -> "SessionCleanupResult":
        return cls(
            target=target,
            outcome=SessionCleanupOutcome.TIMED_OUT,
            safe_message=safe_message,
        )

    @classmethod
    def failed_result(
        cls,
        target: SessionCleanupTarget | str,
        *,
        safe_message: str = "Session resource cleanup failed.",
    ) -> "SessionCleanupResult":
        return cls(
            target=target,
            outcome=SessionCleanupOutcome.FAILED,
            safe_message=safe_message,
        )


def _canonical_results(
    values: Iterable[SessionCleanupResult],
) -> tuple[SessionCleanupResult, ...]:
    results = tuple(values)
    if any(not isinstance(value, SessionCleanupResult) for value in results):
        raise TypeError("cleanup_results must contain SessionCleanupResult values")
    by_target = {result.target: result for result in results}
    if len(by_target) != len(results):
        raise ValueError("cleanup_results must contain each target at most once")
    if set(by_target) != set(_TARGET_ORDER):
        raise ValueError("cleanup_results must contain every canonical target")
    return tuple(by_target[target] for target in _TARGET_ORDER)


@dataclass(frozen=True, slots=True)
class SessionCloseResult:
    """Immutable aggregate close result reserved for Control B adoption."""

    plan: SessionClosePlan
    outcome: SessionCloseOutcome | str
    cleanup_results: tuple[SessionCleanupResult, ...]
    active_turn_terminalized: bool
    session_closed: bool = True
    safe_message: str = ""
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.plan, SessionClosePlan):
            raise TypeError("plan must be a SessionClosePlan")
        outcome = (
            self.outcome
            if isinstance(self.outcome, SessionCloseOutcome)
            else SessionCloseOutcome(str(self.outcome))
        )
        if type(self.active_turn_terminalized) is not bool:
            raise TypeError("active_turn_terminalized must be a boolean")
        if type(self.session_closed) is not bool:
            raise TypeError("session_closed must be a boolean")
        if not self.session_closed:
            raise ValueError("a close result cannot leave the session open")
        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")

        results = _canonical_results(self.cleanup_results)
        by_target = {result.target: result for result in results}
        required = set(self.plan.required_targets)
        for target in _TARGET_ORDER:
            result = by_target[target]
            if target in required:
                if result.outcome is SessionCleanupOutcome.NOT_REQUIRED:
                    raise ValueError("a required cleanup target cannot be not_required")
            elif result.outcome is not SessionCleanupOutcome.NOT_REQUIRED:
                raise ValueError("a non-required cleanup target cannot claim execution")

        active_result = by_target[SessionCleanupTarget.ACTIVE_TURN]
        if (
            self.plan.active_turn_terminal_required
            and active_result.outcome not in _SUCCESSFUL_CLEANUP_OUTCOMES
        ):
            raise ValueError("an active turn must reach its closed terminal result")
        expected_terminalized = (
            self.plan.active_turn_terminal_required
            and active_result.outcome in _SUCCESSFUL_CLEANUP_OUTCOMES
        )
        if self.active_turn_terminalized != expected_terminalized:
            raise ValueError("active-turn terminal fact does not match cleanup result")

        unsuccessful = tuple(
            result
            for result in results
            if result.outcome in _UNSUCCESSFUL_CLEANUP_OUTCOMES
        )
        if outcome is SessionCloseOutcome.ALREADY_CLOSED:
            if required or any(result.attempted for result in results):
                raise ValueError("already-closed result cannot repeat cleanup")
            if self.active_turn_terminalized:
                raise ValueError("already-closed result cannot terminalize a turn")
        elif outcome is SessionCloseOutcome.CLOSED:
            if unsuccessful:
                raise ValueError("successful close cannot contain cleanup failures")
        elif outcome is SessionCloseOutcome.CLOSED_WITH_CLEANUP_FAILURES:
            if not unsuccessful:
                raise ValueError("cleanup-failure close requires a failed or timed-out target")
            if not self.safe_message:
                raise ValueError("cleanup-failure close requires a safe message")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "cleanup_results", results)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def diagnostics(self) -> Mapping[str, int]:
        """Return count-only immutable cleanup diagnostics."""

        return MappingProxyType(
            {
                "cleanup_required_count": len(self.plan.required_targets),
                "cleanup_attempted_count": sum(
                    result.attempted for result in self.cleanup_results
                ),
                "cleanup_completed_count": sum(
                    result.successful for result in self.cleanup_results
                ),
                "cleanup_timeout_count": sum(
                    result.timed_out for result in self.cleanup_results
                ),
                "cleanup_failure_count": sum(
                    result.failed for result in self.cleanup_results
                ),
                "active_turn_terminalized_count": int(
                    self.active_turn_terminalized
                ),
            }
        )

    @classmethod
    def from_cleanup(
        cls,
        plan: SessionClosePlan,
        *,
        cleanup_results: Iterable[SessionCleanupResult],
        active_turn_terminalized: bool,
        safe_message: str = "Session closed with one or more cleanup failures.",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "SessionCloseResult":
        results = _canonical_results(cleanup_results)
        unsuccessful = any(
            result.outcome in _UNSUCCESSFUL_CLEANUP_OUTCOMES
            for result in results
        )
        return cls(
            plan=plan,
            outcome=(
                SessionCloseOutcome.CLOSED_WITH_CLEANUP_FAILURES
                if unsuccessful
                else SessionCloseOutcome.CLOSED
            ),
            cleanup_results=results,
            active_turn_terminalized=active_turn_terminalized,
            safe_message=safe_message if unsuccessful else "",
            public_metadata=public_metadata or {},
        )

    @classmethod
    def already_closed(
        cls,
        *,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "SessionCloseResult":
        plan = build_session_close_plan()
        return cls(
            plan=plan,
            outcome=SessionCloseOutcome.ALREADY_CLOSED,
            cleanup_results=tuple(
                SessionCleanupResult.not_required(target)
                for target in _TARGET_ORDER
            ),
            active_turn_terminalized=False,
            public_metadata=public_metadata or {},
        )


def build_session_close_plan(
    *,
    active_turn_terminal_required: bool = False,
    stage_cleanup_required: bool = False,
    provider_client_cleanup_required: bool = False,
    callback_hub_close_required: bool = False,
    execution_bridge_shutdown_required: bool = False,
    stage_cleanup_timeout_seconds: float = 2.0,
    provider_cleanup_timeout_seconds: float = 2.0,
    bridge_shutdown_timeout_seconds: float = 2.0,
    public_metadata: Mapping[str, Any] | None = None,
) -> SessionClosePlan:
    """Build one truthful close plan without performing lifecycle effects."""

    return SessionClosePlan(
        active_turn_terminal_required=active_turn_terminal_required,
        stage_cleanup_required=stage_cleanup_required,
        provider_client_cleanup_required=provider_client_cleanup_required,
        callback_hub_close_required=callback_hub_close_required,
        execution_bridge_shutdown_required=execution_bridge_shutdown_required,
        stage_cleanup_timeout_seconds=stage_cleanup_timeout_seconds,
        provider_cleanup_timeout_seconds=provider_cleanup_timeout_seconds,
        bridge_shutdown_timeout_seconds=bridge_shutdown_timeout_seconds,
        public_metadata=public_metadata or {},
    )


def _results_for_plan(
    plan: SessionClosePlan,
    *,
    observed: Mapping[SessionCleanupTarget, SessionCleanupResult] | None = None,
) -> tuple[SessionCleanupResult, ...]:
    """Build the canonical five-target result tuple for one runtime owner."""

    if not isinstance(plan, SessionClosePlan):
        raise TypeError("plan must be a SessionClosePlan")
    observations = dict(observed or {})
    required = set(plan.required_targets)
    return tuple(
        observations.get(
            target,
            (
                SessionCleanupResult.completed(target)
                if target in required
                else SessionCleanupResult.not_required(target)
            ),
        )
        for target in _TARGET_ORDER
    )


def _runtime_close_result(
    plan: SessionClosePlan,
    *,
    observed: Mapping[SessionCleanupTarget, SessionCleanupResult] | None = None,
    active_turn_terminalized: bool = False,
    public_metadata: Mapping[str, Any] | None = None,
) -> SessionCloseResult:
    """Compose the immutable result owned by an existing public session."""

    return SessionCloseResult.from_cleanup(
        plan,
        cleanup_results=_results_for_plan(plan, observed=observed),
        active_turn_terminalized=active_turn_terminalized,
        public_metadata=public_metadata,
    )


def _run_bounded_cleanup_operations(
    operations: Iterable[Callable[[], Any]],
    *,
    timeout_seconds: float,
    target: SessionCleanupTarget,
    timeout_message: str,
    failure_message: str,
) -> tuple[SessionCleanupResult, int, int]:
    """Run independent cleanup calls concurrently under one finite deadline.

    Cleanup isolation workers are daemon threads because Python cannot forcibly
    terminate an arbitrary external synchronous close method.  After the common
    deadline, a late worker can update only this helper's private observation
    slots; it cannot alter the returned session result or callback collections.
    """

    timeout = _positive_timeout(timeout_seconds, field_name="timeout_seconds")
    callbacks = tuple(operations)
    if any(not callable(operation) for operation in callbacks):
        raise TypeError("operations must contain callables")
    if not callbacks:
        return SessionCleanupResult.completed(target), 0, 0

    outcomes: list[str | None] = [None] * len(callbacks)
    completions = tuple(Event() for _ in callbacks)
    observation_lock = Lock()

    def worker(index: int, operation: Callable[[], Any]) -> None:
        outcome = "completed"
        try:
            operation()
        except TimeoutError:
            outcome = "timed_out"
        except BaseException:  # cleanup boundary converts to bounded safe state
            outcome = "failed"
        with observation_lock:
            outcomes[index] = outcome
        completions[index].set()

    for index, operation in enumerate(callbacks):
        Thread(
            target=worker,
            args=(index, operation),
            name=f"framework-session-close-{target.value}-{index}",
            daemon=True,
        ).start()

    deadline = time.monotonic() + timeout
    for completion in completions:
        remaining = max(0.0, deadline - time.monotonic())
        completion.wait(timeout=remaining)

    with observation_lock:
        snapshot = tuple(outcomes)
    completed_count = sum(outcome == "completed" for outcome in snapshot)
    failed_count = sum(outcome == "failed" for outcome in snapshot)
    timed_out_count = sum(
        outcome is None or outcome == "timed_out" for outcome in snapshot
    )
    error_count = failed_count + timed_out_count

    if timed_out_count:
        result = SessionCleanupResult.timed_out_result(
            target,
            safe_message=timeout_message,
        )
    elif failed_count:
        result = SessionCleanupResult.failed_result(
            target,
            safe_message=failure_message,
        )
    else:
        result = SessionCleanupResult.completed(target)
    return result, completed_count, error_count


def _run_bounded_cleanup(
    operation: Callable[[], Any],
    *,
    timeout_seconds: float,
    target: SessionCleanupTarget,
    timeout_message: str,
    failure_message: str,
) -> SessionCleanupResult:
    """Run one cleanup call under the shared runtime timeout discipline."""

    result, _completed_count, _error_count = _run_bounded_cleanup_operations(
        (operation,),
        timeout_seconds=timeout_seconds,
        target=target,
        timeout_message=timeout_message,
        failure_message=failure_message,
    )
    return result


__all__ = [
    "SessionCleanupTarget",
    "SessionCleanupOutcome",
    "SessionCloseOutcome",
    "SessionClosePlan",
    "SessionCleanupResult",
    "SessionCloseResult",
    "build_session_close_plan",
]
