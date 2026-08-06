"""Internal realtime event sequencer and subscriber-hub primitives.

This module is provider-neutral and runtime-safe. It owns session-local sequence
allocation, callback registration tokens, serialized callback delivery, bounded
history, overflow diagnostics, callback-failure isolation, slow-subscriber
accounting, and close-after-emission rejection.

The module is intentionally not exported from ``framework`` root in
FW-RT6-2b Control A. ``RealtimeSession`` adoption is a later control.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import re
from threading import RLock
import time
from typing import Callable, Generic, TypeVar
from uuid import uuid4

from .identity import EventSequence


EventT = TypeVar("EventT")
EventCallback = Callable[[EventT], None]
EventFactory = Callable[[EventSequence], EventT]
LegacyProjector = Callable[[EventT], EventT | None]
OverflowEventFactory = Callable[
    [EventSequence, EventSequence | None, int],
    EventT,
]
Clock = Callable[[], float]

_SUBSCRIPTION_TOKEN_PATTERN = re.compile(r"^fw_event_sub_[0-9a-f]{32}$")


class EventHubClosedError(RuntimeError):
    """Raised when registration or emission is attempted after hub close."""


class EventSubscriptionToken(str):
    """Opaque token used to unregister one event callback."""

    _prefix = "fw_event_sub_"

    def __new__(cls, value: str) -> "EventSubscriptionToken":
        if not isinstance(value, str):
            raise TypeError("EventSubscriptionToken value must be a string")
        if not _SUBSCRIPTION_TOKEN_PATTERN.fullmatch(value):
            raise ValueError("Invalid event subscription token.")
        return str.__new__(cls, value)

    @classmethod
    def new(cls) -> "EventSubscriptionToken":
        return cls(f"{cls._prefix}{uuid4().hex}")

    @classmethod
    def parse(
        cls,
        value: "EventSubscriptionToken | str",
    ) -> "EventSubscriptionToken":
        if isinstance(value, cls):
            return value
        return cls(value)


@dataclass(frozen=True, slots=True)
class EventHubDiagnostics:
    """Immutable public-safe counters for one event hub."""

    emitted_event_count: int
    callback_error_count: int
    slow_callback_count: int
    history_overflow_count: int
    rejected_after_close_count: int


@dataclass(frozen=True, slots=True)
class _Delivery(Generic[EventT]):
    event: EventT
    callbacks: tuple[EventCallback[EventT], ...]
    legacy_event: EventT | None
    legacy_callbacks: tuple[EventCallback[EventT], ...]


class RealtimeEventHub(Generic[EventT]):
    """Serialize one session's event allocation, history, and callback delivery.

    Delivery policy is deliberately synchronous and serialized. A slow callback
    may delay the current dispatcher, but cannot reorder event delivery, escape
    an exception into the emitting runtime, or cause a background-thread leak.
    Slow callbacks are measured and retained; automatic eviction is deferred.

    Callback snapshots are captured when an event is accepted. Unregistration
    prevents future accepted events, while already accepted deliveries retain
    their original snapshot.
    """

    def __init__(
        self,
        *,
        history_limit: int = 64,
        slow_callback_seconds: float = 0.25,
        clock: Clock = time.monotonic,
    ) -> None:
        if isinstance(history_limit, bool) or not isinstance(history_limit, int):
            raise TypeError("history_limit must be an integer")
        if history_limit < 2:
            raise ValueError("history_limit must be at least 2")
        if isinstance(slow_callback_seconds, bool) or not isinstance(
            slow_callback_seconds,
            (int, float),
        ):
            raise TypeError("slow_callback_seconds must be a number")
        resolved_slow_seconds = float(slow_callback_seconds)
        if not math.isfinite(resolved_slow_seconds) or resolved_slow_seconds < 0.0:
            raise ValueError(
                "slow_callback_seconds must be a finite non-negative number"
            )
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._history_limit = history_limit
        self._slow_callback_seconds = resolved_slow_seconds
        self._clock = clock
        self._lock = RLock()
        self._callbacks: dict[
            EventSubscriptionToken,
            EventCallback[EventT],
        ] = {}
        self._legacy_callbacks: dict[
            EventSubscriptionToken,
            EventCallback[EventT],
        ] = {}
        self._history: deque[EventT] = deque()
        self._pending: deque[_Delivery[EventT]] = deque()
        self._next_sequence = EventSequence.first()
        self._closed = False
        self._dispatching = False

        self._emitted_event_count = 0
        self._callback_error_count = 0
        self._slow_callback_count = 0
        self._history_overflow_count = 0
        self._rejected_after_close_count = 0

    @property
    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def history_limit(self) -> int:
        return self._history_limit

    @property
    def slow_callback_seconds(self) -> float:
        return self._slow_callback_seconds

    @property
    def event_history(self) -> tuple[EventT, ...]:
        with self._lock:
            return tuple(self._history)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._callbacks) + len(self._legacy_callbacks)

    @property
    def diagnostics(self) -> EventHubDiagnostics:
        with self._lock:
            return EventHubDiagnostics(
                emitted_event_count=self._emitted_event_count,
                callback_error_count=self._callback_error_count,
                slow_callback_count=self._slow_callback_count,
                history_overflow_count=self._history_overflow_count,
                rejected_after_close_count=self._rejected_after_close_count,
            )

    def subscribe(
        self,
        callback: EventCallback[EventT],
        *,
        legacy: bool = False,
    ) -> EventSubscriptionToken:
        """Register a canonical or legacy callback and return its opaque token."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        if type(legacy) is not bool:
            raise TypeError("legacy must be a boolean")

        with self._lock:
            if self._closed:
                raise EventHubClosedError("Realtime event hub is closed.")
            token = EventSubscriptionToken.new()
            target = self._legacy_callbacks if legacy else self._callbacks
            target[token] = callback
            return token

    def unsubscribe(
        self,
        token: EventSubscriptionToken | str,
    ) -> bool:
        """Remove one callback token; return whether a registration existed."""

        resolved = EventSubscriptionToken.parse(token)
        with self._lock:
            removed = self._callbacks.pop(resolved, None)
            legacy_removed = self._legacy_callbacks.pop(resolved, None)
            return removed is not None or legacy_removed is not None

    def emit(
        self,
        event_factory: EventFactory[EventT],
        *,
        legacy_projector: LegacyProjector[EventT] | None = None,
        overflow_event_factory: OverflowEventFactory[EventT] | None = None,
    ) -> EventT:
        """Accept one event, allocate sequence, and serialize callback delivery.

        When bounded history is full, the oldest records are dropped
        deterministically. ``history_overflow_count`` always records the loss.
        When ``overflow_event_factory`` is supplied, a second sequenced event is
        accepted and delivered as the non-silent overflow diagnostic.
        """

        if not callable(event_factory):
            raise TypeError("event_factory must be callable")
        if legacy_projector is not None and not callable(legacy_projector):
            raise TypeError("legacy_projector must be callable or None")
        if overflow_event_factory is not None and not callable(
            overflow_event_factory
        ):
            raise TypeError("overflow_event_factory must be callable or None")

        should_dispatch = False
        with self._lock:
            if self._closed:
                self._rejected_after_close_count += 1
                raise EventHubClosedError("Realtime event hub is closed.")

            event_sequence = self._allocate_sequence_locked()
            event = event_factory(event_sequence)
            self._require_factory_sequence(event, event_sequence)
            self._emitted_event_count += 1

            overflow_event: EventT | None = None
            if len(self._history) >= self._history_limit:
                reserved_slots = 2 if overflow_event_factory is not None else 1
                drop_count = len(self._history) + reserved_slots - self._history_limit
                first_dropped_sequence: EventSequence | None = None
                for _ in range(drop_count):
                    dropped = self._history.popleft()
                    if first_dropped_sequence is None:
                        first_dropped_sequence = self._read_event_sequence(dropped)
                self._history_overflow_count += drop_count

                if overflow_event_factory is not None:
                    overflow_sequence = self._allocate_sequence_locked()
                    overflow_event = overflow_event_factory(
                        overflow_sequence,
                        first_dropped_sequence,
                        self._history_overflow_count,
                    )
                    self._require_factory_sequence(
                        overflow_event,
                        overflow_sequence,
                    )
                    self._emitted_event_count += 1

            self._history.append(event)
            self._pending.append(
                self._delivery_locked(event, legacy_projector)
            )

            if overflow_event is not None:
                self._history.append(overflow_event)
                self._pending.append(
                    self._delivery_locked(
                        overflow_event,
                        legacy_projector,
                    )
                )

            if not self._dispatching:
                self._dispatching = True
                should_dispatch = True

        if should_dispatch:
            self._drain_deliveries()

        return event

    def close(self) -> bool:
        """Close the hub and reject later registration or emission."""

        with self._lock:
            if self._closed:
                return False
            self._closed = True
            self._callbacks.clear()
            self._legacy_callbacks.clear()
            return True

    def _allocate_sequence_locked(self) -> EventSequence:
        sequence = self._next_sequence
        self._next_sequence = sequence.next()
        return sequence

    def _delivery_locked(
        self,
        event: EventT,
        legacy_projector: LegacyProjector[EventT] | None,
    ) -> _Delivery[EventT]:
        legacy_event = (
            legacy_projector(event)
            if legacy_projector is not None
            else None
        )
        return _Delivery(
            event=event,
            callbacks=tuple(self._callbacks.values()),
            legacy_event=legacy_event,
            legacy_callbacks=(
                tuple(self._legacy_callbacks.values())
                if legacy_event is not None
                else ()
            ),
        )

    def _drain_deliveries(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    self._dispatching = False
                    return
                delivery = self._pending.popleft()

            self._deliver_callbacks(
                delivery.callbacks,
                delivery.event,
            )
            if delivery.legacy_event is not None:
                self._deliver_callbacks(
                    delivery.legacy_callbacks,
                    delivery.legacy_event,
                )

    def _deliver_callbacks(
        self,
        callbacks: tuple[EventCallback[EventT], ...],
        event: EventT,
    ) -> None:
        for callback in callbacks:
            started = float(self._clock())
            try:
                callback(event)
            except Exception:
                with self._lock:
                    self._callback_error_count += 1
            finally:
                finished = float(self._clock())
                elapsed = max(0.0, finished - started)
                if elapsed > self._slow_callback_seconds:
                    with self._lock:
                        self._slow_callback_count += 1

    @staticmethod
    def _read_event_sequence(event: EventT) -> EventSequence | None:
        value = getattr(event, "sequence", None)
        if value is None:
            return None
        try:
            return EventSequence.parse(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _require_factory_sequence(
        cls,
        event: EventT,
        expected: EventSequence,
    ) -> None:
        actual = cls._read_event_sequence(event)
        if actual != expected:
            raise ValueError(
                "event_factory must retain the allocated EventSequence"
            )


__all__ = [
    "EventHubClosedError",
    "EventSubscriptionToken",
    "EventHubDiagnostics",
    "RealtimeEventHub",
]
