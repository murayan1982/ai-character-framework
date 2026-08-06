"""Deterministic provider-free realtime race controller.

FW-RT6-3b Control A provides one explicit test-support package for reproducing
ordering, pause/resume, delay, late-completion, duplicate-terminal,
cancellation-timeout, and queue-overflow scenarios without provider SDKs,
network access, microphone input, playback, VTube Studio, private configuration,
wall-clock sleeps, or background threads.

The package is intentionally not imported by :mod:`framework` root. Test and
validation code may import it explicitly as ``framework.realtime_fake_runtime``.
It controls deterministic fake actions only; it does not execute
``RealtimeSession`` stages or claim real runtime orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import heapq
from typing import Callable, Mapping, Sequence

from .public_safety import public_mapping, sanitize_public_value
from .realtime_stage import RealtimeStageKind


FakeRuntimeCallback = Callable[["FakeRuntimeAction"], None]


class FakeRuntimeActionKind(str, Enum):
    """Provider-neutral action kinds understood by the fake controller."""

    STAGE_ACTION = "stage_action"
    LATE_COMPLETION = "late_completion"
    TERMINAL = "terminal"
    CANCELLATION_TIMEOUT = "cancellation_timeout"
    CUSTOM = "custom"


class FakeRuntimeTraceKind(str, Enum):
    """Stable trace vocabulary emitted by deterministic fake execution."""

    ACTION_SCHEDULED = "action_scheduled"
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    CLOCK_ADVANCED = "clock_advanced"
    STAGE_PAUSED = "stage_paused"
    STAGE_RESUMED = "stage_resumed"
    LATE_COMPLETION_INJECTED = "late_completion_injected"
    DUPLICATE_TERMINAL_INJECTED = "duplicate_terminal_injected"
    CANCELLATION_TIMEOUT_INJECTED = "cancellation_timeout_injected"
    QUEUE_OVERFLOW_INJECTED = "queue_overflow_injected"
    CONTROLLER_CLOSED = "controller_closed"


class FakeRuntimeQueueOverflow(RuntimeError):
    """Raised when deterministic fake scheduling exceeds its fixed capacity."""


class FakeRuntimeClosedError(RuntimeError):
    """Raised when work is scheduled after the fake controller is closed."""


def _non_negative_tick(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive_count(value: int, *, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _stage_kind(value: RealtimeStageKind | str | None) -> RealtimeStageKind | None:
    if value is None:
        return None
    if isinstance(value, RealtimeStageKind):
        return value
    return RealtimeStageKind(str(value))


def _correlation_key(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("correlation_key must be a non-empty string or None")
    normalized = value.strip()
    if any(character in normalized for character in ("\n", "\r", "|")):
        raise ValueError("correlation_key contains a reserved trace character")
    sanitized = sanitize_public_value(normalized)
    if not isinstance(sanitized, str):
        raise AssertionError("correlation_key sanitization must return a string")
    return sanitized


@dataclass(slots=True, init=False)
class DeterministicFakeClock:
    """Integer-tick clock that never reads wall time or sleeps."""

    _tick: int

    def __init__(self, initial_tick: int = 0) -> None:
        self._tick = _non_negative_tick(initial_tick, name="initial_tick")

    @property
    def now_tick(self) -> int:
        return self._tick

    def advance_by(self, ticks: int) -> int:
        ticks = _non_negative_tick(ticks, name="ticks")
        self._tick += ticks
        return self._tick

    def advance_to(self, tick: int) -> int:
        tick = _non_negative_tick(tick, name="tick")
        if tick < self._tick:
            raise ValueError("fake clock cannot move backwards")
        self._tick = tick
        return self._tick


@dataclass(frozen=True, slots=True)
class FakeRuntimeAction:
    """Public-safe description delivered to one deterministic callback."""

    action_id: str
    sequence: int
    kind: FakeRuntimeActionKind | str
    due_tick: int
    stage_kind: RealtimeStageKind | str | None = None
    correlation_key: str | None = None
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action_id, str) or not self.action_id.strip():
            raise ValueError("action_id must be a non-empty string")
        sequence = _non_negative_tick(self.sequence, name="sequence")
        due_tick = _non_negative_tick(self.due_tick, name="due_tick")
        kind = (
            self.kind
            if isinstance(self.kind, FakeRuntimeActionKind)
            else FakeRuntimeActionKind(str(self.kind))
        )
        object.__setattr__(self, "action_id", self.action_id.strip())
        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "due_tick", due_tick)
        object.__setattr__(self, "stage_kind", _stage_kind(self.stage_kind))
        object.__setattr__(
            self,
            "correlation_key",
            _correlation_key(self.correlation_key),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )


@dataclass(frozen=True, slots=True)
class FakeRuntimeTraceEvent:
    """Immutable public-safe event in a deterministic controller trace."""

    index: int
    tick: int
    kind: FakeRuntimeTraceKind | str
    action_id: str | None = None
    action_kind: FakeRuntimeActionKind | str | None = None
    stage_kind: RealtimeStageKind | str | None = None
    correlation_key: str | None = None
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        index = _non_negative_tick(self.index, name="index")
        tick = _non_negative_tick(self.tick, name="tick")
        kind = (
            self.kind
            if isinstance(self.kind, FakeRuntimeTraceKind)
            else FakeRuntimeTraceKind(str(self.kind))
        )
        action_kind = (
            None
            if self.action_kind is None
            else (
                self.action_kind
                if isinstance(self.action_kind, FakeRuntimeActionKind)
                else FakeRuntimeActionKind(str(self.action_kind))
            )
        )
        if self.action_id is not None and (
            not isinstance(self.action_id, str) or not self.action_id.strip()
        ):
            raise ValueError("action_id must be a non-empty string or None")
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "action_id",
            None if self.action_id is None else self.action_id.strip(),
        )
        object.__setattr__(self, "action_kind", action_kind)
        object.__setattr__(self, "stage_kind", _stage_kind(self.stage_kind))
        object.__setattr__(
            self,
            "correlation_key",
            _correlation_key(self.correlation_key),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )


@dataclass(order=True, slots=True)
class _ScheduledAction:
    due_tick: int
    sequence: int
    action: FakeRuntimeAction = field(compare=False)
    callback: FakeRuntimeCallback = field(compare=False, repr=False)


def deterministic_trace_signature(
    trace: Sequence[FakeRuntimeTraceEvent],
) -> tuple[str, ...]:
    """Return an exact, metadata-free signature suitable for stable assertions."""

    signature: list[str] = []
    for event in trace:
        if not isinstance(event, FakeRuntimeTraceEvent):
            raise TypeError("trace must contain FakeRuntimeTraceEvent values")
        signature.append(
            "|".join(
                (
                    str(event.index),
                    str(event.tick),
                    event.kind.value,
                    event.action_id or "-",
                    event.action_kind.value if event.action_kind is not None else "-",
                    event.stage_kind.value if event.stage_kind is not None else "-",
                    event.correlation_key or "-",
                )
            )
        )
    return tuple(signature)


def assert_deterministic_trace(
    trace: Sequence[FakeRuntimeTraceEvent],
    expected_signature: Sequence[str],
) -> None:
    """Assert exact deterministic trace identity without exposing metadata values."""

    actual = deterministic_trace_signature(trace)
    expected = tuple(expected_signature)
    if any(not isinstance(item, str) for item in expected):
        raise TypeError("expected_signature must contain strings")
    if actual != expected:
        mismatch_index = min(len(actual), len(expected))
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            if actual_item != expected_item:
                mismatch_index = index
                break
        raise AssertionError(
            "deterministic trace mismatch "
            f"at index {mismatch_index}; expected {len(expected)} events, "
            f"received {len(actual)}"
        )


class DeterministicFakeScheduler:
    """Single-thread deterministic scheduler with stage-aware pause semantics."""

    def __init__(
        self,
        *,
        clock: DeterministicFakeClock | None = None,
        max_queue_size: int = 1024,
    ) -> None:
        self._clock = clock if clock is not None else DeterministicFakeClock()
        if not isinstance(self._clock, DeterministicFakeClock):
            raise TypeError("clock must be a DeterministicFakeClock")
        self._max_queue_size = _positive_count(
            max_queue_size,
            name="max_queue_size",
        )
        self._queue: list[_ScheduledAction] = []
        self._paused_stage_kinds: set[RealtimeStageKind] = set()
        self._trace: list[FakeRuntimeTraceEvent] = []
        self._next_sequence = 0
        self._closed = False

    @property
    def clock(self) -> DeterministicFakeClock:
        return self._clock

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def max_queue_size(self) -> int:
        return self._max_queue_size

    @property
    def paused_stage_kinds(self) -> tuple[RealtimeStageKind, ...]:
        return tuple(
            stage_kind
            for stage_kind in RealtimeStageKind
            if stage_kind in self._paused_stage_kinds
        )

    @property
    def trace(self) -> tuple[FakeRuntimeTraceEvent, ...]:
        return tuple(self._trace)

    @property
    def closed(self) -> bool:
        return self._closed

    def clear_trace(self) -> None:
        self._trace.clear()

    def _record(
        self,
        kind: FakeRuntimeTraceKind,
        *,
        action: FakeRuntimeAction | None = None,
        stage_kind: RealtimeStageKind | str | None = None,
        correlation_key: str | None = None,
        public_metadata: Mapping[str, object] | None = None,
    ) -> FakeRuntimeTraceEvent:
        event = FakeRuntimeTraceEvent(
            index=len(self._trace),
            tick=self._clock.now_tick,
            kind=kind,
            action_id=None if action is None else action.action_id,
            action_kind=None if action is None else action.kind,
            stage_kind=(
                action.stage_kind
                if action is not None
                else _stage_kind(stage_kind)
            ),
            correlation_key=(
                action.correlation_key
                if action is not None
                else _correlation_key(correlation_key)
            ),
            public_metadata=public_metadata or {},
        )
        self._trace.append(event)
        return event

    def _ensure_open(self) -> None:
        if self._closed:
            raise FakeRuntimeClosedError("fake runtime controller is closed")

    def _ensure_capacity(self, count: int = 1) -> None:
        count = _positive_count(count, name="count")
        if len(self._queue) + count > self._max_queue_size:
            self._record(
                FakeRuntimeTraceKind.QUEUE_OVERFLOW_INJECTED,
                public_metadata={
                    "pending_count": len(self._queue),
                    "requested_count": count,
                    "max_queue_size": self._max_queue_size,
                },
            )
            raise FakeRuntimeQueueOverflow(
                "deterministic fake runtime queue capacity exceeded"
            )

    def schedule(
        self,
        callback: FakeRuntimeCallback,
        *,
        delay_ticks: int = 0,
        kind: FakeRuntimeActionKind | str = FakeRuntimeActionKind.CUSTOM,
        stage_kind: RealtimeStageKind | str | None = None,
        correlation_key: str | None = None,
        public_metadata: Mapping[str, object] | None = None,
    ) -> FakeRuntimeAction:
        """Schedule one callback at ``now + delay_ticks`` in insertion order."""

        self._ensure_open()
        if not callable(callback):
            raise TypeError("callback must be callable")
        delay_ticks = _non_negative_tick(delay_ticks, name="delay_ticks")
        self._ensure_capacity()
        sequence = self._next_sequence
        self._next_sequence += 1
        action = FakeRuntimeAction(
            action_id=f"fake-action-{sequence:06d}",
            sequence=sequence,
            kind=kind,
            due_tick=self._clock.now_tick + delay_ticks,
            stage_kind=stage_kind,
            correlation_key=correlation_key,
            public_metadata=public_metadata or {},
        )
        heapq.heappush(
            self._queue,
            _ScheduledAction(
                due_tick=action.due_tick,
                sequence=action.sequence,
                action=action,
                callback=callback,
            ),
        )
        self._record(FakeRuntimeTraceKind.ACTION_SCHEDULED, action=action)
        return action

    def pause_stage(self, stage_kind: RealtimeStageKind | str) -> bool:
        self._ensure_open()
        normalized = _stage_kind(stage_kind)
        if normalized is None:
            raise ValueError("stage_kind is required")
        if normalized in self._paused_stage_kinds:
            return False
        self._paused_stage_kinds.add(normalized)
        self._record(
            FakeRuntimeTraceKind.STAGE_PAUSED,
            stage_kind=normalized,
        )
        return True

    def resume_stage(self, stage_kind: RealtimeStageKind | str) -> bool:
        self._ensure_open()
        normalized = _stage_kind(stage_kind)
        if normalized is None:
            raise ValueError("stage_kind is required")
        if normalized not in self._paused_stage_kinds:
            return False
        self._paused_stage_kinds.remove(normalized)
        self._record(
            FakeRuntimeTraceKind.STAGE_RESUMED,
            stage_kind=normalized,
        )
        return True

    def _entry_is_runnable(self, entry: _ScheduledAction) -> bool:
        stage_kind = entry.action.stage_kind
        return (
            stage_kind is None
            or stage_kind not in self._paused_stage_kinds
        )

    def _pop_next_runnable(
        self,
        *,
        due_only: bool,
    ) -> _ScheduledAction | None:
        best_index: int | None = None
        best_key: tuple[int, int] | None = None
        for index, entry in enumerate(self._queue):
            if due_only and entry.due_tick > self._clock.now_tick:
                continue
            if not self._entry_is_runnable(entry):
                continue
            key = (entry.due_tick, entry.sequence)
            if best_key is None or key < best_key:
                best_index = index
                best_key = key
        if best_index is None:
            return None
        entry = self._queue[best_index]
        last = self._queue.pop()
        if best_index < len(self._queue):
            self._queue[best_index] = last
            heapq.heapify(self._queue)
        return entry

    def _advance_to(self, tick: int) -> None:
        if tick <= self._clock.now_tick:
            return
        previous = self._clock.now_tick
        self._clock.advance_to(tick)
        self._record(
            FakeRuntimeTraceKind.CLOCK_ADVANCED,
            public_metadata={
                "from_tick": previous,
                "to_tick": tick,
            },
        )

    def _execute(self, entry: _ScheduledAction) -> FakeRuntimeAction:
        action = entry.action
        self._record(FakeRuntimeTraceKind.ACTION_EXECUTED, action=action)
        try:
            entry.callback(action)
        except Exception:
            self._record(
                FakeRuntimeTraceKind.ACTION_FAILED,
                action=action,
                public_metadata={"failure": "callback_error"},
            )
            raise
        return action

    def run_next(self) -> FakeRuntimeAction | None:
        """Run the earliest unpaused action, advancing fake time if required."""

        self._ensure_open()
        entry = self._pop_next_runnable(due_only=False)
        if entry is None:
            return None
        self._advance_to(entry.due_tick)
        return self._execute(entry)

    def run_due(self, *, max_actions: int | None = None) -> tuple[FakeRuntimeAction, ...]:
        """Run unpaused actions whose due tick is not later than ``now``."""

        self._ensure_open()
        if max_actions is not None:
            max_actions = _positive_count(max_actions, name="max_actions")
        executed: list[FakeRuntimeAction] = []
        while max_actions is None or len(executed) < max_actions:
            entry = self._pop_next_runnable(due_only=True)
            if entry is None:
                break
            executed.append(self._execute(entry))
        return tuple(executed)

    def advance_by(
        self,
        ticks: int,
        *,
        run_due: bool = True,
    ) -> tuple[FakeRuntimeAction, ...]:
        """Advance fake time and optionally dispatch all newly due actions."""

        self._ensure_open()
        ticks = _non_negative_tick(ticks, name="ticks")
        if ticks:
            self._advance_to(self._clock.now_tick + ticks)
        return self.run_due() if run_due else ()

    def run_until_idle(
        self,
        *,
        max_actions: int = 10000,
    ) -> tuple[FakeRuntimeAction, ...]:
        """Run all reachable unpaused work without wall-clock waiting.

        Work blocked only by paused stages remains queued and the method returns.
        """

        self._ensure_open()
        max_actions = _positive_count(max_actions, name="max_actions")
        executed: list[FakeRuntimeAction] = []
        while len(executed) < max_actions:
            action = self.run_next()
            if action is None:
                break
            executed.append(action)
        if len(executed) == max_actions and any(
            self._entry_is_runnable(entry) for entry in self._queue
        ):
            raise RuntimeError("deterministic fake runtime max_actions exceeded")
        return tuple(executed)

    def inject_queue_overflow(
        self,
        *,
        stage_kind: RealtimeStageKind | str | None = None,
        correlation_key: str | None = None,
        public_metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Inject one explicit queue-overflow fault without provider execution."""

        self._ensure_open()
        self._record(
            FakeRuntimeTraceKind.QUEUE_OVERFLOW_INJECTED,
            stage_kind=stage_kind,
            correlation_key=correlation_key,
            public_metadata={
                "pending_count": len(self._queue),
                "max_queue_size": self._max_queue_size,
                **dict(public_metadata or {}),
            },
        )
        raise FakeRuntimeQueueOverflow(
            "deterministic fake runtime queue overflow injected"
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.clear()
        self._paused_stage_kinds.clear()
        self._record(FakeRuntimeTraceKind.CONTROLLER_CLOSED)


class DeterministicFakeRuntimeController:
    """High-level deterministic race/fault injection controller."""

    def __init__(
        self,
        *,
        initial_tick: int = 0,
        max_queue_size: int = 1024,
    ) -> None:
        self._clock = DeterministicFakeClock(initial_tick)
        self._scheduler = DeterministicFakeScheduler(
            clock=self._clock,
            max_queue_size=max_queue_size,
        )

    @property
    def clock(self) -> DeterministicFakeClock:
        return self._clock

    @property
    def scheduler(self) -> DeterministicFakeScheduler:
        return self._scheduler

    @property
    def trace(self) -> tuple[FakeRuntimeTraceEvent, ...]:
        return self._scheduler.trace

    @property
    def pending_count(self) -> int:
        return self._scheduler.pending_count

    @property
    def paused_stage_kinds(self) -> tuple[RealtimeStageKind, ...]:
        return self._scheduler.paused_stage_kinds

    @property
    def closed(self) -> bool:
        return self._scheduler.closed

    def clear_trace(self) -> None:
        self._scheduler.clear_trace()

    def schedule_stage_action(
        self,
        stage_kind: RealtimeStageKind | str,
        callback: FakeRuntimeCallback,
        *,
        delay_ticks: int = 0,
        correlation_key: str | None = None,
        public_metadata: Mapping[str, object] | None = None,
    ) -> FakeRuntimeAction:
        return self._scheduler.schedule(
            callback,
            delay_ticks=delay_ticks,
            kind=FakeRuntimeActionKind.STAGE_ACTION,
            stage_kind=stage_kind,
            correlation_key=correlation_key,
            public_metadata=public_metadata,
        )

    def pause_stage(self, stage_kind: RealtimeStageKind | str) -> bool:
        return self._scheduler.pause_stage(stage_kind)

    def resume_stage(self, stage_kind: RealtimeStageKind | str) -> bool:
        return self._scheduler.resume_stage(stage_kind)

    def advance_by(
        self,
        ticks: int,
        *,
        run_due: bool = True,
    ) -> tuple[FakeRuntimeAction, ...]:
        return self._scheduler.advance_by(ticks, run_due=run_due)

    def run_next(self) -> FakeRuntimeAction | None:
        return self._scheduler.run_next()

    def run_due(self, *, max_actions: int | None = None) -> tuple[FakeRuntimeAction, ...]:
        return self._scheduler.run_due(max_actions=max_actions)

    def run_until_idle(
        self,
        *,
        max_actions: int = 10000,
    ) -> tuple[FakeRuntimeAction, ...]:
        return self._scheduler.run_until_idle(max_actions=max_actions)

    def inject_late_completion(
        self,
        stage_kind: RealtimeStageKind | str,
        callback: FakeRuntimeCallback,
        *,
        delay_ticks: int = 0,
        correlation_key: str,
        public_metadata: Mapping[str, object] | None = None,
    ) -> FakeRuntimeAction:
        """Schedule one caller-defined completion after a deterministic delay.

        The target callback decides whether the supplied completion is stale. The
        controller intentionally does not inspect a live generation registry.
        """

        normalized = _stage_kind(stage_kind)
        if normalized is None:
            raise ValueError("stage_kind is required")
        correlation_key = _correlation_key(correlation_key)
        self._scheduler._ensure_open()
        self._scheduler._ensure_capacity()
        self._scheduler._record(
            FakeRuntimeTraceKind.LATE_COMPLETION_INJECTED,
            stage_kind=normalized,
            correlation_key=correlation_key,
            public_metadata=public_metadata,
        )
        return self._scheduler.schedule(
            callback,
            delay_ticks=delay_ticks,
            kind=FakeRuntimeActionKind.LATE_COMPLETION,
            stage_kind=normalized,
            correlation_key=correlation_key,
            public_metadata=public_metadata,
        )

    def inject_duplicate_terminal(
        self,
        stage_kind: RealtimeStageKind | str,
        callback: FakeRuntimeCallback,
        *,
        correlation_key: str,
        copies: int = 2,
        delay_ticks: int = 0,
        interval_ticks: int = 0,
        public_metadata: Mapping[str, object] | None = None,
    ) -> tuple[FakeRuntimeAction, ...]:
        """Schedule two or more same-key terminal deliveries in fixed order."""

        normalized = _stage_kind(stage_kind)
        if normalized is None:
            raise ValueError("stage_kind is required")
        copies = _positive_count(copies, name="copies", minimum=2)
        delay_ticks = _non_negative_tick(delay_ticks, name="delay_ticks")
        interval_ticks = _non_negative_tick(interval_ticks, name="interval_ticks")
        correlation_key = _correlation_key(correlation_key)
        self._scheduler._ensure_open()
        self._scheduler._ensure_capacity(copies)
        self._scheduler._record(
            FakeRuntimeTraceKind.DUPLICATE_TERMINAL_INJECTED,
            stage_kind=normalized,
            correlation_key=correlation_key,
            public_metadata={
                "copies": copies,
                "interval_ticks": interval_ticks,
                **dict(public_metadata or {}),
            },
        )
        return tuple(
            self._scheduler.schedule(
                callback,
                delay_ticks=delay_ticks + (index * interval_ticks),
                kind=FakeRuntimeActionKind.TERMINAL,
                stage_kind=normalized,
                correlation_key=correlation_key,
                public_metadata={
                    "duplicate_ordinal": index,
                    "duplicate_count": copies,
                    **dict(public_metadata or {}),
                },
            )
            for index in range(copies)
        )

    def inject_cancellation_timeout(
        self,
        stage_kind: RealtimeStageKind | str,
        callback: FakeRuntimeCallback,
        *,
        timeout_ticks: int,
        correlation_key: str,
        public_metadata: Mapping[str, object] | None = None,
    ) -> FakeRuntimeAction:
        """Schedule one deterministic cancellation-timeout callback."""

        normalized = _stage_kind(stage_kind)
        if normalized is None:
            raise ValueError("stage_kind is required")
        timeout_ticks = _non_negative_tick(timeout_ticks, name="timeout_ticks")
        correlation_key = _correlation_key(correlation_key)
        self._scheduler._ensure_open()
        self._scheduler._ensure_capacity()
        self._scheduler._record(
            FakeRuntimeTraceKind.CANCELLATION_TIMEOUT_INJECTED,
            stage_kind=normalized,
            correlation_key=correlation_key,
            public_metadata={
                "timeout_ticks": timeout_ticks,
                **dict(public_metadata or {}),
            },
        )
        return self._scheduler.schedule(
            callback,
            delay_ticks=timeout_ticks,
            kind=FakeRuntimeActionKind.CANCELLATION_TIMEOUT,
            stage_kind=normalized,
            correlation_key=correlation_key,
            public_metadata=public_metadata,
        )

    def inject_queue_overflow(
        self,
        *,
        stage_kind: RealtimeStageKind | str | None = None,
        correlation_key: str | None = None,
        public_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self._scheduler.inject_queue_overflow(
            stage_kind=stage_kind,
            correlation_key=correlation_key,
            public_metadata=public_metadata,
        )

    def trace_signature(self) -> tuple[str, ...]:
        return deterministic_trace_signature(self.trace)

    def assert_trace(self, expected_signature: Sequence[str]) -> None:
        assert_deterministic_trace(self.trace, expected_signature)

    def close(self) -> None:
        self._scheduler.close()


__all__ = [
    "FakeRuntimeActionKind",
    "FakeRuntimeTraceKind",
    "FakeRuntimeQueueOverflow",
    "FakeRuntimeClosedError",
    "DeterministicFakeClock",
    "FakeRuntimeAction",
    "FakeRuntimeTraceEvent",
    "deterministic_trace_signature",
    "assert_deterministic_trace",
    "DeterministicFakeScheduler",
    "DeterministicFakeRuntimeController",
]
