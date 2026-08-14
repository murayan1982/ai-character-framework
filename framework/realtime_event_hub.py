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

from .backpressure import (
    BackpressureAdmissionResult,
    BackpressureBoundary,
    BackpressureCapability,
    BackpressureControlResult,
    BackpressureOverflowEvent,
    BackpressureSnapshot,
)
from .backpressure_runtime import BoundedBackpressureRuntime
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


class EventHubBackpressureError(RuntimeError):
    """Typed retryable delivery rejection without event acceptance or loss."""

    def __init__(self, result: BackpressureAdmissionResult) -> None:
        if not isinstance(result, BackpressureAdmissionResult):
            raise TypeError("result must be a BackpressureAdmissionResult")
        self.result = result
        super().__init__(result.safe_message or "Realtime event delivery was rejected.")

    @property
    def retryable(self) -> bool:
        return self.result.retryable


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
    delivery_backpressure_rejection_count: int


@dataclass(frozen=True, slots=True)
class _Delivery(Generic[EventT]):
    event: EventT
    callbacks: tuple[EventCallback[EventT], ...]
    legacy_event: EventT | None
    legacy_callbacks: tuple[EventCallback[EventT], ...]
    backpressure_item_id: str
    response_delta: bool


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
        delivery_pending_limit: int = 64,
        slow_callback_seconds: float = 0.25,
        clock: Clock = time.monotonic,
        on_backpressure_overflow: Callable[[BackpressureOverflowEvent], None]
        | None = None,
    ) -> None:
        if isinstance(history_limit, bool) or not isinstance(history_limit, int):
            raise TypeError("history_limit must be an integer")
        if history_limit < 2:
            raise ValueError("history_limit must be at least 2")
        if isinstance(delivery_pending_limit, bool) or not isinstance(
            delivery_pending_limit,
            int,
        ):
            raise TypeError("delivery_pending_limit must be an integer")
        if delivery_pending_limit < 1:
            raise ValueError("delivery_pending_limit must be at least 1")
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
        self._event_subscriber_backpressure = BoundedBackpressureRuntime(
            boundary=BackpressureBoundary.EVENT_SUBSCRIBER,
            maximum_pending_count=delivery_pending_limit,
            maximum_in_flight_count=1,
            on_overflow=on_backpressure_overflow,
            public_metadata={"owner": "realtime_event_hub"},
        )
        self._response_delta_backpressure = BoundedBackpressureRuntime(
            boundary=BackpressureBoundary.RESPONSE_DELTA,
            maximum_pending_count=delivery_pending_limit,
            maximum_in_flight_count=1,
            on_overflow=on_backpressure_overflow,
            public_metadata={"owner": "realtime_event_hub"},
        )
        self._next_sequence = EventSequence.first()
        self._closed = False
        self._dispatching = False

        self._emitted_event_count = 0
        self._callback_error_count = 0
        self._slow_callback_count = 0
        self._history_overflow_count = 0
        self._rejected_after_close_count = 0
        self._delivery_backpressure_rejection_count = 0

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
                delivery_backpressure_rejection_count=(
                    self._delivery_backpressure_rejection_count
                ),
            )

    def backpressure_capability(
        self,
        boundary: BackpressureBoundary | str,
    ) -> BackpressureCapability:
        return self._backpressure_runtime(boundary).capability

    def backpressure_snapshot(
        self,
        boundary: BackpressureBoundary | str,
    ) -> BackpressureSnapshot:
        return self._backpressure_runtime(boundary).snapshot

    def last_backpressure_rejection(
        self,
        boundary: BackpressureBoundary | str,
    ) -> BackpressureAdmissionResult | None:
        return self._backpressure_runtime(boundary).last_rejection

    def pause_backpressure(
        self,
        boundary: BackpressureBoundary | str,
    ) -> BackpressureControlResult:
        return self._backpressure_runtime(boundary).pause()

    def resume_backpressure(
        self,
        boundary: BackpressureBoundary | str,
    ) -> BackpressureControlResult:
        return self._backpressure_runtime(boundary).resume()

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

            event_sequence = self._next_sequence
            event = event_factory(event_sequence)
            self._require_factory_sequence(event, event_sequence)

            overflow_event: EventT | None = None
            drop_count = 0
            first_dropped_sequence: EventSequence | None = None
            if len(self._history) >= self._history_limit:
                reserved_slots = 2 if overflow_event_factory is not None else 1
                drop_count = len(self._history) + reserved_slots - self._history_limit
                if drop_count:
                    first_dropped_sequence = self._read_event_sequence(
                        self._history[0]
                    )

                if overflow_event_factory is not None:
                    overflow_sequence = event_sequence.next()
                    overflow_event = overflow_event_factory(
                        overflow_sequence,
                        first_dropped_sequence,
                        self._history_overflow_count + drop_count,
                    )
                    self._require_factory_sequence(
                        overflow_event,
                        overflow_sequence,
                    )
            deliveries = [event]
            if overflow_event is not None:
                deliveries.append(overflow_event)
            accepted_items: list[tuple[str, bool]] = []
            try:
                for delivery_event in deliveries:
                    accepted_items.append(
                        self._admit_delivery_locked(delivery_event)
                    )
            except EventHubBackpressureError:
                for item_id, response_delta in accepted_items:
                    self._event_subscriber_backpressure.withdraw_pending(item_id)
                    if response_delta:
                        self._response_delta_backpressure.withdraw_pending(item_id)
                self._delivery_backpressure_rejection_count += 1
                raise

            self._next_sequence = event_sequence.next()
            self._emitted_event_count += 1
            if overflow_event is not None:
                self._next_sequence = self._next_sequence.next()
                self._emitted_event_count += 1
            for _ in range(drop_count):
                self._history.popleft()
            self._history_overflow_count += drop_count

            self._history.append(event)
            self._pending.append(
                self._delivery_locked(
                    event,
                    legacy_projector,
                    backpressure_item_id=accepted_items[0][0],
                    response_delta=accepted_items[0][1],
                )
            )

            if overflow_event is not None:
                self._history.append(overflow_event)
                self._pending.append(
                    self._delivery_locked(
                        overflow_event,
                        legacy_projector,
                        backpressure_item_id=accepted_items[1][0],
                        response_delta=accepted_items[1][1],
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
            self._event_subscriber_backpressure.close()
            self._response_delta_backpressure.close()
            return True

    def _allocate_sequence_locked(self) -> EventSequence:
        sequence = self._next_sequence
        self._next_sequence = sequence.next()
        return sequence

    def _delivery_locked(
        self,
        event: EventT,
        legacy_projector: LegacyProjector[EventT] | None,
        *,
        backpressure_item_id: str,
        response_delta: bool,
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
            backpressure_item_id=backpressure_item_id,
            response_delta=response_delta,
        )

    def _drain_deliveries(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    self._dispatching = False
                    return
                delivery = self._pending.popleft()

            subscriber_claim = self._event_subscriber_backpressure.claim(
                delivery.backpressure_item_id
            )
            if subscriber_claim is None:
                raise RuntimeError("event-subscriber backpressure claim drift")
            if delivery.response_delta:
                response_claim = self._response_delta_backpressure.claim(
                    delivery.backpressure_item_id
                )
                if response_claim is None:
                    self._event_subscriber_backpressure.complete(
                        delivery.backpressure_item_id
                    )
                    raise RuntimeError("response-delta backpressure claim drift")

            try:
                self._deliver_callbacks(
                    delivery.callbacks,
                    delivery.event,
                )
                if delivery.legacy_event is not None:
                    self._deliver_callbacks(
                        delivery.legacy_callbacks,
                        delivery.legacy_event,
                    )
            finally:
                self._event_subscriber_backpressure.complete(
                    delivery.backpressure_item_id
                )
                if delivery.response_delta:
                    self._response_delta_backpressure.complete(
                        delivery.backpressure_item_id
                    )

    def _admit_delivery_locked(self, event: EventT) -> tuple[str, bool]:
        sequence = self._read_event_sequence(event)
        if sequence is None:
            raise ValueError("event must expose an EventSequence")
        item_id = f"event_{int(sequence)}"
        response_delta = self._is_response_delta(event)
        subscriber_result = self._event_subscriber_backpressure.admit_item(
            item_id,
            public_metadata={"event_sequence": int(sequence)},
        )
        if not subscriber_result.accepted:
            raise EventHubBackpressureError(subscriber_result)
        if response_delta:
            response_result = self._response_delta_backpressure.admit_item(
                item_id,
                public_metadata={"event_sequence": int(sequence)},
            )
            if not response_result.accepted:
                self._event_subscriber_backpressure.withdraw_pending(item_id)
                raise EventHubBackpressureError(response_result)
        return item_id, response_delta

    def _backpressure_runtime(
        self,
        boundary: BackpressureBoundary | str,
    ) -> BoundedBackpressureRuntime:
        resolved = (
            boundary
            if isinstance(boundary, BackpressureBoundary)
            else BackpressureBoundary(str(boundary))
        )
        if resolved is BackpressureBoundary.EVENT_SUBSCRIBER:
            return self._event_subscriber_backpressure
        if resolved is BackpressureBoundary.RESPONSE_DELTA:
            return self._response_delta_backpressure
        raise ValueError("event hub owns only response_delta and event_subscriber")

    @staticmethod
    def _is_response_delta(event: EventT) -> bool:
        value = getattr(event, "type", None)
        value = getattr(value, "value", value)
        return value == "realtime.response.delta"

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
    "EventHubBackpressureError",
    "EventSubscriptionToken",
    "EventHubDiagnostics",
    "RealtimeEventHub",
]
