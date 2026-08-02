"""Internal async VTube Studio transport protocol and in-memory fake.

FW-VTS-0c defines a provider-specific internal transport boundary for later
real pyvts composition. It does not import pyvts/WebSocket modules, inspect
environment or files, create a provider client, connect/authenticate, discover
models, resolve provider hotkey IDs, trigger a real hotkey, or execute motion.

These symbols are intentionally not exported from the ``framework`` root.
Host applications and DRC consume only the provider-neutral root-public
MotionSession contract after the later FW-VTS-0e composition checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Protocol, runtime_checkable
from uuid import uuid4

from .motion import MotionIntent


_SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)

_HOTKEY_FIRST_INTENTS = frozenset(
    {
        MotionIntent.EXPRESSION,
        MotionIntent.EMOTION,
        MotionIntent.GESTURE,
        MotionIntent.STOP_MOTION,
        MotionIntent.RESET_EXPRESSION,
    }
)


def _public_mapping(
    values: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if not values:
        return MappingProxyType({})

    safe: dict[str, Any] = {}
    for key, value in values.items():
        text_key = str(key)
        lowered = text_key.lower()
        safe[text_key] = (
            "<redacted>"
            if any(
                fragment in lowered
                for fragment in _SECRET_KEY_FRAGMENTS
            )
            else value
        )
    return MappingProxyType(safe)


def _normalize_hotkey_name(value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("hotkey_name must not be blank")
    return normalized


def _normalize_hotkey_names(
    values: Iterable[str] | None,
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for value in values or ():
        name = _normalize_hotkey_name(value)
        normalized[name.casefold()] = name
    return normalized


class VTubeStudioTransportOperation(str, Enum):
    """Bounded internal VTube Studio transport operations."""

    PREFLIGHT = "preflight"
    TRIGGER_HOTKEY = "trigger_hotkey"
    CLOSE = "close"


class VTubeStudioTransportOutcome(str, Enum):
    """Provider-safe internal transport outcomes."""

    READY = "ready"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not_found"
    BUSY = "busy"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class VTubeStudioHotkeyRequest:
    """Bounded internal hotkey request.

    The provider hotkey name is required for internal transport execution, but
    it is omitted from repr and public/result metadata. Provider hotkey IDs are
    not represented by this contract.
    """

    intent: MotionIntent | str
    hotkey_name: str = field(repr=False)
    request_id: str = field(default_factory=lambda: uuid4().hex)
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        intent = (
            self.intent
            if isinstance(self.intent, MotionIntent)
            else MotionIntent(str(self.intent))
        )
        if intent not in _HOTKEY_FIRST_INTENTS:
            raise ValueError(
                "VTube Studio hotkey request contains an unproven intent: "
                + intent.value
            )

        request_id = str(self.request_id).strip()
        if not request_id:
            raise ValueError("request_id must not be blank")

        object.__setattr__(self, "intent", intent)
        object.__setattr__(
            self,
            "hotkey_name",
            _normalize_hotkey_name(self.hotkey_name),
        )
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(
            self,
            "public_metadata",
            _public_mapping(self.public_metadata),
        )

    def to_public_dict(self) -> Mapping[str, Any]:
        return _public_mapping(
            {
                "request_id": self.request_id,
                "intent": self.intent.value,
                "hotkey_configured": True,
                "public_metadata": self.public_metadata,
            }
        )


@dataclass(frozen=True, slots=True)
class VTubeStudioTransportResult:
    """Provider-safe internal transport result."""

    operation: VTubeStudioTransportOperation | str
    outcome: VTubeStudioTransportOutcome | str
    request_id: str | None = None
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        operation = (
            self.operation
            if isinstance(self.operation, VTubeStudioTransportOperation)
            else VTubeStudioTransportOperation(str(self.operation))
        )
        outcome = (
            self.outcome
            if isinstance(self.outcome, VTubeStudioTransportOutcome)
            else VTubeStudioTransportOutcome(str(self.outcome))
        )
        request_id = (
            str(self.request_id).strip()
            if self.request_id is not None
            else None
        )
        if request_id == "":
            raise ValueError("request_id must not be blank when provided")

        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "safe_message", str(self.safe_message))
        object.__setattr__(self, "retryable", bool(self.retryable))
        object.__setattr__(
            self,
            "public_metadata",
            _public_mapping(self.public_metadata),
        )

    @property
    def is_success(self) -> bool:
        return self.outcome in {
            VTubeStudioTransportOutcome.READY,
            VTubeStudioTransportOutcome.COMPLETED,
        }

    @property
    def is_terminal(self) -> bool:
        return True


@runtime_checkable
class VTubeStudioTransport(Protocol):
    """Minimum injected async VTube Studio transport shape."""

    @property
    def transport_name(self) -> str:
        ...

    @property
    def is_closed(self) -> bool:
        ...

    async def preflight(self) -> VTubeStudioTransportResult:
        ...

    async def trigger_hotkey(
        self,
        request: VTubeStudioHotkeyRequest,
    ) -> VTubeStudioTransportResult:
        ...

    async def close(self) -> VTubeStudioTransportResult:
        ...


VTubeStudioTransportFactory = Callable[[], VTubeStudioTransport]


class FakeVTubeStudioTransport:
    """Deterministic in-memory transport for contract tests only."""

    def __init__(
        self,
        *,
        available_hotkeys: Iterable[str] | None = None,
        failing_hotkeys: Iterable[str] | None = None,
        available: bool = True,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        available_names = _normalize_hotkey_names(available_hotkeys)
        failing_names = _normalize_hotkey_names(failing_hotkeys)
        available_names.update(failing_names)

        self._available_hotkeys = available_names
        self._failing_hotkeys = frozenset(failing_names)
        self._available = bool(available)
        self._public_metadata = _public_mapping(public_metadata)
        self._closed = False
        self._preflight_call_count = 0
        self._trigger_call_count = 0
        self._close_call_count = 0
        self._received_requests: list[VTubeStudioHotkeyRequest] = []

    @property
    def transport_name(self) -> str:
        return "fake_vts"

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def preflight_call_count(self) -> int:
        return self._preflight_call_count

    @property
    def trigger_call_count(self) -> int:
        return self._trigger_call_count

    @property
    def close_call_count(self) -> int:
        return self._close_call_count

    @property
    def received_requests(
        self,
    ) -> tuple[VTubeStudioHotkeyRequest, ...]:
        return tuple(self._received_requests)

    def _metadata(
        self,
        *,
        reason: str,
        fake_protocol_call_executed: bool,
        hotkey_resolved: bool = False,
        already_closed: bool = False,
    ) -> Mapping[str, Any]:
        return _public_mapping(
            {
                **dict(self._public_metadata),
                "boundary": "vts_transport",
                "transport": self.transport_name,
                "fake_transport": True,
                "fake_protocol_call_executed": (
                    fake_protocol_call_executed
                ),
                "available_hotkey_count": len(
                    self._available_hotkeys
                ),
                "hotkey_resolved": hotkey_resolved,
                "already_closed": already_closed,
                "provider_sdk_imported": False,
                "provider_client_created": False,
                "network_executed": False,
                "authentication_material_accessed": False,
                "authentication_location_accessed": False,
                "model_location_accessed": False,
                "raw_payload_exposed": False,
                "hotkey_identifier_exposed": False,
                "hotkey_name_exposed": False,
                "real_hotkey_triggered": False,
                "real_motion_executed": False,
                "reason": reason,
            }
        )

    def _result(
        self,
        *,
        operation: VTubeStudioTransportOperation,
        outcome: VTubeStudioTransportOutcome,
        safe_message: str,
        request_id: str | None = None,
        retryable: bool = False,
        fake_protocol_call_executed: bool,
        hotkey_resolved: bool = False,
        already_closed: bool = False,
        reason: str,
    ) -> VTubeStudioTransportResult:
        return VTubeStudioTransportResult(
            operation=operation,
            outcome=outcome,
            request_id=request_id,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=self._metadata(
                reason=reason,
                fake_protocol_call_executed=(
                    fake_protocol_call_executed
                ),
                hotkey_resolved=hotkey_resolved,
                already_closed=already_closed,
            ),
        )

    async def preflight(self) -> VTubeStudioTransportResult:
        self._preflight_call_count += 1

        if self._closed:
            return self._result(
                operation=VTubeStudioTransportOperation.PREFLIGHT,
                outcome=VTubeStudioTransportOutcome.CLOSED,
                safe_message="The fake VTube Studio transport is closed.",
                fake_protocol_call_executed=True,
                reason="transport_closed",
            )

        if not self._available:
            return self._result(
                operation=VTubeStudioTransportOperation.PREFLIGHT,
                outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                safe_message=(
                    "The fake VTube Studio transport is unavailable."
                ),
                fake_protocol_call_executed=True,
                reason="fake_transport_unavailable",
            )

        return self._result(
            operation=VTubeStudioTransportOperation.PREFLIGHT,
            outcome=VTubeStudioTransportOutcome.READY,
            safe_message=(
                "The in-memory fake VTube Studio transport is ready."
            ),
            fake_protocol_call_executed=True,
            reason="fake_transport_ready",
        )

    async def trigger_hotkey(
        self,
        request: VTubeStudioHotkeyRequest,
    ) -> VTubeStudioTransportResult:
        if not isinstance(request, VTubeStudioHotkeyRequest):
            raise TypeError(
                "request must be VTubeStudioHotkeyRequest"
            )

        self._trigger_call_count += 1
        self._received_requests.append(request)

        if self._closed:
            return self._result(
                operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
                outcome=VTubeStudioTransportOutcome.CLOSED,
                request_id=request.request_id,
                safe_message="The fake VTube Studio transport is closed.",
                fake_protocol_call_executed=True,
                reason="transport_closed",
            )

        if not self._available:
            return self._result(
                operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
                outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                request_id=request.request_id,
                safe_message=(
                    "The fake VTube Studio transport is unavailable."
                ),
                fake_protocol_call_executed=True,
                reason="fake_transport_unavailable",
            )

        lookup_key = request.hotkey_name.casefold()
        if lookup_key not in self._available_hotkeys:
            return self._result(
                operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
                outcome=VTubeStudioTransportOutcome.NOT_FOUND,
                request_id=request.request_id,
                safe_message=(
                    "The requested fake VTube Studio hotkey was not found."
                ),
                fake_protocol_call_executed=True,
                reason="fake_hotkey_not_found",
            )

        if lookup_key in self._failing_hotkeys:
            return self._result(
                operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
                outcome=VTubeStudioTransportOutcome.FAILED,
                request_id=request.request_id,
                safe_message=(
                    "The configured fake VTube Studio hotkey failed."
                ),
                fake_protocol_call_executed=True,
                hotkey_resolved=True,
                reason="fake_hotkey_failed",
            )

        return self._result(
            operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
            outcome=VTubeStudioTransportOutcome.COMPLETED,
            request_id=request.request_id,
            safe_message=(
                "The in-memory fake VTube Studio hotkey call completed."
            ),
            fake_protocol_call_executed=True,
            hotkey_resolved=True,
            reason="fake_hotkey_completed",
        )

    async def close(self) -> VTubeStudioTransportResult:
        self._close_call_count += 1
        already_closed = self._closed
        self._closed = True
        return self._result(
            operation=VTubeStudioTransportOperation.CLOSE,
            outcome=VTubeStudioTransportOutcome.COMPLETED,
            safe_message=(
                "The in-memory fake VTube Studio transport is closed."
            ),
            fake_protocol_call_executed=True,
            already_closed=already_closed,
            reason=(
                "transport_already_closed"
                if already_closed
                else "transport_closed"
            ),
        )
