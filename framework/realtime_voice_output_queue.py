"""Provider-neutral bounded pending voice-synthesis queue contracts for v6.

FW-RT6-6c Control A defines Framework-owned pending-work identity, bounded
admission, typed enqueue/clear results, and non-silent overflow notification.
Control B composes the non-stable concrete queue with the non-stable concrete
synthesis stage while the stable queue protocol remains pending-only. The
module does not cancel active generation, invalidate artifacts, perform host
playback, import provider SDKs, access the network directly, use a microphone,
or connect to VTube Studio.

The module is an explicitly stable package as
``framework.realtime_voice_output_queue`` but is not re-exported by the
``framework`` root.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import threading
from typing import Callable, Mapping, Protocol, runtime_checkable

from .audio.voice_output import VoiceOutputRequest
from .backpressure import (
    BackpressureAdmissionResult,
    BackpressureBoundary,
    BackpressureCapability,
    BackpressureControlResult,
    BackpressureRejectionCode,
    BackpressureSnapshot,
)
from .backpressure_runtime import BoundedBackpressureRuntime
from .identity import GenerationId, SessionId, TurnId
from .public_safety import public_mapping, sanitize_public_value
from .realtime_stage import RealtimeStageContext
from .realtime_voice_output import (
    ProviderNeutralVoiceSynthesisStage,
    SynthesisWorkId,
    VoiceSynthesisResultEnvelope,
)


def _non_negative_int(value: int, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _positive_int(value: int, *, field_name: str) -> int:
    normalized = _non_negative_int(value, field_name=field_name)
    if normalized < 1:
        raise ValueError(f"{field_name} must be at least 1")
    return normalized


def _safe_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = sanitize_public_value(value)
    if not isinstance(normalized, str):
        raise TypeError(f"{field_name} must normalize to public-safe text")
    return normalized


@dataclass(frozen=True, slots=True)
class VoiceSynthesisPendingWork:
    """Public-safe identity snapshot for one pending synthesis item.

    Request text and provider/runtime objects are intentionally absent.
    """

    context: RealtimeStageContext
    work_id: SynthesisWorkId | str

    def __post_init__(self) -> None:
        if not isinstance(self.context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        work_id = (
            self.work_id
            if isinstance(self.work_id, SynthesisWorkId)
            else SynthesisWorkId.parse(self.work_id)
        )
        object.__setattr__(self, "work_id", work_id)

    @property
    def session_id(self) -> SessionId | str:
        return self.context.session_id

    @property
    def turn_id(self) -> TurnId | str:
        return self.context.turn_id

    @property
    def generation_id(self) -> GenerationId:
        return self.context.generation_id


class VoiceSynthesisEnqueueOutcome(str, Enum):
    """Typed admission result for one pending synthesis request."""

    ACCEPTED = "accepted"
    REJECTED_FULL = "rejected_full"
    REJECTED_PAUSED = "rejected_paused"
    REJECTED_CLOSED = "rejected_closed"


@dataclass(frozen=True, slots=True)
class VoiceSynthesisEnqueueResult:
    """Public-safe bounded-queue admission result."""

    outcome: VoiceSynthesisEnqueueOutcome | str
    work: VoiceSynthesisPendingWork
    pending_count: int
    max_pending_depth: int
    safe_message: str = ""
    public_metadata: Mapping[str, object] = field(default_factory=dict)
    backpressure_result: BackpressureAdmissionResult | None = field(
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, VoiceSynthesisEnqueueOutcome)
            else VoiceSynthesisEnqueueOutcome(str(self.outcome))
        )
        if not isinstance(self.work, VoiceSynthesisPendingWork):
            raise TypeError("work must be VoiceSynthesisPendingWork")
        pending_count = _non_negative_int(
            self.pending_count,
            field_name="pending_count",
        )
        max_pending_depth = _positive_int(
            self.max_pending_depth,
            field_name="max_pending_depth",
        )
        if pending_count > max_pending_depth:
            raise ValueError("pending_count must not exceed max_pending_depth")
        if outcome is VoiceSynthesisEnqueueOutcome.ACCEPTED and pending_count < 1:
            raise ValueError("accepted enqueue must report at least one pending item")
        if (
            outcome is VoiceSynthesisEnqueueOutcome.REJECTED_FULL
            and pending_count != max_pending_depth
        ):
            raise ValueError("rejected_full enqueue requires a full pending queue")
        if self.backpressure_result is not None:
            if not isinstance(
                self.backpressure_result,
                BackpressureAdmissionResult,
            ):
                raise TypeError(
                    "backpressure_result must be BackpressureAdmissionResult or None"
                )
            if self.backpressure_result.accepted is not (
                outcome is VoiceSynthesisEnqueueOutcome.ACCEPTED
            ):
                raise ValueError("enqueue and backpressure acceptance must agree")
            if self.backpressure_result.admission.item_id != str(self.work.work_id):
                raise ValueError("enqueue and backpressure work identity must agree")
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "pending_count", pending_count)
        object.__setattr__(self, "max_pending_depth", max_pending_depth)
        object.__setattr__(
            self,
            "safe_message",
            _safe_text(self.safe_message, field_name="safe_message"),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def accepted(self) -> bool:
        return self.outcome is VoiceSynthesisEnqueueOutcome.ACCEPTED

    @property
    def retryable(self) -> bool:
        if self.backpressure_result is not None:
            return self.backpressure_result.retryable
        return self.outcome in (
            VoiceSynthesisEnqueueOutcome.REJECTED_FULL,
            VoiceSynthesisEnqueueOutcome.REJECTED_PAUSED,
        )

    @property
    def dropped(self) -> bool:
        return False


class VoiceSynthesisPendingClearOutcome(str, Enum):
    """Typed result for a pending-only queue clear."""

    CLEARED = "cleared"
    NOTHING_CLEARED = "nothing_cleared"


@dataclass(frozen=True, slots=True)
class VoiceSynthesisPendingClearResult:
    """Public-safe result for clearing pending work without active cancellation."""

    outcome: VoiceSynthesisPendingClearOutcome | str
    cleared_work: tuple[VoiceSynthesisPendingWork, ...] = ()
    pending_count: int = 0
    max_pending_depth: int = 1
    active_generation_cancelled: bool = False
    safe_message: str = ""
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, VoiceSynthesisPendingClearOutcome)
            else VoiceSynthesisPendingClearOutcome(str(self.outcome))
        )
        if not isinstance(self.cleared_work, tuple) or not all(
            isinstance(item, VoiceSynthesisPendingWork)
            for item in self.cleared_work
        ):
            raise TypeError(
                "cleared_work must be a tuple of VoiceSynthesisPendingWork"
            )
        pending_count = _non_negative_int(
            self.pending_count,
            field_name="pending_count",
        )
        max_pending_depth = _positive_int(
            self.max_pending_depth,
            field_name="max_pending_depth",
        )
        if pending_count > max_pending_depth:
            raise ValueError("pending_count must not exceed max_pending_depth")
        if type(self.active_generation_cancelled) is not bool:
            raise TypeError("active_generation_cancelled must be a boolean")
        if self.active_generation_cancelled:
            raise ValueError(
                "pending clear must never claim active generation cancellation"
            )
        if outcome is VoiceSynthesisPendingClearOutcome.CLEARED:
            if not self.cleared_work:
                raise ValueError("cleared outcome requires at least one cleared item")
        elif self.cleared_work:
            raise ValueError("nothing_cleared outcome must not report cleared work")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "pending_count", pending_count)
        object.__setattr__(self, "max_pending_depth", max_pending_depth)
        object.__setattr__(
            self,
            "safe_message",
            _safe_text(self.safe_message, field_name="safe_message"),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def cleared_count(self) -> int:
        return len(self.cleared_work)


class VoiceSynthesisQueueEventType(str, Enum):
    """Provider-neutral pending-queue diagnostic event type."""

    OVERFLOW = "overflow"


@dataclass(frozen=True, slots=True)
class VoiceSynthesisQueueEvent:
    """Public-safe component event for non-silent queue overflow."""

    type: VoiceSynthesisQueueEventType | str
    work: VoiceSynthesisPendingWork
    pending_count: int
    max_pending_depth: int
    overflow_count: int
    safe_message: str = ""
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_type = (
            self.type
            if isinstance(self.type, VoiceSynthesisQueueEventType)
            else VoiceSynthesisQueueEventType(str(self.type))
        )
        if not isinstance(self.work, VoiceSynthesisPendingWork):
            raise TypeError("work must be VoiceSynthesisPendingWork")
        pending_count = _non_negative_int(
            self.pending_count,
            field_name="pending_count",
        )
        max_pending_depth = _positive_int(
            self.max_pending_depth,
            field_name="max_pending_depth",
        )
        overflow_count = _positive_int(
            self.overflow_count,
            field_name="overflow_count",
        )
        if pending_count != max_pending_depth:
            raise ValueError("overflow event requires a full pending queue")
        object.__setattr__(self, "type", event_type)
        object.__setattr__(self, "pending_count", pending_count)
        object.__setattr__(self, "max_pending_depth", max_pending_depth)
        object.__setattr__(self, "overflow_count", overflow_count)
        object.__setattr__(
            self,
            "safe_message",
            _safe_text(self.safe_message, field_name="safe_message"),
        )
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )


VoiceSynthesisQueueEventCallback = Callable[[VoiceSynthesisQueueEvent], None]


@runtime_checkable
class VoiceSynthesisPendingQueue(Protocol):
    """Stable pending-only queue contract.

    This protocol deliberately does not expose an active-generation property and
    does not define synthesis execution or cancellation.
    """

    @property
    def max_pending_depth(self) -> int:
        ...

    @property
    def pending_count(self) -> int:
        ...

    @property
    def pending_work(self) -> tuple[VoiceSynthesisPendingWork, ...]:
        ...

    @property
    def overflow_count(self) -> int:
        ...

    def enqueue(
        self,
        *,
        context: RealtimeStageContext,
        request: VoiceOutputRequest,
    ) -> VoiceSynthesisEnqueueResult:
        ...

    def clear_pending(
        self,
        *,
        context: RealtimeStageContext | None = None,
    ) -> VoiceSynthesisPendingClearResult:
        ...


@dataclass(slots=True)
class _PendingVoiceSynthesisEntry:
    work: VoiceSynthesisPendingWork
    request: VoiceOutputRequest = field(repr=False)


class BoundedVoiceSynthesisPendingQueue:
    """Framework reference implementation of the bounded pending queue.

    The concrete implementation is intentionally omitted from ``__all__``.
    Control B adds a reference-only pending-to-active handoff while the stable
    pending protocol remains unchanged.
    """

    __slots__ = (
        "_max_pending_depth",
        "_on_event",
        "_lock",
        "_pending",
        "_overflow_count",
        "_backpressure",
    )

    def __init__(
        self,
        *,
        max_pending_depth: int,
        on_event: VoiceSynthesisQueueEventCallback | None = None,
    ) -> None:
        self._max_pending_depth = _positive_int(
            max_pending_depth,
            field_name="max_pending_depth",
        )
        if on_event is not None and not callable(on_event):
            raise TypeError("on_event must be callable or None")
        self._on_event = on_event
        self._lock = threading.RLock()
        self._pending: deque[_PendingVoiceSynthesisEntry] = deque()
        self._overflow_count = 0
        self._backpressure = BoundedBackpressureRuntime(
            boundary=BackpressureBoundary.VOICE_OUTPUT,
            maximum_pending_count=self._max_pending_depth,
            maximum_in_flight_count=1,
            public_metadata={
                "owner": "BoundedVoiceSynthesisPendingQueue",
                "payload_retained": False,
            },
        )

    @property
    def max_pending_depth(self) -> int:
        return self._max_pending_depth

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def pending_work(self) -> tuple[VoiceSynthesisPendingWork, ...]:
        with self._lock:
            return tuple(entry.work for entry in self._pending)

    @property
    def overflow_count(self) -> int:
        with self._lock:
            return self._overflow_count

    @property
    def backpressure_capability(self) -> BackpressureCapability:
        return self._backpressure.capability

    @property
    def backpressure_snapshot(self) -> BackpressureSnapshot:
        return self._backpressure.snapshot

    @property
    def last_backpressure_result(self) -> BackpressureAdmissionResult | None:
        return self._backpressure.last_rejection

    def pause(self) -> BackpressureControlResult:
        return self._backpressure.pause()

    def resume(self) -> BackpressureControlResult:
        return self._backpressure.resume()

    def close(self) -> BackpressureSnapshot:
        """Close new admission while retaining explicitly accepted pending work."""

        return self._backpressure.close()

    def enqueue(
        self,
        *,
        context: RealtimeStageContext,
        request: VoiceOutputRequest,
    ) -> VoiceSynthesisEnqueueResult:
        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(request, VoiceOutputRequest):
            raise TypeError("request must be a VoiceOutputRequest")

        work = VoiceSynthesisPendingWork(
            context=context,
            work_id=SynthesisWorkId.new(),
        )
        overflow_event: VoiceSynthesisQueueEvent | None = None
        with self._lock:
            backpressure_result = self._backpressure.admit_item(
                str(work.work_id),
                public_metadata={
                    "session_id": str(work.session_id),
                    "turn_id": str(work.turn_id),
                    "generation_id": str(work.generation_id),
                },
            )
            if not backpressure_result.accepted:
                rejection_code = backpressure_result.rejection_code
                if rejection_code is BackpressureRejectionCode.CAPACITY_REACHED:
                    outcome = VoiceSynthesisEnqueueOutcome.REJECTED_FULL
                    reason = "bounded_pending_capacity"
                    message = (
                        "Voice synthesis work was rejected because the pending "
                        "queue is full."
                    )
                elif rejection_code is BackpressureRejectionCode.PAUSED:
                    outcome = VoiceSynthesisEnqueueOutcome.REJECTED_PAUSED
                    reason = "admission_paused"
                    message = "Voice synthesis work was rejected while admission is paused."
                elif rejection_code is BackpressureRejectionCode.CLOSED:
                    outcome = VoiceSynthesisEnqueueOutcome.REJECTED_CLOSED
                    reason = "admission_closed"
                    message = "Voice synthesis work was rejected because admission is closed."
                else:  # pragma: no cover - controller has an exact rejection set
                    raise AssertionError("unexpected voice-output rejection")

                if outcome is VoiceSynthesisEnqueueOutcome.REJECTED_FULL:
                    self._overflow_count += 1
                    overflow_event = VoiceSynthesisQueueEvent(
                        type=VoiceSynthesisQueueEventType.OVERFLOW,
                        work=work,
                        pending_count=len(self._pending),
                        max_pending_depth=self._max_pending_depth,
                        overflow_count=self._overflow_count,
                        safe_message="Voice synthesis pending queue is full.",
                        public_metadata={
                            "boundary": "voice_synthesis_pending_queue",
                            "reason": reason,
                        },
                    )
                result = VoiceSynthesisEnqueueResult(
                    outcome=outcome,
                    work=work,
                    pending_count=len(self._pending),
                    max_pending_depth=self._max_pending_depth,
                    safe_message=message,
                    public_metadata={
                        "boundary": BackpressureBoundary.VOICE_OUTPUT.value,
                        "reason": reason,
                    },
                    backpressure_result=backpressure_result,
                )
            else:
                self._pending.append(
                    _PendingVoiceSynthesisEntry(
                        work=work,
                        request=request,
                    )
                )
                result = VoiceSynthesisEnqueueResult(
                    outcome=VoiceSynthesisEnqueueOutcome.ACCEPTED,
                    work=work,
                    pending_count=len(self._pending),
                    max_pending_depth=self._max_pending_depth,
                    safe_message="Voice synthesis work was accepted into the pending queue.",
                    public_metadata={
                        "boundary": BackpressureBoundary.VOICE_OUTPUT.value,
                        "reason": "accepted",
                    },
                    backpressure_result=backpressure_result,
                )

        if overflow_event is not None:
            self._deliver_event(overflow_event)
        return result

    def clear_pending(
        self,
        *,
        context: RealtimeStageContext | None = None,
    ) -> VoiceSynthesisPendingClearResult:
        if context is not None and not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext or None")

        with self._lock:
            if context is None:
                cleared_entries = tuple(self._pending)
                self._pending.clear()
            else:
                kept: deque[_PendingVoiceSynthesisEntry] = deque()
                cleared: list[_PendingVoiceSynthesisEntry] = []
                while self._pending:
                    entry = self._pending.popleft()
                    if entry.work.context == context:
                        cleared.append(entry)
                    else:
                        kept.append(entry)
                self._pending = kept
                cleared_entries = tuple(cleared)

            cleared_work = tuple(entry.work for entry in cleared_entries)
            for work in cleared_work:
                if not self._backpressure.withdraw_pending(str(work.work_id)):
                    raise AssertionError("cleared voice work lost pending ownership")
            pending_count = len(self._pending)

        if cleared_work:
            return VoiceSynthesisPendingClearResult(
                outcome=VoiceSynthesisPendingClearOutcome.CLEARED,
                cleared_work=cleared_work,
                pending_count=pending_count,
                max_pending_depth=self._max_pending_depth,
                active_generation_cancelled=False,
                safe_message="Pending voice synthesis work was cleared.",
                public_metadata={
                    "boundary": "voice_synthesis_pending_queue",
                    "reason": "pending_cleared",
                },
            )
        return VoiceSynthesisPendingClearResult(
            outcome=VoiceSynthesisPendingClearOutcome.NOTHING_CLEARED,
            cleared_work=(),
            pending_count=pending_count,
            max_pending_depth=self._max_pending_depth,
            active_generation_cancelled=False,
            safe_message="No matching pending voice synthesis work was queued.",
            public_metadata={
                "boundary": "voice_synthesis_pending_queue",
                "reason": "nothing_cleared",
            },
        )

    def handoff_next(
        self,
        *,
        stage: ProviderNeutralVoiceSynthesisStage,
    ) -> VoiceSynthesisResultEnvelope | None:
        """Move the oldest pending item into the concrete active stage boundary.

        This reference-only composition helper is intentionally absent from the
        stable ``VoiceSynthesisPendingQueue`` protocol. The pending item is removed
        only after the stage has successfully claimed the exact enqueue-time
        ``SynthesisWorkId``. A closed or already-active stage therefore leaves the
        FIFO unchanged. Provider execution happens after the queue lock is released.
        """

        if not isinstance(stage, ProviderNeutralVoiceSynthesisStage):
            raise TypeError("stage must be ProviderNeutralVoiceSynthesisStage")

        with self._lock:
            if not self._pending:
                return None
            entry = self._pending[0]
            active = stage._claim_generation(
                context=entry.work.context,
                work_id=entry.work.work_id,
            )
            admission = self._backpressure.claim(str(entry.work.work_id))
            if admission is None:
                stage._release_generation(active.work_id)
                return None
            claimed = self._pending.popleft()
            if claimed is not entry:  # pragma: no cover - protected by queue lock
                stage._release_generation(active.work_id)
                self._backpressure.complete(str(entry.work.work_id))
                raise RuntimeError("pending voice synthesis FIFO claim drift")

        try:
            return stage._run_claimed(active=active, request=entry.request)
        finally:
            if not self._backpressure.complete(str(entry.work.work_id)):
                raise AssertionError("voice-output in-flight ownership was lost")

    def _deliver_event(self, event: VoiceSynthesisQueueEvent) -> None:
        callback = self._on_event
        if callback is None:
            return
        try:
            callback(event)
        except Exception:
            # Queue admission remains deterministic even when a host diagnostic
            # callback fails. The typed rejected result still makes overflow
            # non-silent to the caller.
            return


__all__ = [
    "VoiceSynthesisPendingWork",
    "VoiceSynthesisEnqueueOutcome",
    "VoiceSynthesisEnqueueResult",
    "VoiceSynthesisPendingClearOutcome",
    "VoiceSynthesisPendingClearResult",
    "VoiceSynthesisQueueEventType",
    "VoiceSynthesisQueueEvent",
    "VoiceSynthesisPendingQueue",
]
