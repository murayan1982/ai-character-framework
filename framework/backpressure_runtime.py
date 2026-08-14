"""Internal bounded runtime owner for the public backpressure vocabulary.

The controller retains opaque item identities only. Payload ownership remains
with the adopting audio-input, response-delta, voice-output, or subscriber
runtime. Capacity rejection is explicit and never consumes or drops the item.
"""

from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Callable, Mapping

from .backpressure import (
    BackpressureAdmission,
    BackpressureAdmissionResult,
    BackpressureBoundary,
    BackpressureCapability,
    BackpressureControlResult,
    BackpressureOperationKind,
    BackpressureOverflowEvent,
    BackpressureRejectionCode,
    BackpressureSnapshot,
    BackpressureState,
)


OverflowCallback = Callable[[BackpressureOverflowEvent], None]


class BoundedBackpressureRuntime:
    """Thread-safe pending/in-flight admission owner for one exact boundary."""

    def __init__(
        self,
        *,
        boundary: BackpressureBoundary | str,
        maximum_pending_count: int,
        maximum_in_flight_count: int,
        pause_resume_supported: bool = True,
        on_overflow: OverflowCallback | None = None,
        public_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self._capability = BackpressureCapability(
            boundary=boundary,
            supported=True,
            maximum_pending_count=maximum_pending_count,
            maximum_in_flight_count=maximum_in_flight_count,
            pause_resume_supported=pause_resume_supported,
            retryable_rejection_supported=True,
            overflow_event_supported=True,
            public_metadata=public_metadata or {},
        )
        if on_overflow is not None and not callable(on_overflow):
            raise TypeError("on_overflow must be callable or None")
        self._on_overflow = on_overflow
        self._lock = RLock()
        self._state = BackpressureState.ACCEPTING
        self._pending: deque[BackpressureAdmission] = deque()
        self._in_flight: dict[str, BackpressureAdmission] = {}
        self._overflow_count = 0
        self._last_rejection: BackpressureAdmissionResult | None = None

    @property
    def capability(self) -> BackpressureCapability:
        return self._capability

    @property
    def snapshot(self) -> BackpressureSnapshot:
        with self._lock:
            return self._snapshot_locked()

    @property
    def pending_item_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(admission.item_id for admission in self._pending)

    @property
    def in_flight_item_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._in_flight)

    @property
    def last_rejection(self) -> BackpressureAdmissionResult | None:
        with self._lock:
            return self._last_rejection

    def admit_item(
        self,
        item_id: str,
        *,
        start_immediately: bool = False,
        public_metadata: Mapping[str, object] | None = None,
    ) -> BackpressureAdmissionResult:
        return self.admit(
            BackpressureAdmission(
                boundary=self._capability.boundary,
                item_id=item_id,
                public_metadata=public_metadata or {},
            ),
            start_immediately=start_immediately,
        )

    def admit(
        self,
        admission: BackpressureAdmission,
        *,
        start_immediately: bool = False,
    ) -> BackpressureAdmissionResult:
        if not isinstance(admission, BackpressureAdmission):
            raise TypeError("admission must be a BackpressureAdmission")
        if admission.boundary is not self._capability.boundary:
            raise ValueError("admission boundary does not match runtime boundary")
        if type(start_immediately) is not bool:
            raise TypeError("start_immediately must be a boolean")

        overflow_event: BackpressureOverflowEvent | None = None
        with self._lock:
            self._require_unique_item_locked(admission.item_id)
            if self._state is BackpressureState.PAUSED:
                result = self._rejected_locked(
                    admission,
                    code=BackpressureRejectionCode.PAUSED,
                    safe_message="Backpressure admission is paused.",
                    retryable=True,
                )
            elif self._state is BackpressureState.CLOSED:
                result = self._rejected_locked(
                    admission,
                    code=BackpressureRejectionCode.CLOSED,
                    safe_message="Backpressure admission is closed.",
                    retryable=False,
                )
            else:
                at_capacity = (
                    len(self._in_flight)
                    >= (self._capability.maximum_in_flight_count or 0)
                    if start_immediately
                    else len(self._pending)
                    >= (self._capability.maximum_pending_count or 0)
                )
                if at_capacity:
                    self._overflow_count += 1
                    result = self._rejected_locked(
                        admission,
                        code=BackpressureRejectionCode.CAPACITY_REACHED,
                        safe_message="Backpressure capacity was reached.",
                        retryable=True,
                    )
                    overflow_event = BackpressureOverflowEvent(
                        admission=admission,
                        snapshot=result.snapshot,
                        public_metadata={
                            "boundary": self._capability.boundary.value,
                            "overflow_policy": self._capability.overflow_policy.value,
                        },
                    )
                else:
                    if start_immediately:
                        self._in_flight[admission.item_id] = admission
                    else:
                        self._pending.append(admission)
                    result = BackpressureAdmissionResult(
                        accepted=True,
                        admission=admission,
                        snapshot=self._snapshot_locked(),
                        safe_message="Backpressure admission was accepted.",
                    )
                    self._last_rejection = None

        if overflow_event is not None:
            self._deliver_overflow(overflow_event)
        return result

    def claim(
        self,
        item_id: str | None = None,
    ) -> BackpressureAdmission | None:
        """Move already accepted pending work to in-flight capacity."""

        if item_id is not None and not isinstance(item_id, str):
            raise TypeError("item_id must be a string or None")
        with self._lock:
            if len(self._in_flight) >= (
                self._capability.maximum_in_flight_count or 0
            ):
                return None
            admission: BackpressureAdmission | None = None
            if item_id is None:
                if self._pending:
                    admission = self._pending.popleft()
            else:
                kept: deque[BackpressureAdmission] = deque()
                while self._pending:
                    current = self._pending.popleft()
                    if admission is None and current.item_id == item_id:
                        admission = current
                    else:
                        kept.append(current)
                self._pending = kept
            if admission is None:
                return None
            self._in_flight[admission.item_id] = admission
            return admission

    def complete(self, item_id: str) -> bool:
        if not isinstance(item_id, str):
            raise TypeError("item_id must be a string")
        with self._lock:
            return self._in_flight.pop(item_id, None) is not None

    def withdraw_pending(self, item_id: str) -> bool:
        """Remove explicitly cancelled pending ownership; never used silently."""

        if not isinstance(item_id, str):
            raise TypeError("item_id must be a string")
        with self._lock:
            removed = False
            kept: deque[BackpressureAdmission] = deque()
            while self._pending:
                current = self._pending.popleft()
                if not removed and current.item_id == item_id:
                    removed = True
                else:
                    kept.append(current)
            self._pending = kept
            return removed

    def pause(self) -> BackpressureControlResult:
        return self._control(BackpressureOperationKind.PAUSE)

    def resume(self) -> BackpressureControlResult:
        return self._control(BackpressureOperationKind.RESUME)

    def close(self) -> BackpressureSnapshot:
        """Reject new work while retaining accepted work until owner cleanup."""

        with self._lock:
            self._state = BackpressureState.CLOSED
            return self._snapshot_locked()

    def _control(
        self,
        kind: BackpressureOperationKind,
    ) -> BackpressureControlResult:
        if not self._capability.pause_resume_supported:
            raise RuntimeError("pause/resume is not supported")
        with self._lock:
            previous = self._state
            if self._state is BackpressureState.CLOSED:
                accepted = False
                code = BackpressureRejectionCode.CLOSED
            elif kind is BackpressureOperationKind.PAUSE:
                if self._state is BackpressureState.PAUSED:
                    accepted = False
                    code = BackpressureRejectionCode.ALREADY_PAUSED
                else:
                    accepted = True
                    code = BackpressureRejectionCode.NONE
                    self._state = BackpressureState.PAUSED
            else:
                if self._state is BackpressureState.ACCEPTING:
                    accepted = False
                    code = BackpressureRejectionCode.ALREADY_ACCEPTING
                else:
                    accepted = True
                    code = BackpressureRejectionCode.NONE
                    self._state = BackpressureState.ACCEPTING
            return BackpressureControlResult(
                kind=kind,
                boundary=self._capability.boundary,
                accepted=accepted,
                previous_state=previous,
                current_state=self._state,
                snapshot=self._snapshot_locked(),
                rejection_code=code,
                safe_message=(
                    "Backpressure admission state changed."
                    if accepted
                    else "Backpressure admission state was unchanged."
                ),
            )

    def _snapshot_locked(self) -> BackpressureSnapshot:
        return BackpressureSnapshot(
            boundary=self._capability.boundary,
            state=self._state,
            pending_count=len(self._pending),
            in_flight_count=len(self._in_flight),
            maximum_pending_count=self._capability.maximum_pending_count or 1,
            maximum_in_flight_count=(
                self._capability.maximum_in_flight_count or 1
            ),
            overflow_count=self._overflow_count,
        )

    def _rejected_locked(
        self,
        admission: BackpressureAdmission,
        *,
        code: BackpressureRejectionCode,
        safe_message: str,
        retryable: bool,
    ) -> BackpressureAdmissionResult:
        result = BackpressureAdmissionResult(
            accepted=False,
            admission=admission,
            snapshot=self._snapshot_locked(),
            rejection_code=code,
            safe_message=safe_message,
            retryable=retryable,
        )
        self._last_rejection = result
        return result

    def _require_unique_item_locked(self, item_id: str) -> None:
        if item_id in self._in_flight or any(
            admission.item_id == item_id for admission in self._pending
        ):
            raise ValueError("item_id is already owned by this runtime")

    def _deliver_overflow(self, event: BackpressureOverflowEvent) -> None:
        callback = self._on_overflow
        if callback is None:
            return
        try:
            callback(event)
        except Exception:
            # The typed admission rejection remains observable to the caller.
            return


__all__ = ("BoundedBackpressureRuntime",)
