"""Public motion session skeleton.

This module provides a mock-safe public motion / Live2D / VTS adapter boundary.
It intentionally does not connect to VTube Studio, load Live2D runtime, read
token files, open websockets, access private model paths, or import provider SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from .motion import (
    MotionAdapterStatus,
    MotionCapability,
    MotionErrorCode,
    MotionEventType,
    MotionIntent,
    MotionOutcome,
    MotionRequest,
    MotionResult,
    MotionState,
    _public_mapping,
)


MotionEventCallback = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class MotionSessionInfo:
    """App-safe metadata for a public motion session."""

    api_version: str = "5.2.0"
    session_type: str = "motion"
    session_id: str = field(default_factory=lambda: uuid4().hex)
    adapter: str = "mock"
    adapter_status: MotionAdapterStatus | str = MotionAdapterStatus.MOCK_AVAILABLE
    state: MotionState | str = MotionState.IDLE
    capability: MotionCapability = field(default_factory=MotionCapability.mock_available)
    supports_events: bool = True
    supports_apply_motion: bool = True
    supports_expression: bool = True
    supports_emotion: bool = True
    supports_speaking_state: bool = True
    supports_gesture: bool = True
    supports_look_at: bool = True
    supports_stop_motion: bool = True
    supports_close: bool = True
    real_adapter_enabled: bool = False
    real_adapter_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = (
            self.adapter_status
            if isinstance(self.adapter_status, MotionAdapterStatus)
            else MotionAdapterStatus(str(self.adapter_status))
        )
        state = self.state if isinstance(self.state, MotionState) else MotionState(str(self.state))
        object.__setattr__(self, "adapter_status", status)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


class MotionSession:
    """Mock-safe public motion adapter session skeleton."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        adapter: str = "mock",
        real_adapter_enabled: bool | None = None,
        allow_provider_execution: bool | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._session_id = uuid4().hex
        self._adapter = adapter or "mock"
        self._real_adapter_enabled = bool(real_adapter_enabled)
        self._allow_provider_execution = bool(allow_provider_execution)
        self._closed = False
        self._state = MotionState.IDLE
        self._callbacks: list[MotionEventCallback] = []
        self._public_metadata = _public_mapping(public_metadata)
        self._capability = self._resolve_capability()

    def _resolve_capability(self) -> MotionCapability:
        adapter = self._adapter.lower()

        if adapter in {"", "disabled", "none"}:
            return MotionCapability.disabled(adapter=self._adapter)

        if adapter == "mock" and not self._real_adapter_enabled:
            return MotionCapability.mock_available()

        if self._real_adapter_enabled and not self._allow_provider_execution:
            return MotionCapability(
                adapter=self._adapter,
                adapter_status=MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
                safe_message="Motion adapter provider execution is not allowed.",
                public_metadata={"boundary": "motion", "reason": "provider_execution_not_allowed"},
            )

        if adapter not in {"mock", "live2d", "vts", "vtube_studio"}:
            return MotionCapability(
                adapter=self._adapter,
                adapter_status=MotionAdapterStatus.UNSUPPORTED_ADAPTER,
                safe_message="Motion adapter is unsupported.",
                public_metadata={"boundary": "motion", "reason": "unsupported_adapter"},
            )

        return MotionCapability(
            adapter=self._adapter,
            adapter_status=MotionAdapterStatus.NOT_IMPLEMENTED,
            safe_message="Real motion adapter is not implemented yet.",
            public_metadata={"boundary": "motion", "reason": "not_implemented"},
        )

    @property
    def info(self) -> MotionSessionInfo:
        capability = self._capability
        return MotionSessionInfo(
            session_id=self._session_id,
            adapter=self._adapter,
            adapter_status=MotionAdapterStatus.CLOSED if self._closed else capability.adapter_status,
            state=self._state,
            capability=capability,
            supports_expression=capability.supports_expression,
            supports_emotion=capability.supports_emotion,
            supports_speaking_state=capability.supports_speaking_state,
            supports_gesture=capability.supports_gesture,
            supports_look_at=capability.supports_look_at,
            supports_stop_motion=capability.supports_stop_motion,
            real_adapter_enabled=self._real_adapter_enabled,
            real_adapter_supported=capability.supports_real_adapter,
            public_metadata={
                "boundary": "motion",
                **dict(self._public_metadata),
            },
        )

    @property
    def capability(self) -> MotionCapability:
        return self._capability

    @property
    def state(self) -> MotionState:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._closed

    def on_event(self, callback: MotionEventCallback) -> None:
        """Register a public motion event callback.

        Callbacks receive immutable public-safe mapping payloads.
        """

        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callbacks.append(callback)

    def _emit(
        self,
        event_type: MotionEventType,
        *,
        request: MotionRequest | None = None,
        result: MotionResult | None = None,
        state: MotionState | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        payload = _public_mapping(
            {
                "type": event_type.value,
                "session_id": self._session_id,
                "request_id": request.request_id if request else result.request_id if result else None,
                "state": (state or self._state).value,
                "adapter": self._adapter,
                "adapter_status": (result.adapter_status if result else self.info.adapter_status).value,
                "outcome": result.outcome.value if result else None,
                "public_error_code": result.public_error_code.value if result else MotionErrorCode.NONE.value,
                "safe_message": result.safe_message if result else "",
                "retryable": result.retryable if result else False,
                "public_metadata": _public_mapping(
                    {
                        "boundary": "motion",
                        **dict(public_metadata or {}),
                    }
                ),
            }
        )
        for callback in list(self._callbacks):
            callback(payload)
        return payload

    def emit_created(self) -> Mapping[str, Any]:
        """Emit a public motion session-created event."""

        return self._emit(MotionEventType.SESSION_CREATED, state=self._state)

    def preflight(self) -> MotionCapability:
        """Return the public motion adapter capability snapshot."""

        self._emit(
            MotionEventType.ADAPTER_PREFLIGHT_COMPLETED,
            public_metadata={"adapter_status": self._capability.adapter_status.value},
        )
        return self._capability

    def apply_motion(self, request: MotionRequest) -> MotionResult:
        """Apply a mock-safe public motion request.

        This skeleton performs no real Live2D or VTS operation. Mock adapter
        requests complete locally; real adapters return typed unavailable /
        not-implemented results.
        """

        if not isinstance(request, MotionRequest):
            raise TypeError("request must be a MotionRequest")

        if self._closed:
            result = MotionResult.closed(request=request, session_id=self._session_id)
            self._emit(MotionEventType.SESSION_CLOSED, request=request, result=result, state=MotionState.CLOSED)
            return result

        self._emit(MotionEventType.REQUESTED, request=request, public_metadata={"intent": request.intent.value})
        self._state = self._state_for_request(request)
        self._emit(MotionEventType.STARTED, request=request, state=self._state, public_metadata={"intent": request.intent.value})

        if self._capability.adapter_status is MotionAdapterStatus.MOCK_AVAILABLE:
            result = MotionResult.completed(
                request=request,
                session_id=self._session_id,
                state=MotionState.IDLE,
                public_metadata={
                    "mock_motion": True,
                    "intent": request.intent.value,
                },
            )
            self._state = MotionState.IDLE
            self._emit(MotionEventType.COMPLETED, request=request, result=result, state=self._state)
            return result

        if self._capability.adapter_status is MotionAdapterStatus.UNSUPPORTED_ADAPTER:
            result = MotionResult.unavailable(
                request=request,
                adapter_status=self._capability.adapter_status,
                public_error_code=MotionErrorCode.UNSUPPORTED,
                safe_message="Motion adapter is unsupported.",
                session_id=self._session_id,
                public_metadata={"reason": "unsupported_adapter"},
            )
            self._state = MotionState.UNAVAILABLE
            self._emit(MotionEventType.UNSUPPORTED, request=request, result=result, state=self._state)
            return result

        if self._capability.adapter_status is MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED:
            result = MotionResult.unavailable(
                request=request,
                adapter_status=self._capability.adapter_status,
                public_error_code=MotionErrorCode.PROVIDER_EXECUTION_NOT_ALLOWED,
                safe_message="Motion adapter provider execution is not allowed.",
                session_id=self._session_id,
                public_metadata={"reason": "provider_execution_not_allowed"},
            )
            self._state = MotionState.UNAVAILABLE
            self._emit(MotionEventType.UNSUPPORTED, request=request, result=result, state=self._state)
            return result

        if self._capability.adapter_status is MotionAdapterStatus.DISABLED:
            result = MotionResult.unavailable(
                request=request,
                adapter_status=self._capability.adapter_status,
                public_error_code=MotionErrorCode.UNAVAILABLE,
                safe_message="Motion adapter is disabled.",
                session_id=self._session_id,
                public_metadata={"reason": "disabled"},
            )
            self._state = MotionState.UNAVAILABLE
            self._emit(MotionEventType.UNSUPPORTED, request=request, result=result, state=self._state)
            return result

        result = MotionResult.not_implemented(request=request, session_id=self._session_id)
        self._state = MotionState.UNAVAILABLE
        self._emit(MotionEventType.UNSUPPORTED, request=request, result=result, state=self._state)
        return result

    def _state_for_request(self, request: MotionRequest) -> MotionState:
        if request.intent is MotionIntent.EXPRESSION or request.intent is MotionIntent.EMOTION:
            return MotionState.EXPRESSING
        if request.intent is MotionIntent.SPEAKING_STATE:
            return MotionState.SPEAKING
        if request.intent is MotionIntent.GESTURE:
            return MotionState.GESTURING
        if request.intent is MotionIntent.STOP_MOTION:
            return MotionState.INTERRUPTED
        return MotionState.PREPARING

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._state = MotionState.CLOSED
        self._emit(MotionEventType.SESSION_CLOSED, state=MotionState.CLOSED, public_metadata={"reason": "session_closed"})

    def dispose(self) -> None:
        self.close()

    def __enter__(self) -> "MotionSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def create_motion_session(
    *,
    project_root: str | Path | None = None,
    adapter: str = "mock",
    real_adapter_enabled: bool | None = None,
    allow_provider_execution: bool | None = None,
    public_metadata: Mapping[str, Any] | None = None,
) -> MotionSession:
    """Create a mock-safe public motion session."""

    return MotionSession(
        project_root=project_root,
        adapter=adapter,
        real_adapter_enabled=real_adapter_enabled,
        allow_provider_execution=allow_provider_execution,
        public_metadata=public_metadata,
    )
