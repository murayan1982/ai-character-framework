"""Public motion session boundary.

The default mock path remains local and provider-neutral.  FW-VTS-0e adds a
strictly explicit VTube Studio composition path behind the existing root-public
MotionSession API.  Failed guards stop before importing the internal composition
module, starting its worker thread, importing pyvts, or executing a network
operation.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping
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
from .version import MOTION_API_VERSION

from .motion_adapter_execution import (
    MotionAdapterExecutionConfig,
    get_motion_adapter_execution_capability,
    resolve_motion_adapter_execution_config,
)
if TYPE_CHECKING:
    from .vtube_studio_transport import VTubeStudioTransportResult


MotionEventCallback = Callable[[Mapping[str, Any]], None]

_VTS_ALIASES = frozenset({"vts", "vtube_studio", "live2d"})
_MAX_VTS_HOTKEY_BINDINGS = 256
_MAX_VTS_SELECTOR_LENGTH = 128
_MAX_VTS_HOTKEY_NAME_LENGTH = 128
_VTS_HOTKEY_INTENTS = frozenset(
    {
        MotionIntent.EXPRESSION,
        MotionIntent.EMOTION,
        MotionIntent.GESTURE,
        MotionIntent.STOP_MOTION,
        MotionIntent.RESET_EXPRESSION,
    }
)
_SAFE_TRANSPORT_BOOLEAN_KEYS = frozenset(
    {
        "provider_import_attempted",
        "provider_sdk_imported",
        "provider_client_factory_invoked",
        "provider_client_created",
        "provider_protocol_call_executed",
        "network_execution_attempted",
        "connected",
        "authenticated",
        "model_loaded",
        "hotkey_inventory_loaded",
        "hotkey_resolved",
        "single_flight_enforced",
        "late_completion_suppressed",
        "already_ready",
        "already_closed",
        "waiting_operation_queue_created",
        "automatic_retry_executed",
        "automatic_reconnect_executed",
        "background_task_created",
        "raw_payload_exposed",
        "raw_exception_exposed",
        "endpoint_exposed",
        "authentication_material_exposed",
        "authentication_location_exposed",
        "model_identity_exposed",
        "hotkey_name_exposed",
        "hotkey_identifier_exposed",
        "real_hotkey_triggered",
        "real_motion_executed",
        "persistent_event_loop",
        "worker_thread_started",
        "worker_thread_terminated",
    }
)
_SAFE_TRANSPORT_STRING_KEYS = frozenset(
    {"boundary", "transport", "reason", "timeout_stage"}
)


def _positive_finite(value: float, *, field_name: str) -> float:
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0:
        raise ValueError(f"{field_name} must be finite and positive")
    return resolved


def _normalize_vts_selector(value: str) -> tuple[str, MotionIntent]:
    selector = str(value).strip().casefold()
    if not selector:
        raise ValueError("VTube Studio hotkey selector must not be blank")
    if len(selector) > _MAX_VTS_SELECTOR_LENGTH:
        raise ValueError("VTube Studio hotkey selector is too long")

    if selector in {"stop_motion", "reset_expression"}:
        intent = (
            MotionIntent.STOP_MOTION
            if selector == "stop_motion"
            else MotionIntent.RESET_EXPRESSION
        )
        return selector, intent

    prefix, separator, selected_value = selector.partition(":")
    intent_by_prefix = {
        "expression": MotionIntent.EXPRESSION,
        "emotion": MotionIntent.EMOTION,
        "gesture": MotionIntent.GESTURE,
    }
    if not separator or prefix not in intent_by_prefix or not selected_value.strip():
        raise ValueError(
            "VTube Studio hotkey selector must be expression:<value>, "
            "emotion:<value>, gesture:<value>, stop_motion, or "
            "reset_expression"
        )
    return f"{prefix}:{selected_value.strip()}", intent_by_prefix[prefix]


def _normalize_vts_hotkey_bindings(
    values: Mapping[str, str] | None,
) -> tuple[Mapping[str, str], tuple[MotionIntent, ...]]:
    if values is None:
        return _public_mapping({}), ()
    if not isinstance(values, Mapping):
        raise TypeError("vts_hotkey_bindings must be a mapping")
    if len(values) > _MAX_VTS_HOTKEY_BINDINGS:
        raise ValueError("vts_hotkey_bindings contains too many entries")

    normalized: dict[str, str] = {}
    intents: list[MotionIntent] = []
    seen_intents: set[MotionIntent] = set()
    for raw_selector, raw_hotkey_name in values.items():
        if not isinstance(raw_selector, str) or not isinstance(raw_hotkey_name, str):
            raise TypeError("vts_hotkey_bindings keys and values must be strings")
        selector, intent = _normalize_vts_selector(raw_selector)
        if selector in normalized:
            raise ValueError(
                "vts_hotkey_bindings contains a duplicate normalized selector"
            )
        hotkey_name = str(raw_hotkey_name).strip()
        if not hotkey_name:
            raise ValueError("VTube Studio hotkey name must not be blank")
        if len(hotkey_name) > _MAX_VTS_HOTKEY_NAME_LENGTH:
            raise ValueError("VTube Studio hotkey name is too long")
        normalized[selector] = hotkey_name
        if intent not in seen_intents:
            intents.append(intent)
            seen_intents.add(intent)

    # The mapping remains internal.  MappingProxyType is useful here, but this
    # is intentionally not passed through public metadata redaction.
    from types import MappingProxyType

    return MappingProxyType(normalized), tuple(intents)


def _safe_transport_metadata(
    result: "VTubeStudioTransportResult",
) -> Mapping[str, Any]:
    safe: dict[str, Any] = {
        "boundary": "motion",
        "transport_outcome": result.outcome.value,
    }
    for key, value in result.public_metadata.items():
        if key in _SAFE_TRANSPORT_BOOLEAN_KEYS and isinstance(value, bool):
            safe[key] = value
        elif key == "boundary" and isinstance(value, str):
            safe["transport_boundary"] = value[:128]
        elif key in _SAFE_TRANSPORT_STRING_KEYS and isinstance(value, str):
            safe[key] = value[:128]
        elif key == "available_hotkey_count" and isinstance(value, int):
            safe[key] = max(0, min(value, 10000))
    return _public_mapping(safe)


@dataclass(frozen=True)
class MotionSessionInfo:
    """App-safe metadata for a public motion session."""

    # FW-VTS-0a historical marker retained for its frozen readiness checker:
    # api_version: str = "5.2.0"
    api_version: str = MOTION_API_VERSION
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
    """Public provider-neutral motion session with guarded VTS composition."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        adapter: str = "mock",
        real_adapter_enabled: bool | None = None,
        allow_provider_execution: bool | None = None,
        runtime_available: bool | None = None,
        model_selected: bool | None = None,
        vts_endpoint_host: str | None = None,
        vts_endpoint_port: int | None = None,
        vts_authentication_token: str | None = None,
        vts_hotkey_bindings: Mapping[str, str] | None = None,
        vts_connect_timeout_seconds: float = 3.0,
        vts_authenticate_timeout_seconds: float = 3.0,
        vts_request_timeout_seconds: float = 3.0,
        vts_close_timeout_seconds: float = 2.0,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._session_id = uuid4().hex
        self._adapter = adapter or "mock"
        self._real_adapter_enabled = bool(real_adapter_enabled)
        self._allow_provider_execution = bool(allow_provider_execution)
        self._closed = False
        self._closed_event_emitted = False
        self._closed_event_lock = threading.Lock()
        self._state = MotionState.IDLE
        self._callbacks: list[MotionEventCallback] = []
        self._public_metadata = _public_mapping(public_metadata)

        self._runtime_available = bool(runtime_available)
        self._model_selected = bool(model_selected)
        self._vts_endpoint_host = (
            str(vts_endpoint_host).strip()
            if vts_endpoint_host is not None
            else ""
        )
        self._vts_endpoint_port = self._normalize_vts_port(vts_endpoint_port)
        self._vts_authentication_token = (
            str(vts_authentication_token).strip()
            if vts_authentication_token is not None
            else ""
        )
        (
            self._vts_hotkey_bindings,
            self._vts_configured_intents,
        ) = _normalize_vts_hotkey_bindings(vts_hotkey_bindings)
        self._vts_connect_timeout_seconds = _positive_finite(
            vts_connect_timeout_seconds,
            field_name="vts_connect_timeout_seconds",
        )
        self._vts_authenticate_timeout_seconds = _positive_finite(
            vts_authenticate_timeout_seconds,
            field_name="vts_authenticate_timeout_seconds",
        )
        self._vts_request_timeout_seconds = _positive_finite(
            vts_request_timeout_seconds,
            field_name="vts_request_timeout_seconds",
        )
        self._vts_close_timeout_seconds = _positive_finite(
            vts_close_timeout_seconds,
            field_name="vts_close_timeout_seconds",
        )
        self._vts_configuration_supplied = any(
            value is not None
            for value in (
                runtime_available,
                model_selected,
                vts_endpoint_host,
                vts_endpoint_port,
                vts_authentication_token,
                vts_hotkey_bindings,
            )
        )
        self._vts_execution_config: MotionAdapterExecutionConfig | None = None
        self._vts_composition: Any | None = None
        self._vts_preflight_ready = False
        self._capability = self._resolve_capability()

    @staticmethod
    def _normalize_vts_port(value: int | None) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            port = int(value)
        except (TypeError, ValueError):
            return None
        return port if 1 <= port <= 65535 else None

    @property
    def _uses_vts_composition(self) -> bool:
        return (
            self._adapter.strip().lower() in _VTS_ALIASES
            and self._vts_configuration_supplied
        )

    def _resolve_capability(self) -> MotionCapability:
        adapter = self._adapter.lower()

        if not self._uses_vts_composition:
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

        endpoint_configured = bool(
            self._vts_endpoint_host and self._vts_endpoint_port is not None
        )
        self._vts_execution_config = resolve_motion_adapter_execution_config(
            adapter=self._adapter,
            real_adapter_enabled=self._real_adapter_enabled,
            allow_provider_execution=self._allow_provider_execution,
            endpoint_configured=endpoint_configured,
            runtime_available=self._runtime_available,
            token_available=bool(self._vts_authentication_token),
            model_selected=self._model_selected,
            configured_intents=self._vts_configured_intents,
        )
        return get_motion_adapter_execution_capability(
            self._vts_execution_config
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
        """Register a public motion event callback."""

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


    def _emit_closed_once(
        self,
        *,
        request: MotionRequest | None = None,
        result: MotionResult | None = None,
    ) -> Mapping[str, Any] | None:
        with self._closed_event_lock:
            if self._closed_event_emitted:
                return None
            self._closed_event_emitted = True
        return self._emit(
            MotionEventType.SESSION_CLOSED,
            request=request,
            result=result,
            state=MotionState.CLOSED,
            public_metadata={"reason": "session_closed"},
        )

    def emit_created(self) -> Mapping[str, Any]:
        """Emit a public motion session-created event."""

        return self._emit(MotionEventType.SESSION_CREATED, state=self._state)

    def _ensure_vts_composition(self) -> Any:
        if self._vts_composition is not None:
            return self._vts_composition
        if self._vts_execution_config is None:
            raise RuntimeError("VTube Studio execution config is unavailable")
        if self._vts_endpoint_port is None:
            raise RuntimeError("VTube Studio endpoint is unavailable")

        from .vtube_studio_motion_composition import (
            create_vtube_studio_motion_composition,
        )

        self._vts_composition = create_vtube_studio_motion_composition(
            execution_config=self._vts_execution_config,
            endpoint_host=self._vts_endpoint_host,
            endpoint_port=self._vts_endpoint_port,
            authentication_token=self._vts_authentication_token,
            hotkey_bindings=self._vts_hotkey_bindings,
            connect_timeout_seconds=self._vts_connect_timeout_seconds,
            authenticate_timeout_seconds=self._vts_authenticate_timeout_seconds,
            request_timeout_seconds=self._vts_request_timeout_seconds,
            close_timeout_seconds=self._vts_close_timeout_seconds,
        )
        return self._vts_composition

    def _vts_ready_capability(
        self,
        transport_result: "VTubeStudioTransportResult",
    ) -> MotionCapability:
        configured = frozenset(self._vts_configured_intents)
        metadata = {
            "boundary": "motion",
            "reason": "vts_transport_ready",
            "configuration_source": "explicit_arguments_only",
            "transport_ready": True,
            "configured_intent_count": len(configured),
            **dict(_safe_transport_metadata(transport_result)),
        }
        return MotionCapability(
            adapter=self._adapter,
            adapter_status=MotionAdapterStatus.CONFIGURED,
            supports_motion_session=True,
            supports_mock_motion=True,
            supports_real_adapter=True,
            supports_expression=MotionIntent.EXPRESSION in configured,
            supports_emotion=MotionIntent.EMOTION in configured,
            supports_speaking_state=False,
            supports_idle_motion=False,
            supports_gesture=MotionIntent.GESTURE in configured,
            supports_look_at=False,
            supports_stop_motion=MotionIntent.STOP_MOTION in configured,
            supports_reset_expression=(
                MotionIntent.RESET_EXPRESSION in configured
            ),
            safe_message="The VTube Studio motion adapter is ready.",
            public_metadata=metadata,
        )

    def _vts_failed_preflight_capability(
        self,
        transport_result: "VTubeStudioTransportResult",
    ) -> MotionCapability:
        if transport_result.outcome.value == "closed":
            status = MotionAdapterStatus.CLOSED
        else:
            reason = str(transport_result.public_metadata.get("reason", ""))
            if "authentication" in reason:
                status = MotionAdapterStatus.TOKEN_MISSING
            elif "model" in reason:
                status = MotionAdapterStatus.MODEL_NOT_SELECTED
            else:
                status = MotionAdapterStatus.CONFIGURED
        return MotionCapability(
            adapter=self._adapter,
            adapter_status=status,
            supports_motion_session=True,
            supports_mock_motion=True,
            supports_real_adapter=False,
            supports_expression=(
                MotionIntent.EXPRESSION in self._vts_configured_intents
            ),
            supports_emotion=(
                MotionIntent.EMOTION in self._vts_configured_intents
            ),
            supports_gesture=(
                MotionIntent.GESTURE in self._vts_configured_intents
            ),
            supports_stop_motion=(
                MotionIntent.STOP_MOTION in self._vts_configured_intents
            ),
            supports_reset_expression=(
                MotionIntent.RESET_EXPRESSION in self._vts_configured_intents
            ),
            safe_message="The VTube Studio motion adapter is not ready.",
            public_metadata={
                "boundary": "motion",
                "reason": "vts_preflight_failed",
                "transport_ready": False,
                **dict(_safe_transport_metadata(transport_result)),
            },
        )

    def preflight(self) -> MotionCapability:
        """Return and, for an explicitly configured VTS adapter, verify capability."""

        if self._closed:
            self._capability = MotionCapability(
                adapter=self._adapter,
                adapter_status=MotionAdapterStatus.CLOSED,
                safe_message="Motion session is closed.",
                public_metadata={"boundary": "motion", "reason": "session_closed"},
            )
        elif (
            self._uses_vts_composition
            and self._vts_execution_config is not None
            and self._vts_execution_config.configuration_complete
        ):
            composition = self._ensure_vts_composition()
            transport_result = composition.preflight()
            self._vts_preflight_ready = (
                transport_result.outcome.value == "ready"
            )
            self._capability = (
                self._vts_ready_capability(transport_result)
                if self._vts_preflight_ready
                else self._vts_failed_preflight_capability(transport_result)
            )

        self._emit(
            MotionEventType.ADAPTER_PREFLIGHT_COMPLETED,
            public_metadata={
                "adapter_status": self._capability.adapter_status.value,
                "transport_ready": self._vts_preflight_ready,
            },
        )
        return self._capability

    def _capability_failure_result(
        self,
        request: MotionRequest,
    ) -> tuple[MotionResult, MotionEventType]:
        status = self._capability.adapter_status
        if status is MotionAdapterStatus.UNSUPPORTED_ADAPTER:
            return (
                MotionResult.unavailable(
                    request=request,
                    adapter_status=status,
                    public_error_code=MotionErrorCode.UNSUPPORTED,
                    safe_message="Motion adapter is unsupported.",
                    session_id=self._session_id,
                    public_metadata={"reason": "unsupported_adapter"},
                ),
                MotionEventType.UNSUPPORTED,
            )
        if status is MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED:
            return (
                MotionResult.unavailable(
                    request=request,
                    adapter_status=status,
                    public_error_code=MotionErrorCode.PROVIDER_EXECUTION_NOT_ALLOWED,
                    safe_message="Motion adapter provider execution is not allowed.",
                    session_id=self._session_id,
                    public_metadata={"reason": "provider_execution_not_allowed"},
                ),
                MotionEventType.UNSUPPORTED,
            )
        if status is MotionAdapterStatus.DISABLED:
            return (
                MotionResult.unavailable(
                    request=request,
                    adapter_status=status,
                    public_error_code=MotionErrorCode.UNAVAILABLE,
                    safe_message="Motion adapter is disabled.",
                    session_id=self._session_id,
                    public_metadata={"reason": "disabled"},
                ),
                MotionEventType.UNSUPPORTED,
            )
        error_by_status = {
            MotionAdapterStatus.NOT_CONFIGURED: MotionErrorCode.NOT_CONFIGURED,
            MotionAdapterStatus.TOKEN_MISSING: MotionErrorCode.TOKEN_MISSING,
            MotionAdapterStatus.RUNTIME_NOT_INSTALLED: MotionErrorCode.RUNTIME_NOT_INSTALLED,
            MotionAdapterStatus.MODEL_NOT_SELECTED: MotionErrorCode.MODEL_NOT_SELECTED,
        }
        if status in error_by_status:
            outcome = (
                MotionOutcome.UNAVAILABLE
                if status is MotionAdapterStatus.RUNTIME_NOT_INSTALLED
                else MotionOutcome.NOT_CONFIGURED
            )
            return (
                MotionResult(
                    outcome=outcome,
                    state=MotionState.UNAVAILABLE,
                    adapter_status=status,
                    public_error_code=error_by_status[status],
                    safe_message=self._capability.safe_message,
                    retryable=False,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata={
                        "boundary": "motion",
                        "reason": str(
                            self._capability.public_metadata.get(
                                "reason",
                                "adapter_unavailable",
                            )
                        ),
                    },
                ),
                MotionEventType.FAILED,
            )
        return (
            MotionResult.not_implemented(
                request=request,
                session_id=self._session_id,
            ),
            MotionEventType.UNSUPPORTED,
        )

    def _vts_transport_result(
        self,
        *,
        request: MotionRequest,
        transport_result: "VTubeStudioTransportResult",
    ) -> tuple[MotionResult, MotionEventType]:
        metadata = {
            "boundary": "motion",
            "intent": request.intent.value,
            **dict(_safe_transport_metadata(transport_result)),
        }
        outcome = transport_result.outcome
        if outcome.value == "completed":
            return (
                MotionResult(
                    outcome=MotionOutcome.COMPLETED,
                    state=MotionState.IDLE,
                    adapter_status=MotionAdapterStatus.CONFIGURED,
                    public_error_code=MotionErrorCode.NONE,
                    safe_message="Motion completed.",
                    retryable=False,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata=metadata,
                ),
                MotionEventType.COMPLETED,
            )
        if outcome.value == "not_found":
            return (
                MotionResult(
                    outcome=MotionOutcome.NOT_CONFIGURED,
                    state=MotionState.UNAVAILABLE,
                    adapter_status=MotionAdapterStatus.CONFIGURED,
                    public_error_code=MotionErrorCode.NOT_CONFIGURED,
                    safe_message="The configured motion binding is unavailable.",
                    retryable=False,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata=metadata,
                ),
                MotionEventType.FAILED,
            )
        if outcome.value == "busy":
            return (
                MotionResult(
                    outcome=MotionOutcome.UNAVAILABLE,
                    state=MotionState.UNAVAILABLE,
                    adapter_status=MotionAdapterStatus.CONFIGURED,
                    public_error_code=MotionErrorCode.UNAVAILABLE,
                    safe_message="Another motion operation is active.",
                    retryable=True,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata=metadata,
                ),
                MotionEventType.FAILED,
            )
        if outcome.value in {"timed_out", "failed"}:
            return (
                MotionResult(
                    outcome=MotionOutcome.FAILED,
                    state=MotionState.FAILED,
                    adapter_status=MotionAdapterStatus.CONFIGURED,
                    public_error_code=MotionErrorCode.PROVIDER_ERROR,
                    safe_message="The motion provider operation failed.",
                    retryable=(
                        True
                        if outcome.value == "timed_out"
                        else transport_result.retryable
                    ),
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata=metadata,
                ),
                MotionEventType.FAILED,
            )
        if outcome.value == "unavailable":
            return (
                MotionResult(
                    outcome=MotionOutcome.UNAVAILABLE,
                    state=MotionState.UNAVAILABLE,
                    adapter_status=MotionAdapterStatus.CONFIGURED,
                    public_error_code=MotionErrorCode.UNAVAILABLE,
                    safe_message="The motion provider is unavailable.",
                    retryable=False,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata=metadata,
                ),
                MotionEventType.FAILED,
            )
        if outcome.value == "closed":
            return (
                MotionResult(
                    outcome=MotionOutcome.CLOSED,
                    state=MotionState.CLOSED,
                    adapter_status=MotionAdapterStatus.CLOSED,
                    public_error_code=MotionErrorCode.SESSION_CLOSED,
                    safe_message="Motion session is closed.",
                    retryable=False,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata=metadata,
                ),
                MotionEventType.SESSION_CLOSED,
            )
        return (
            MotionResult(
                outcome=MotionOutcome.FAILED,
                state=MotionState.FAILED,
                adapter_status=MotionAdapterStatus.CONFIGURED,
                public_error_code=MotionErrorCode.PROVIDER_ERROR,
                safe_message="The motion provider returned an invalid result.",
                retryable=False,
                request_id=request.request_id,
                session_id=self._session_id,
                public_metadata=metadata,
            ),
            MotionEventType.FAILED,
        )

    def apply_motion(self, request: MotionRequest) -> MotionResult:
        """Apply a public motion request through mock or guarded VTS paths."""

        if not isinstance(request, MotionRequest):
            raise TypeError("request must be a MotionRequest")

        if self._closed:
            result = MotionResult.closed(request=request, session_id=self._session_id)
            self._emit_closed_once(request=request, result=result)
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

        if self._uses_vts_composition:
            if self._capability.adapter_status is not MotionAdapterStatus.CONFIGURED:
                result, event_type = self._capability_failure_result(request)
                self._state = result.state
                self._emit(event_type, request=request, result=result, state=self._state)
                return result

            if not self._vts_preflight_ready or self._vts_composition is None:
                result = MotionResult(
                    outcome=MotionOutcome.NOT_CONFIGURED,
                    state=MotionState.UNAVAILABLE,
                    adapter_status=MotionAdapterStatus.CONFIGURED,
                    public_error_code=MotionErrorCode.NOT_CONFIGURED,
                    safe_message="Motion adapter preflight is required.",
                    retryable=False,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata={
                        "boundary": "motion",
                        "reason": "preflight_required",
                        "intent": request.intent.value,
                    },
                )
                self._state = result.state
                self._emit(MotionEventType.FAILED, request=request, result=result, state=self._state)
                return result

            resolution = self._vts_composition.resolve_request(request)
            if not resolution.resolved:
                unsupported = resolution.reason == "unsupported_intent"
                result = MotionResult(
                    outcome=(
                        MotionOutcome.UNSUPPORTED
                        if unsupported
                        else MotionOutcome.NOT_CONFIGURED
                    ),
                    state=MotionState.UNAVAILABLE,
                    adapter_status=MotionAdapterStatus.CONFIGURED,
                    public_error_code=(
                        MotionErrorCode.UNSUPPORTED
                        if unsupported
                        else MotionErrorCode.NOT_CONFIGURED
                    ),
                    safe_message=(
                        "Motion intent is unsupported by the VTube Studio adapter."
                        if unsupported
                        else "Motion intent has no configured VTube Studio binding."
                    ),
                    retryable=False,
                    request_id=request.request_id,
                    session_id=self._session_id,
                    public_metadata={
                        "boundary": "motion",
                        "reason": resolution.reason,
                        "intent": request.intent.value,
                        "provider_call_executed": False,
                    },
                )
                self._state = result.state
                self._emit(MotionEventType.UNSUPPORTED, request=request, result=result, state=self._state)
                return result

            transport_result = self._vts_composition.trigger(
                resolution.request
            )
            result, event_type = self._vts_transport_result(
                request=request,
                transport_result=transport_result,
            )
            self._state = result.state
            if result.outcome is MotionOutcome.CLOSED:
                self._closed = True
                self._vts_preflight_ready = False
                self._vts_composition.close()
            if event_type is MotionEventType.SESSION_CLOSED:
                self._emit_closed_once(request=request, result=result)
            else:
                self._emit(event_type, request=request, result=result, state=self._state)
            return result

        result, event_type = self._capability_failure_result(request)
        self._state = result.state
        self._emit(event_type, request=request, result=result, state=self._state)
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
        self._vts_preflight_ready = False
        if self._vts_composition is not None:
            self._vts_composition.close()
        self._emit_closed_once()

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
    runtime_available: bool | None = None,
    model_selected: bool | None = None,
    vts_endpoint_host: str | None = None,
    vts_endpoint_port: int | None = None,
    vts_authentication_token: str | None = None,
    vts_hotkey_bindings: Mapping[str, str] | None = None,
    vts_connect_timeout_seconds: float = 3.0,
    vts_authenticate_timeout_seconds: float = 3.0,
    vts_request_timeout_seconds: float = 3.0,
    vts_close_timeout_seconds: float = 2.0,
    public_metadata: Mapping[str, Any] | None = None,
) -> MotionSession:
    """Create a public motion session with default-off real VTS composition."""

    return MotionSession(
        project_root=project_root,
        adapter=adapter,
        real_adapter_enabled=real_adapter_enabled,
        allow_provider_execution=allow_provider_execution,
        runtime_available=runtime_available,
        model_selected=model_selected,
        vts_endpoint_host=vts_endpoint_host,
        vts_endpoint_port=vts_endpoint_port,
        vts_authentication_token=vts_authentication_token,
        vts_hotkey_bindings=vts_hotkey_bindings,
        vts_connect_timeout_seconds=vts_connect_timeout_seconds,
        vts_authenticate_timeout_seconds=vts_authenticate_timeout_seconds,
        vts_request_timeout_seconds=vts_request_timeout_seconds,
        vts_close_timeout_seconds=vts_close_timeout_seconds,
        public_metadata=public_metadata,
    )
