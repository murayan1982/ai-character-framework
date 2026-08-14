"""Provider-neutral public backpressure and flow-control contracts.

FW-RT6-12b Control A defines immutable, data-only vocabulary shared by audio
input, response-delta, voice-output, and event-subscriber boundaries. Importing
this explicit namespace does not create a queue, adopt a runtime boundary,
load a provider SDK, perform network work, access a device, or drop work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .public_safety import looks_like_private_path, public_mapping


BACKPRESSURE_API_VERSION = "6.0"


class BackpressureBoundary(str, Enum):
    """Framework boundary whose pending/in-flight work is flow-controlled."""

    AUDIO_INPUT = "audio_input"
    RESPONSE_DELTA = "response_delta"
    VOICE_OUTPUT = "voice_output"
    EVENT_SUBSCRIBER = "event_subscriber"


class BackpressureState(str, Enum):
    """Admission state independent from completion of already-owned work."""

    ACCEPTING = "accepting"
    PAUSED = "paused"
    CLOSED = "closed"


class BackpressureOverflowPolicy(str, Enum):
    """Explicit overflow policy accepted by the v6 public contract."""

    REJECT_NEWEST = "reject_newest"


class BackpressureOperationKind(str, Enum):
    """Kind of one public flow-control acknowledgement."""

    ADMIT = "admit"
    PAUSE = "pause"
    RESUME = "resume"


class BackpressureRejectionCode(str, Enum):
    """Provider-neutral reason that an admission/control operation failed."""

    NONE = "none"
    CAPACITY_REACHED = "capacity_reached"
    PAUSED = "paused"
    CLOSED = "closed"
    ALREADY_PAUSED = "already_paused"
    ALREADY_ACCEPTING = "already_accepting"


def _enum(value: object, enum_type: type[Enum], *, field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(str(value))
    except ValueError as error:
        raise ValueError(f"{field_name} is invalid") from error


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _positive_optional_int(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    normalized = _non_negative_int(value, field_name=field_name)
    if normalized < 1:
        raise ValueError(f"{field_name} must be at least 1")
    return normalized


def _identifier(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if len(normalized) > 128:
        raise ValueError(f"{field_name} must be at most 128 characters")
    if looks_like_private_path(normalized) or any(
        marker in normalized for marker in ("/", "\\", "://")
    ):
        raise ValueError(f"{field_name} must be opaque, not a path or URL")
    return normalized


def _safe_message(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("safe_message must be a string")
    normalized = value.strip()
    if looks_like_private_path(normalized):
        raise ValueError("safe_message must not contain a private path")
    return normalized


@dataclass(frozen=True, slots=True)
class BackpressureCapability:
    """Truthful capacity and overflow behavior for one boundary."""

    boundary: BackpressureBoundary | str
    supported: bool = False
    maximum_pending_count: int | None = None
    maximum_in_flight_count: int | None = None
    pause_resume_supported: bool = False
    retryable_rejection_supported: bool = False
    overflow_event_supported: bool = False
    overflow_policy: BackpressureOverflowPolicy | str = (
        BackpressureOverflowPolicy.REJECT_NEWEST
    )
    silent_drop: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        boundary = _enum(
            self.boundary,
            BackpressureBoundary,
            field_name="boundary",
        )
        policy = _enum(
            self.overflow_policy,
            BackpressureOverflowPolicy,
            field_name="overflow_policy",
        )
        for name in (
            "supported",
            "pause_resume_supported",
            "retryable_rejection_supported",
            "overflow_event_supported",
            "silent_drop",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a boolean")
        maximum_pending = _positive_optional_int(
            self.maximum_pending_count,
            field_name="maximum_pending_count",
        )
        maximum_in_flight = _positive_optional_int(
            self.maximum_in_flight_count,
            field_name="maximum_in_flight_count",
        )
        if self.silent_drop:
            raise ValueError("silent_drop is prohibited")
        if self.supported:
            if maximum_pending is None or maximum_in_flight is None:
                raise ValueError(
                    "supported backpressure requires pending and in-flight limits"
                )
            if not self.retryable_rejection_supported:
                raise ValueError(
                    "supported backpressure requires typed retryable rejection"
                )
            if not self.overflow_event_supported:
                raise ValueError(
                    "supported backpressure requires non-silent overflow events"
                )
        elif any(
            (
                maximum_pending is not None,
                maximum_in_flight is not None,
                self.pause_resume_supported,
                self.retryable_rejection_supported,
                self.overflow_event_supported,
            )
        ):
            raise ValueError(
                "unsupported backpressure must not advertise limits or features"
            )
        object.__setattr__(self, "boundary", boundary)
        object.__setattr__(self, "maximum_pending_count", maximum_pending)
        object.__setattr__(self, "maximum_in_flight_count", maximum_in_flight)
        object.__setattr__(self, "overflow_policy", policy)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "boundary": self.boundary.value,
                "supported": self.supported,
                "maximum_pending_count": self.maximum_pending_count,
                "maximum_in_flight_count": self.maximum_in_flight_count,
                "pause_resume_supported": self.pause_resume_supported,
                "retryable_rejection_supported": (
                    self.retryable_rejection_supported
                ),
                "overflow_event_supported": self.overflow_event_supported,
                "overflow_policy": self.overflow_policy.value,
                "silent_drop": self.silent_drop,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class BackpressureSnapshot:
    """Public-safe queue and in-flight counts at one observation point."""

    boundary: BackpressureBoundary | str
    state: BackpressureState | str
    pending_count: int
    in_flight_count: int
    maximum_pending_count: int
    maximum_in_flight_count: int
    overflow_count: int = 0

    def __post_init__(self) -> None:
        boundary = _enum(
            self.boundary,
            BackpressureBoundary,
            field_name="boundary",
        )
        state = _enum(self.state, BackpressureState, field_name="state")
        pending = _non_negative_int(self.pending_count, field_name="pending_count")
        in_flight = _non_negative_int(
            self.in_flight_count,
            field_name="in_flight_count",
        )
        maximum_pending = _positive_optional_int(
            self.maximum_pending_count,
            field_name="maximum_pending_count",
        )
        maximum_in_flight = _positive_optional_int(
            self.maximum_in_flight_count,
            field_name="maximum_in_flight_count",
        )
        overflow = _non_negative_int(
            self.overflow_count,
            field_name="overflow_count",
        )
        if maximum_pending is None or maximum_in_flight is None:
            raise AssertionError("snapshot maximum counts must be present")
        if pending > maximum_pending:
            raise ValueError("pending_count exceeds maximum_pending_count")
        if in_flight > maximum_in_flight:
            raise ValueError("in_flight_count exceeds maximum_in_flight_count")
        object.__setattr__(self, "boundary", boundary)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "pending_count", pending)
        object.__setattr__(self, "in_flight_count", in_flight)
        object.__setattr__(self, "maximum_pending_count", maximum_pending)
        object.__setattr__(self, "maximum_in_flight_count", maximum_in_flight)
        object.__setattr__(self, "overflow_count", overflow)

    @property
    def at_capacity(self) -> bool:
        return (
            self.pending_count == self.maximum_pending_count
            or self.in_flight_count == self.maximum_in_flight_count
        )

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "boundary": self.boundary.value,
                "state": self.state.value,
                "pending_count": self.pending_count,
                "in_flight_count": self.in_flight_count,
                "maximum_pending_count": self.maximum_pending_count,
                "maximum_in_flight_count": self.maximum_in_flight_count,
                "overflow_count": self.overflow_count,
                "at_capacity": self.at_capacity,
            }
        )


@dataclass(frozen=True, slots=True)
class BackpressureAdmission:
    """Opaque work identity submitted without retaining its payload."""

    boundary: BackpressureBoundary | str
    item_id: str
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "boundary",
            _enum(self.boundary, BackpressureBoundary, field_name="boundary"),
        )
        object.__setattr__(self, "item_id", _identifier(self.item_id, field_name="item_id"))
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "boundary": self.boundary.value,
                "item_id": self.item_id,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class BackpressureAdmissionResult:
    """Typed accepted/rejected result; rejection never implies silent loss."""

    accepted: bool
    admission: BackpressureAdmission
    snapshot: BackpressureSnapshot
    rejection_code: BackpressureRejectionCode | str = BackpressureRejectionCode.NONE
    safe_message: str = ""
    retryable: bool = False
    dropped: bool = False
    kind: BackpressureOperationKind = field(
        init=False,
        default=BackpressureOperationKind.ADMIT,
    )

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be a boolean")
        if not isinstance(self.admission, BackpressureAdmission):
            raise TypeError("admission must be a BackpressureAdmission")
        if not isinstance(self.snapshot, BackpressureSnapshot):
            raise TypeError("snapshot must be a BackpressureSnapshot")
        code = _enum(
            self.rejection_code,
            BackpressureRejectionCode,
            field_name="rejection_code",
        )
        if type(self.retryable) is not bool:
            raise TypeError("retryable must be a boolean")
        if type(self.dropped) is not bool:
            raise TypeError("dropped must be a boolean")
        if self.dropped:
            raise ValueError("backpressure admission must never report silent drop")
        if self.admission.boundary is not self.snapshot.boundary:
            raise ValueError("admission and snapshot boundary must match")
        if self.accepted:
            if code is not BackpressureRejectionCode.NONE:
                raise ValueError("accepted admission must use rejection_code=none")
            if self.retryable:
                raise ValueError("accepted admission cannot be retryable")
            if self.snapshot.state is not BackpressureState.ACCEPTING:
                raise ValueError("accepted admission requires accepting state")
        else:
            if code is BackpressureRejectionCode.NONE:
                raise ValueError("rejected admission requires a rejection code")
            if code is BackpressureRejectionCode.CAPACITY_REACHED:
                if not self.snapshot.at_capacity or not self.retryable:
                    raise ValueError("capacity rejection must be full and retryable")
            elif code is BackpressureRejectionCode.PAUSED:
                if self.snapshot.state is not BackpressureState.PAUSED or not self.retryable:
                    raise ValueError("paused rejection must be paused and retryable")
            elif code is BackpressureRejectionCode.CLOSED:
                if self.snapshot.state is not BackpressureState.CLOSED or self.retryable:
                    raise ValueError("closed rejection must be terminal and non-retryable")
            else:
                raise ValueError("control-state rejection code is invalid for admission")
        object.__setattr__(self, "rejection_code", code)
        object.__setattr__(self, "safe_message", _safe_message(self.safe_message))

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "kind": self.kind.value,
                "accepted": self.accepted,
                "admission": dict(self.admission.as_dict()),
                "snapshot": dict(self.snapshot.as_dict()),
                "rejection_code": self.rejection_code.value,
                "safe_message": self.safe_message,
                "retryable": self.retryable,
                "dropped": self.dropped,
            }
        )


@dataclass(frozen=True, slots=True)
class BackpressureOverflowEvent:
    """Non-silent diagnostic paired with a capacity-rejected admission."""

    admission: BackpressureAdmission
    snapshot: BackpressureSnapshot
    safe_message: str = "Backpressure capacity was reached."
    retryable: bool = True
    dropped: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.admission, BackpressureAdmission):
            raise TypeError("admission must be a BackpressureAdmission")
        if not isinstance(self.snapshot, BackpressureSnapshot):
            raise TypeError("snapshot must be a BackpressureSnapshot")
        if self.admission.boundary is not self.snapshot.boundary:
            raise ValueError("admission and snapshot boundary must match")
        if not self.snapshot.at_capacity:
            raise ValueError("overflow event requires an at-capacity snapshot")
        if type(self.retryable) is not bool or not self.retryable:
            raise ValueError("overflow event must be retryable")
        if type(self.dropped) is not bool:
            raise TypeError("dropped must be a boolean")
        if self.dropped:
            raise ValueError("overflow event must not claim silent drop")
        object.__setattr__(self, "safe_message", _safe_message(self.safe_message))
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    @property
    def boundary(self) -> BackpressureBoundary:
        return self.admission.boundary

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "boundary": self.boundary.value,
                "admission": dict(self.admission.as_dict()),
                "snapshot": dict(self.snapshot.as_dict()),
                "rejection_code": BackpressureRejectionCode.CAPACITY_REACHED.value,
                "safe_message": self.safe_message,
                "retryable": self.retryable,
                "dropped": self.dropped,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class BackpressureControlResult:
    """Typed pause/resume acknowledgement without cancelling owned work."""

    kind: BackpressureOperationKind | str
    boundary: BackpressureBoundary | str
    accepted: bool
    previous_state: BackpressureState | str
    current_state: BackpressureState | str
    snapshot: BackpressureSnapshot
    rejection_code: BackpressureRejectionCode | str = BackpressureRejectionCode.NONE
    safe_message: str = ""
    cancelled_count: int = 0
    dropped: bool = False

    def __post_init__(self) -> None:
        kind = _enum(self.kind, BackpressureOperationKind, field_name="kind")
        boundary = _enum(self.boundary, BackpressureBoundary, field_name="boundary")
        previous = _enum(
            self.previous_state,
            BackpressureState,
            field_name="previous_state",
        )
        current = _enum(
            self.current_state,
            BackpressureState,
            field_name="current_state",
        )
        code = _enum(
            self.rejection_code,
            BackpressureRejectionCode,
            field_name="rejection_code",
        )
        if kind not in (BackpressureOperationKind.PAUSE, BackpressureOperationKind.RESUME):
            raise ValueError("control result kind must be pause or resume")
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be a boolean")
        if not isinstance(self.snapshot, BackpressureSnapshot):
            raise TypeError("snapshot must be a BackpressureSnapshot")
        if self.snapshot.boundary is not boundary or self.snapshot.state is not current:
            raise ValueError("control result snapshot does not match boundary/state")
        cancelled = _non_negative_int(
            self.cancelled_count,
            field_name="cancelled_count",
        )
        if cancelled:
            raise ValueError("pause/resume must not claim cancellation")
        if type(self.dropped) is not bool:
            raise TypeError("dropped must be a boolean")
        if self.dropped:
            raise ValueError("pause/resume must not drop work")
        if self.accepted:
            if code is not BackpressureRejectionCode.NONE:
                raise ValueError("accepted control result must use rejection_code=none")
            expected = (
                (BackpressureState.ACCEPTING, BackpressureState.PAUSED)
                if kind is BackpressureOperationKind.PAUSE
                else (BackpressureState.PAUSED, BackpressureState.ACCEPTING)
            )
            if (previous, current) != expected:
                raise ValueError("accepted pause/resume transition is invalid")
        else:
            expected_code = (
                BackpressureRejectionCode.ALREADY_PAUSED
                if kind is BackpressureOperationKind.PAUSE
                and current is BackpressureState.PAUSED
                else BackpressureRejectionCode.ALREADY_ACCEPTING
                if kind is BackpressureOperationKind.RESUME
                and current is BackpressureState.ACCEPTING
                else BackpressureRejectionCode.CLOSED
                if current is BackpressureState.CLOSED
                else None
            )
            if code is not expected_code:
                raise ValueError("rejected pause/resume state/code mismatch")
            if previous is not current:
                raise ValueError("rejected pause/resume must not change state")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "boundary", boundary)
        object.__setattr__(self, "previous_state", previous)
        object.__setattr__(self, "current_state", current)
        object.__setattr__(self, "rejection_code", code)
        object.__setattr__(self, "safe_message", _safe_message(self.safe_message))
        object.__setattr__(self, "cancelled_count", cancelled)

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "kind": self.kind.value,
                "boundary": self.boundary.value,
                "accepted": self.accepted,
                "previous_state": self.previous_state.value,
                "current_state": self.current_state.value,
                "snapshot": dict(self.snapshot.as_dict()),
                "rejection_code": self.rejection_code.value,
                "safe_message": self.safe_message,
                "cancelled_count": self.cancelled_count,
                "dropped": self.dropped,
            }
        )


__all__ = (
    "BACKPRESSURE_API_VERSION",
    "BackpressureBoundary",
    "BackpressureState",
    "BackpressureOverflowPolicy",
    "BackpressureOperationKind",
    "BackpressureRejectionCode",
    "BackpressureCapability",
    "BackpressureSnapshot",
    "BackpressureAdmission",
    "BackpressureAdmissionResult",
    "BackpressureOverflowEvent",
    "BackpressureControlResult",
)
