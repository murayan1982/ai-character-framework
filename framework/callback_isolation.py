"""Provider-neutral callback, hook, and stage-failure isolation contract.

FW-RT6-10d Control A defines immutable failure-policy vocabulary plus small
provider-free reference dispatchers.  Runtime adoption is deliberately
separate: this package does not register a callback, invoke a plugin manager,
change a session lock, execute a realtime stage, import a provider SDK, or
alter an existing conversation terminal.

The dispatch results retain counts and policy identity only.  They never retain
callback or hook objects, return values, exceptions, credentials, provider
payloads, transcripts, audio, threads, clients, or filesystem paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import inspect
from typing import Callable, Iterable

from .realtime_stage import RealtimeStageKind


Callback = Callable[..., object]


class CallbackBoundary(str, Enum):
    """One extension boundary covered by the isolation contract."""

    PUBLIC_CALLBACK = "public_callback"
    PLUGIN_HOOK = "plugin_hook"
    MOTION_HOOK = "motion_hook"


class CallbackFailureAction(str, Enum):
    """Framework action after one callback or hook raises."""

    CONTINUE_DISPATCH = "continue_dispatch"
    SKIP_MOTION = "skip_motion"


@dataclass(frozen=True, slots=True)
class CallbackIsolationPolicy:
    """Canonical immutable policy for one callback or hook boundary."""

    boundary: CallbackBoundary | str
    failure_action: CallbackFailureAction | str
    continue_remaining_handlers: bool
    runtime_failure_on_exception: bool
    invoke_without_session_lock: bool
    reentrant_safe: bool

    def __post_init__(self) -> None:
        boundary = (
            self.boundary
            if isinstance(self.boundary, CallbackBoundary)
            else CallbackBoundary(str(self.boundary))
        )
        failure_action = (
            self.failure_action
            if isinstance(self.failure_action, CallbackFailureAction)
            else CallbackFailureAction(str(self.failure_action))
        )
        for field_name in (
            "continue_remaining_handlers",
            "runtime_failure_on_exception",
            "invoke_without_session_lock",
            "reentrant_safe",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a boolean")

        expected_action = (
            CallbackFailureAction.SKIP_MOTION
            if boundary is CallbackBoundary.MOTION_HOOK
            else CallbackFailureAction.CONTINUE_DISPATCH
        )
        expected_continue = boundary is not CallbackBoundary.MOTION_HOOK
        if failure_action is not expected_action:
            raise ValueError("failure_action must match the callback boundary")
        if self.continue_remaining_handlers is not expected_continue:
            raise ValueError(
                "continue_remaining_handlers must match the callback boundary"
            )
        if self.runtime_failure_on_exception:
            raise ValueError("callback or hook failure cannot fail the runtime")
        if not self.invoke_without_session_lock:
            raise ValueError("callbacks and hooks must run without a session lock")
        if not self.reentrant_safe:
            raise ValueError("callbacks and hooks must remain reentrant-safe")

        object.__setattr__(self, "boundary", boundary)
        object.__setattr__(self, "failure_action", failure_action)

    def as_dict(self) -> dict[str, str | bool]:
        """Return the exact JSON-friendly public-safe policy surface."""

        return {
            "boundary": self.boundary.value,
            "failure_action": self.failure_action.value,
            "continue_remaining_handlers": self.continue_remaining_handlers,
            "runtime_failure_on_exception": self.runtime_failure_on_exception,
            "invoke_without_session_lock": self.invoke_without_session_lock,
            "reentrant_safe": self.reentrant_safe,
        }


@dataclass(frozen=True, slots=True)
class CallbackDispatchResult:
    """Public-safe counts from one isolated callback dispatch pass."""

    boundary: CallbackBoundary | str
    attempted_count: int
    completed_count: int
    failed_count: int

    def __post_init__(self) -> None:
        boundary = (
            self.boundary
            if isinstance(self.boundary, CallbackBoundary)
            else CallbackBoundary(str(self.boundary))
        )
        if boundary is CallbackBoundary.MOTION_HOOK:
            raise ValueError(
                "motion hooks use the existing typed motion-lifecycle resolver"
            )
        for field_name in (
            "attempted_count",
            "completed_count",
            "failed_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer")
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.attempted_count != self.completed_count + self.failed_count:
            raise ValueError(
                "attempted_count must equal completed_count plus failed_count"
            )
        object.__setattr__(self, "boundary", boundary)

    @property
    def runtime_failed(self) -> bool:
        """Callback dispatch never represents a runtime failure."""

        return False

    @property
    def all_completed(self) -> bool:
        return self.failed_count == 0

    def as_dict(self) -> dict[str, str | int | bool]:
        """Return counts without callback, return-value, or exception data."""

        return {
            "boundary": self.boundary.value,
            "attempted_count": self.attempted_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "runtime_failed": False,
        }


class StageCriticality(str, Enum):
    """Whether one stage is required for the current primary operation."""

    CRITICAL = "critical"
    NON_CRITICAL = "non_critical"


class StageFailureAction(str, Enum):
    """Typed disposition of a safely normalized stage failure."""

    FAIL_CURRENT_OPERATION = "fail_current_operation"
    CONTINUE_DEGRADED = "continue_degraded"


@dataclass(frozen=True, slots=True)
class StageFailurePolicy:
    """Canonical failure semantics for one criticality class."""

    criticality: StageCriticality | str
    failure_action: StageFailureAction | str
    current_operation_fails: bool
    session_remains_open: bool
    runtime_remains_available: bool
    existing_terminal_replacement_allowed: bool

    def __post_init__(self) -> None:
        criticality = (
            self.criticality
            if isinstance(self.criticality, StageCriticality)
            else StageCriticality(str(self.criticality))
        )
        failure_action = (
            self.failure_action
            if isinstance(self.failure_action, StageFailureAction)
            else StageFailureAction(str(self.failure_action))
        )
        for field_name in (
            "current_operation_fails",
            "session_remains_open",
            "runtime_remains_available",
            "existing_terminal_replacement_allowed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a boolean")

        is_critical = criticality is StageCriticality.CRITICAL
        expected_action = (
            StageFailureAction.FAIL_CURRENT_OPERATION
            if is_critical
            else StageFailureAction.CONTINUE_DEGRADED
        )
        if failure_action is not expected_action:
            raise ValueError("failure_action must match stage criticality")
        if self.current_operation_fails is not is_critical:
            raise ValueError("current_operation_fails must match stage criticality")
        if not self.session_remains_open or not self.runtime_remains_available:
            raise ValueError("a stage failure cannot kill the session or runtime")
        if self.existing_terminal_replacement_allowed:
            raise ValueError("a stage failure cannot replace an existing terminal")

        object.__setattr__(self, "criticality", criticality)
        object.__setattr__(self, "failure_action", failure_action)

    def as_dict(self) -> dict[str, str | bool]:
        """Return the exact JSON-friendly public-safe stage policy surface."""

        return {
            "criticality": self.criticality.value,
            "failure_action": self.failure_action.value,
            "current_operation_fails": self.current_operation_fails,
            "session_remains_open": self.session_remains_open,
            "runtime_remains_available": self.runtime_remains_available,
            "existing_terminal_replacement_allowed": (
                self.existing_terminal_replacement_allowed
            ),
        }


def callback_isolation_policy(
    boundary: CallbackBoundary | str,
) -> CallbackIsolationPolicy:
    """Build the sole canonical policy for an extension boundary."""

    resolved = (
        boundary
        if isinstance(boundary, CallbackBoundary)
        else CallbackBoundary(str(boundary))
    )
    motion = resolved is CallbackBoundary.MOTION_HOOK
    return CallbackIsolationPolicy(
        boundary=resolved,
        failure_action=(
            CallbackFailureAction.SKIP_MOTION
            if motion
            else CallbackFailureAction.CONTINUE_DISPATCH
        ),
        continue_remaining_handlers=not motion,
        runtime_failure_on_exception=False,
        invoke_without_session_lock=True,
        reentrant_safe=True,
    )


def criticality_for_stage(
    stage_kind: RealtimeStageKind | str,
) -> StageCriticality:
    """Return the accepted default criticality of one realtime stage.

    Voice input is critical when it is selected as the input owner for the
    current operation.  Text generation is always primary.  Voice output and
    motion are optional side effects and therefore non-critical.
    """

    resolved = (
        stage_kind
        if isinstance(stage_kind, RealtimeStageKind)
        else RealtimeStageKind(str(stage_kind))
    )
    if resolved in {
        RealtimeStageKind.VOICE_INPUT,
        RealtimeStageKind.TEXT_GENERATION,
    }:
        return StageCriticality.CRITICAL
    return StageCriticality.NON_CRITICAL


def stage_failure_policy(
    criticality: StageCriticality | str,
) -> StageFailurePolicy:
    """Build the sole canonical policy for one stage criticality class."""

    resolved = (
        criticality
        if isinstance(criticality, StageCriticality)
        else StageCriticality(str(criticality))
    )
    critical = resolved is StageCriticality.CRITICAL
    return StageFailurePolicy(
        criticality=resolved,
        failure_action=(
            StageFailureAction.FAIL_CURRENT_OPERATION
            if critical
            else StageFailureAction.CONTINUE_DEGRADED
        ),
        current_operation_fails=critical,
        session_remains_open=True,
        runtime_remains_available=True,
        existing_terminal_replacement_allowed=False,
    )


def _dispatch_result(
    boundary: CallbackBoundary,
    *,
    attempted_count: int,
    completed_count: int,
) -> CallbackDispatchResult:
    return CallbackDispatchResult(
        boundary=boundary,
        attempted_count=attempted_count,
        completed_count=completed_count,
        failed_count=attempted_count - completed_count,
    )


def _dispatch_boundary(boundary: CallbackBoundary | str) -> CallbackBoundary:
    resolved = (
        boundary
        if isinstance(boundary, CallbackBoundary)
        else CallbackBoundary(str(boundary))
    )
    if resolved is CallbackBoundary.MOTION_HOOK:
        raise ValueError(
            "motion hooks must use invoke_motion_lifecycle_hook"
        )
    return resolved


def dispatch_isolated_callbacks(
    callbacks: Iterable[Callback],
    *args: object,
    boundary: CallbackBoundary | str = CallbackBoundary.PUBLIC_CALLBACK,
    **kwargs: object,
) -> CallbackDispatchResult:
    """Run a stable handler snapshot and isolate each ordinary exception.

    This function intentionally owns no lock or mutable registry.  Runtime
    adopters must snapshot their registry while locked, release every session
    and registry lock, and only then call this dispatcher.
    """

    resolved = _dispatch_boundary(boundary)
    handlers = tuple(callbacks)
    completed = 0
    for callback in handlers:
        try:
            if not callable(callback):
                raise TypeError("callback must be callable")
            returned = callback(*args, **kwargs)
            if inspect.isawaitable(returned):
                close = getattr(returned, "close", None)
                if callable(close):
                    close()
                raise TypeError("awaitable callback requires async dispatch")
        except Exception:
            continue
        completed += 1
    return _dispatch_result(
        resolved,
        attempted_count=len(handlers),
        completed_count=completed,
    )


async def dispatch_isolated_callbacks_async(
    callbacks: Iterable[Callback],
    *args: object,
    boundary: CallbackBoundary | str = CallbackBoundary.PLUGIN_HOOK,
    **kwargs: object,
) -> CallbackDispatchResult:
    """Run sync or async hook handlers in order with per-handler isolation."""

    resolved = _dispatch_boundary(boundary)
    handlers = tuple(callbacks)
    completed = 0
    for callback in handlers:
        try:
            if not callable(callback):
                raise TypeError("callback must be callable")
            returned = callback(*args, **kwargs)
            if inspect.isawaitable(returned):
                await returned
        except Exception:
            continue
        completed += 1
    return _dispatch_result(
        resolved,
        attempted_count=len(handlers),
        completed_count=completed,
    )


__all__ = [
    "CallbackBoundary",
    "CallbackFailureAction",
    "CallbackIsolationPolicy",
    "CallbackDispatchResult",
    "StageCriticality",
    "StageFailureAction",
    "StageFailurePolicy",
    "callback_isolation_policy",
    "criticality_for_stage",
    "stage_failure_policy",
    "dispatch_isolated_callbacks",
    "dispatch_isolated_callbacks_async",
]
