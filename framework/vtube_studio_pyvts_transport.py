"""Guarded lazy pyvts VTube Studio transport.

FW-VTS-0d implements the internal FW-VTS-0c async transport Protocol with a
lazy pyvts boundary. Normal Framework import, configuration construction, and
all failed explicit guards stop before importing pyvts or creating a provider
client.

The transport accepts explicitly injected endpoint and authentication material.
It does not inspect environment variables, read or write token files, bootstrap
tokens, discover model files, expose endpoint/token/model/hotkey identities,
return raw provider payloads or exceptions, retry automatically, reconnect, or
create background tasks.

These symbols are internal and are intentionally not exported from the
``framework`` root. MotionSession composition remains deferred to FW-VTS-0e.
"""

from __future__ import annotations

import asyncio
import importlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from .motion_adapter_execution import MotionAdapterExecutionConfig
from .vtube_studio_transport import (
    VTubeStudioHotkeyRequest,
    VTubeStudioTransportOperation,
    VTubeStudioTransportOutcome,
    VTubeStudioTransportResult,
)


@runtime_checkable
class VTubeStudioPyvtsClient(Protocol):
    """Minimum structural pyvts client shape used by the transport."""

    vts_request: Any

    async def connect(self) -> None:
        ...

    async def request(
        self,
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        ...

    async def close(self) -> None:
        ...


VTubeStudioPyvtsModuleImporter = Callable[[str], Any]
VTubeStudioPyvtsClientFactory = Callable[
    [Any, "VTubeStudioPyvtsTransportConfig"],
    VTubeStudioPyvtsClient,
]


def _positive_finite(value: float, *, field_name: str) -> float:
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0:
        raise ValueError(f"{field_name} must be finite and positive")
    return resolved


@dataclass(frozen=True, slots=True)
class VTubeStudioPyvtsTransportConfig:
    """Private transport configuration with public-safe declarations.

    Endpoint values and authentication material are internal-only and omitted
    from repr. They are never copied into transport results or safe messages.
    """

    execution_config: MotionAdapterExecutionConfig
    endpoint_host: str = field(
        default="localhost",
        repr=False,
        compare=False,
    )
    endpoint_port: int = field(
        default=8001,
        repr=False,
        compare=False,
    )
    authentication_token: str = field(
        default="",
        repr=False,
        compare=False,
    )
    plugin_name: str = "AI Character Framework"
    plugin_developer: str = "murayan"
    connect_timeout_seconds: float = 3.0
    authenticate_timeout_seconds: float = 3.0
    request_timeout_seconds: float = 3.0
    close_timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        if not isinstance(
            self.execution_config,
            MotionAdapterExecutionConfig,
        ):
            raise TypeError(
                "execution_config must be MotionAdapterExecutionConfig"
            )

        plugin_name = str(self.plugin_name).strip()
        plugin_developer = str(self.plugin_developer).strip()
        if not 3 <= len(plugin_name) <= 32:
            raise ValueError(
                "plugin_name must contain between 3 and 32 characters"
            )
        if not 3 <= len(plugin_developer) <= 32:
            raise ValueError(
                "plugin_developer must contain between 3 and 32 characters"
            )

        endpoint_host = str(self.endpoint_host).strip()
        try:
            endpoint_port: int | None = int(self.endpoint_port)
        except (TypeError, ValueError):
            endpoint_port = None

        object.__setattr__(self, "endpoint_host", endpoint_host)
        object.__setattr__(self, "endpoint_port", endpoint_port)
        object.__setattr__(
            self,
            "authentication_token",
            str(self.authentication_token).strip(),
        )
        object.__setattr__(self, "plugin_name", plugin_name)
        object.__setattr__(self, "plugin_developer", plugin_developer)
        object.__setattr__(
            self,
            "connect_timeout_seconds",
            _positive_finite(
                self.connect_timeout_seconds,
                field_name="connect_timeout_seconds",
            ),
        )
        object.__setattr__(
            self,
            "authenticate_timeout_seconds",
            _positive_finite(
                self.authenticate_timeout_seconds,
                field_name="authenticate_timeout_seconds",
            ),
        )
        object.__setattr__(
            self,
            "request_timeout_seconds",
            _positive_finite(
                self.request_timeout_seconds,
                field_name="request_timeout_seconds",
            ),
        )
        object.__setattr__(
            self,
            "close_timeout_seconds",
            _positive_finite(
                self.close_timeout_seconds,
                field_name="close_timeout_seconds",
            ),
        )

    @property
    def endpoint_valid(self) -> bool:
        return (
            bool(self.endpoint_host)
            and isinstance(self.endpoint_port, int)
            and 1 <= self.endpoint_port <= 65535
        )

    @property
    def authentication_material_present(self) -> bool:
        return bool(self.authentication_token)

    def to_public_dict(self) -> Mapping[str, Any]:
        execution = self.execution_config
        return {
            "adapter": execution.adapter,
            "real_adapter_enabled": execution.real_adapter_enabled,
            "provider_execution_allowed": (
                execution.allow_provider_execution
            ),
            "endpoint_configured": execution.endpoint_configured,
            "runtime_available": execution.runtime_available,
            "authentication_material_available": (
                execution.token_available
            ),
            "model_selected": execution.model_selected,
            "endpoint_value_valid": self.endpoint_valid,
            "authentication_material_present": (
                self.authentication_material_present
            ),
            "plugin_identity_configured": True,
            "connect_timeout_configured": True,
            "authenticate_timeout_configured": True,
            "request_timeout_configured": True,
            "close_timeout_configured": True,
            "endpoint_exposed": False,
            "authentication_material_exposed": False,
            "authentication_location_exposed": False,
        }


def _default_module_importer(name: str) -> Any:
    return importlib.import_module(name)


def _default_client_factory(
    pyvts_module: Any,
    config: VTubeStudioPyvtsTransportConfig,
) -> VTubeStudioPyvtsClient:
    constructor = getattr(pyvts_module, "vts")
    return constructor(
        plugin_info={
            "plugin_name": config.plugin_name,
            "developer": config.plugin_developer,
            "plugin_icon": None,
            "authentication_token_path": "",
        },
        vts_api_info={
            "name": "VTubeStudioPublicAPI",
            "version": "1.0",
            "host": config.endpoint_host,
            "port": config.endpoint_port,
        },
    )


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _response_data(
    response: Any,
) -> tuple[Mapping[str, Any] | None, bool]:
    root = _mapping(response)
    if root is None:
        return None, False

    message_type = str(root.get("messageType", "")).strip()
    if message_type == "APIError":
        return None, True

    data = root.get("data")
    if isinstance(data, Mapping):
        if "errorID" in data:
            return None, True
        return data, False

    return root, False


class VTubeStudioPyvtsTransport:
    """Lazy guarded pyvts implementation of the internal transport Protocol."""

    def __init__(
        self,
        *,
        config: VTubeStudioPyvtsTransportConfig,
        module_importer: VTubeStudioPyvtsModuleImporter | None = None,
        client_factory: VTubeStudioPyvtsClientFactory | None = None,
    ) -> None:
        if not isinstance(config, VTubeStudioPyvtsTransportConfig):
            raise TypeError(
                "config must be VTubeStudioPyvtsTransportConfig"
            )

        self._config = config
        self._module_importer = (
            module_importer or _default_module_importer
        )
        self._client_factory = (
            client_factory or _default_client_factory
        )

        self._client: VTubeStudioPyvtsClient | None = None
        self._available_hotkey_names: dict[str, str] = {}
        self._ready = False
        self._closed = False
        self._operation_active = False
        self._lifecycle_generation = 0

        self._provider_import_attempted = False
        self._provider_sdk_imported = False
        self._provider_client_factory_invoked = False
        self._provider_client_created = False
        self._network_execution_attempted = False
        self._connected = False
        self._authenticated = False
        self._model_loaded = False
        self._hotkey_inventory_loaded = False

    @property
    def transport_name(self) -> str:
        return "pyvts"

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def is_ready(self) -> bool:
        return self._ready and not self._closed

    def _metadata(
        self,
        *,
        reason: str,
        provider_protocol_call_executed: bool = False,
        hotkey_resolved: bool = False,
        single_flight_enforced: bool = False,
        late_completion_suppressed: bool = False,
        already_ready: bool = False,
        already_closed: bool = False,
        timeout_stage: str = "",
    ) -> Mapping[str, Any]:
        return {
            **dict(self._config.to_public_dict()),
            "boundary": "pyvts_transport",
            "transport": self.transport_name,
            "reason": reason,
            "provider_import_attempted": (
                self._provider_import_attempted
            ),
            "provider_sdk_imported": self._provider_sdk_imported,
            "provider_client_factory_invoked": (
                self._provider_client_factory_invoked
            ),
            "provider_client_created": self._provider_client_created,
            "provider_protocol_call_executed": (
                provider_protocol_call_executed
            ),
            "network_execution_attempted": (
                self._network_execution_attempted
            ),
            "connected": self._connected,
            "authenticated": self._authenticated,
            "model_loaded": self._model_loaded,
            "hotkey_inventory_loaded": self._hotkey_inventory_loaded,
            "available_hotkey_count": len(
                self._available_hotkey_names
            ),
            "hotkey_resolved": hotkey_resolved,
            "single_flight_enforced": single_flight_enforced,
            "late_completion_suppressed": (
                late_completion_suppressed
            ),
            "already_ready": already_ready,
            "already_closed": already_closed,
            "timeout_stage": timeout_stage,
            "waiting_operation_queue_created": False,
            "automatic_retry_executed": False,
            "automatic_reconnect_executed": False,
            "background_task_created": False,
            "raw_payload_exposed": False,
            "raw_exception_exposed": False,
            "endpoint_exposed": False,
            "authentication_material_exposed": False,
            "authentication_location_exposed": False,
            "model_identity_exposed": False,
            "hotkey_name_exposed": False,
            "hotkey_identifier_exposed": False,
            "real_hotkey_triggered": False,
            "real_motion_executed": False,
        }

    def _result(
        self,
        *,
        operation: VTubeStudioTransportOperation,
        outcome: VTubeStudioTransportOutcome,
        safe_message: str,
        request_id: str | None = None,
        retryable: bool = False,
        reason: str,
        provider_protocol_call_executed: bool = False,
        hotkey_resolved: bool = False,
        single_flight_enforced: bool = False,
        late_completion_suppressed: bool = False,
        already_ready: bool = False,
        already_closed: bool = False,
        timeout_stage: str = "",
    ) -> VTubeStudioTransportResult:
        return VTubeStudioTransportResult(
            operation=operation,
            outcome=outcome,
            request_id=request_id,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=self._metadata(
                reason=reason,
                provider_protocol_call_executed=(
                    provider_protocol_call_executed
                ),
                hotkey_resolved=hotkey_resolved,
                single_flight_enforced=single_flight_enforced,
                late_completion_suppressed=(
                    late_completion_suppressed
                ),
                already_ready=already_ready,
                already_closed=already_closed,
                timeout_stage=timeout_stage,
            ),
        )

    def _guard_failure(
        self,
    ) -> tuple[str, str] | None:
        execution = self._config.execution_config

        if execution.adapter != "vts":
            return (
                "adapter_not_vts",
                "The configured motion adapter is not VTube Studio.",
            )
        if not execution.real_adapter_enabled:
            return (
                "real_adapter_disabled",
                "The real motion adapter is disabled.",
            )
        if not execution.allow_provider_execution:
            return (
                "provider_execution_not_allowed",
                "Motion provider execution is not allowed.",
            )
        if not execution.endpoint_configured:
            return (
                "endpoint_not_configured",
                "The VTube Studio endpoint is not configured.",
            )
        if not execution.runtime_available:
            return (
                "runtime_not_available",
                "The VTube Studio runtime is not available.",
            )
        if not execution.token_available:
            return (
                "authentication_material_unavailable",
                "VTube Studio authentication material is unavailable.",
            )
        if not execution.model_selected:
            return (
                "model_not_selected",
                "A VTube Studio model is not selected.",
            )
        if not self._config.endpoint_valid:
            return (
                "endpoint_value_invalid",
                "The VTube Studio endpoint configuration is invalid.",
            )
        if not self._config.authentication_material_present:
            return (
                "authentication_material_missing",
                "VTube Studio authentication material is missing.",
            )
        return None

    def _closed_result(
        self,
        operation: VTubeStudioTransportOperation,
        *,
        request_id: str | None = None,
        late_completion_suppressed: bool = False,
    ) -> VTubeStudioTransportResult:
        return self._result(
            operation=operation,
            outcome=VTubeStudioTransportOutcome.CLOSED,
            request_id=request_id,
            safe_message="The VTube Studio transport is closed.",
            reason=(
                "late_completion_suppressed"
                if late_completion_suppressed
                else "transport_closed"
            ),
            late_completion_suppressed=late_completion_suppressed,
        )

    def _busy_result(
        self,
        operation: VTubeStudioTransportOperation,
        *,
        request_id: str | None = None,
    ) -> VTubeStudioTransportResult:
        return self._result(
            operation=operation,
            outcome=VTubeStudioTransportOutcome.BUSY,
            request_id=request_id,
            safe_message=(
                "Another VTube Studio transport operation is active."
            ),
            retryable=True,
            reason="single_flight_busy",
            single_flight_enforced=True,
        )

    def _generation_changed(self, generation: int) -> bool:
        return (
            self._closed
            or generation != self._lifecycle_generation
        )

    def _reset_runtime_state(self) -> None:
        self._ready = False
        self._connected = False
        self._authenticated = False
        self._model_loaded = False
        self._hotkey_inventory_loaded = False
        self._available_hotkey_names = {}

    async def _close_client_best_effort(
        self,
        client: VTubeStudioPyvtsClient,
    ) -> None:
        try:
            await asyncio.wait_for(
                client.close(),
                timeout=self._config.close_timeout_seconds,
            )
        except (TimeoutError, Exception):
            pass

    async def _discard_failed_client(
        self,
        client: VTubeStudioPyvtsClient,
    ) -> None:
        if self._client is client:
            self._client = None
            await self._close_client_best_effort(client)
        self._reset_runtime_state()

    async def preflight(self) -> VTubeStudioTransportResult:
        operation = VTubeStudioTransportOperation.PREFLIGHT

        if self._closed:
            return self._closed_result(operation)

        guard_failure = self._guard_failure()
        if guard_failure is not None:
            reason, message = guard_failure
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                safe_message=message,
                reason=reason,
            )

        if self._ready and self._client is not None:
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.READY,
                safe_message="The VTube Studio transport is ready.",
                reason="already_ready",
                already_ready=True,
            )

        if self._operation_active:
            return self._busy_result(operation)

        self._operation_active = True
        generation = self._lifecycle_generation
        client: VTubeStudioPyvtsClient | None = None

        try:
            self._provider_import_attempted = True
            try:
                pyvts_module = self._module_importer("pyvts")
            except Exception:
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "The VTube Studio provider runtime could not be loaded."
                    ),
                    reason="runtime_import_failed",
                )

            self._provider_sdk_imported = True
            self._provider_client_factory_invoked = True
            try:
                client = self._client_factory(
                    pyvts_module,
                    self._config,
                )
            except Exception:
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "The VTube Studio provider client could not be created."
                    ),
                    reason="provider_client_creation_failed",
                )

            if not isinstance(client, VTubeStudioPyvtsClient):
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "The VTube Studio provider client is incompatible."
                    ),
                    reason="provider_client_incompatible",
                )

            self._provider_client_created = True
            self._client = client

            self._network_execution_attempted = True
            try:
                await asyncio.wait_for(
                    client.connect(),
                    timeout=self._config.connect_timeout_seconds,
                )
            except TimeoutError:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.TIMED_OUT,
                    safe_message=(
                        "The VTube Studio connection timed out."
                    ),
                    reason="connect_timed_out",
                    timeout_stage="connect",
                )
            except Exception:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "The VTube Studio connection could not be established."
                    ),
                    reason="connect_failed",
                )

            if self._generation_changed(generation):
                return self._closed_result(
                    operation,
                    late_completion_suppressed=True,
                )
            self._connected = True

            try:
                auth_request = client.vts_request.authentication(
                    self._config.authentication_token
                )
            except Exception:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    safe_message=(
                        "The VTube Studio authentication request "
                        "could not be prepared."
                    ),
                    reason="authentication_request_failed",
                )

            try:
                auth_response = await asyncio.wait_for(
                    client.request(auth_request),
                    timeout=(
                        self._config.authenticate_timeout_seconds
                    ),
                )
            except TimeoutError:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.TIMED_OUT,
                    safe_message=(
                        "VTube Studio authentication timed out."
                    ),
                    reason="authentication_timed_out",
                    provider_protocol_call_executed=True,
                    timeout_stage="authenticate",
                )
            except Exception:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "VTube Studio authentication failed."
                    ),
                    reason="authentication_failed",
                    provider_protocol_call_executed=True,
                )

            if self._generation_changed(generation):
                return self._closed_result(
                    operation,
                    late_completion_suppressed=True,
                )

            auth_data, auth_api_error = _response_data(auth_response)
            if auth_api_error:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "VTube Studio authentication was rejected."
                    ),
                    reason="authentication_rejected",
                    provider_protocol_call_executed=True,
                )
            if (
                auth_data is None
                or "authenticated" not in auth_data
                or not isinstance(auth_data.get("authenticated"), bool)
            ):
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    safe_message=(
                        "VTube Studio returned an invalid authentication "
                        "response."
                    ),
                    reason="authentication_response_invalid",
                    provider_protocol_call_executed=True,
                )
            if auth_data["authenticated"] is not True:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "VTube Studio authentication was rejected."
                    ),
                    reason="authentication_rejected",
                    provider_protocol_call_executed=True,
                )
            self._authenticated = True

            try:
                inventory_request = (
                    client.vts_request.requestHotKeyList()
                )
            except Exception:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    safe_message=(
                        "The VTube Studio hotkey inventory request "
                        "could not be prepared."
                    ),
                    reason="hotkey_inventory_request_failed",
                    provider_protocol_call_executed=True,
                )

            try:
                inventory_response = await asyncio.wait_for(
                    client.request(inventory_request),
                    timeout=self._config.request_timeout_seconds,
                )
            except TimeoutError:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.TIMED_OUT,
                    safe_message=(
                        "The VTube Studio hotkey inventory timed out."
                    ),
                    reason="hotkey_inventory_timed_out",
                    provider_protocol_call_executed=True,
                    timeout_stage="hotkey_inventory",
                )
            except Exception:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    safe_message=(
                        "The VTube Studio hotkey inventory failed."
                    ),
                    reason="hotkey_inventory_failed",
                    provider_protocol_call_executed=True,
                )

            if self._generation_changed(generation):
                return self._closed_result(
                    operation,
                    late_completion_suppressed=True,
                )

            inventory_data, inventory_api_error = _response_data(
                inventory_response
            )
            if inventory_api_error:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    safe_message=(
                        "The VTube Studio hotkey inventory was rejected."
                    ),
                    reason="hotkey_inventory_rejected",
                    provider_protocol_call_executed=True,
                )
            if inventory_data is None:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    safe_message=(
                        "VTube Studio returned an invalid hotkey inventory."
                    ),
                    reason="hotkey_inventory_response_invalid",
                    provider_protocol_call_executed=True,
                )

            model_loaded = inventory_data.get("modelLoaded")
            available_hotkeys = inventory_data.get(
                "availableHotkeys"
            )
            if (
                not isinstance(model_loaded, bool)
                or not isinstance(available_hotkeys, list)
            ):
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    safe_message=(
                        "VTube Studio returned an invalid hotkey inventory."
                    ),
                    reason="hotkey_inventory_response_invalid",
                    provider_protocol_call_executed=True,
                )

            if model_loaded is not True:
                await self._discard_failed_client(client)
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                    safe_message=(
                        "No VTube Studio model is currently loaded."
                    ),
                    reason="model_not_loaded",
                    provider_protocol_call_executed=True,
                )

            names: dict[str, str] = {}
            for item in available_hotkeys:
                if not isinstance(item, Mapping):
                    await self._discard_failed_client(client)
                    return self._result(
                        operation=operation,
                        outcome=VTubeStudioTransportOutcome.FAILED,
                        safe_message=(
                            "VTube Studio returned an invalid hotkey "
                            "inventory."
                        ),
                        reason="hotkey_inventory_response_invalid",
                        provider_protocol_call_executed=True,
                    )
                value = item.get("name")
                if value is None:
                    continue
                name = str(value).strip()
                if name:
                    names[name.casefold()] = name

            self._available_hotkey_names = names
            self._model_loaded = True
            self._hotkey_inventory_loaded = True
            self._ready = True

            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.READY,
                safe_message="The VTube Studio transport is ready.",
                reason="transport_ready",
                provider_protocol_call_executed=True,
            )
        finally:
            self._operation_active = False

    async def trigger_hotkey(
        self,
        request: VTubeStudioHotkeyRequest,
    ) -> VTubeStudioTransportResult:
        if not isinstance(request, VTubeStudioHotkeyRequest):
            raise TypeError(
                "request must be VTubeStudioHotkeyRequest"
            )

        operation = VTubeStudioTransportOperation.TRIGGER_HOTKEY

        if self._closed:
            return self._closed_result(
                operation,
                request_id=request.request_id,
            )

        if not self._ready or self._client is None:
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.UNAVAILABLE,
                request_id=request.request_id,
                safe_message=(
                    "The VTube Studio transport has not completed preflight."
                ),
                reason="transport_not_ready",
            )

        if self._operation_active:
            return self._busy_result(
                operation,
                request_id=request.request_id,
            )

        lookup_key = request.hotkey_name.casefold()
        if lookup_key not in self._available_hotkey_names:
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.NOT_FOUND,
                request_id=request.request_id,
                safe_message=(
                    "The configured VTube Studio hotkey was not found."
                ),
                reason="hotkey_not_found",
            )

        self._operation_active = True
        generation = self._lifecycle_generation
        client = self._client

        try:
            try:
                trigger_request = (
                    client.vts_request.requestTriggerHotKey(
                        request.hotkey_name
                    )
                )
            except Exception:
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    request_id=request.request_id,
                    safe_message=(
                        "The VTube Studio hotkey request could not "
                        "be prepared."
                    ),
                    reason="trigger_request_failed",
                    hotkey_resolved=True,
                )

            self._network_execution_attempted = True
            try:
                response = await asyncio.wait_for(
                    client.request(trigger_request),
                    timeout=self._config.request_timeout_seconds,
                )
            except TimeoutError:
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.TIMED_OUT,
                    request_id=request.request_id,
                    safe_message=(
                        "The VTube Studio hotkey request timed out."
                    ),
                    reason="trigger_timed_out",
                    provider_protocol_call_executed=True,
                    hotkey_resolved=True,
                    timeout_stage="trigger_hotkey",
                )
            except Exception:
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    request_id=request.request_id,
                    safe_message=(
                        "The VTube Studio hotkey request failed."
                    ),
                    reason="trigger_failed",
                    provider_protocol_call_executed=True,
                    hotkey_resolved=True,
                )

            if self._generation_changed(generation):
                return self._closed_result(
                    operation,
                    request_id=request.request_id,
                    late_completion_suppressed=True,
                )

            response_root = _mapping(response)
            _, api_error = _response_data(response)
            if response_root is None:
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    request_id=request.request_id,
                    safe_message=(
                        "VTube Studio returned an invalid hotkey response."
                    ),
                    reason="trigger_response_invalid",
                    provider_protocol_call_executed=True,
                    hotkey_resolved=True,
                )
            if api_error:
                return self._result(
                    operation=operation,
                    outcome=VTubeStudioTransportOutcome.FAILED,
                    request_id=request.request_id,
                    safe_message=(
                        "VTube Studio rejected the hotkey request."
                    ),
                    reason="trigger_rejected",
                    provider_protocol_call_executed=True,
                    hotkey_resolved=True,
                )

            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.COMPLETED,
                request_id=request.request_id,
                safe_message=(
                    "The VTube Studio hotkey request completed."
                ),
                reason="trigger_completed",
                provider_protocol_call_executed=True,
                hotkey_resolved=True,
            )
        finally:
            self._operation_active = False

    async def close(self) -> VTubeStudioTransportResult:
        operation = VTubeStudioTransportOperation.CLOSE

        if self._closed:
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.COMPLETED,
                safe_message="The VTube Studio transport is closed.",
                reason="transport_already_closed",
                already_closed=True,
            )

        self._closed = True
        self._lifecycle_generation += 1
        self._ready = False
        self._available_hotkey_names = {}
        self._model_loaded = False
        self._hotkey_inventory_loaded = False

        client = self._client
        self._client = None

        if client is None:
            self._connected = False
            self._authenticated = False
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.COMPLETED,
                safe_message="The VTube Studio transport is closed.",
                reason="transport_closed_without_client",
            )

        try:
            await asyncio.wait_for(
                client.close(),
                timeout=self._config.close_timeout_seconds,
            )
        except TimeoutError:
            self._connected = False
            self._authenticated = False
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.TIMED_OUT,
                safe_message=(
                    "Closing the VTube Studio transport timed out."
                ),
                reason="close_timed_out",
                timeout_stage="close",
            )
        except Exception:
            self._connected = False
            self._authenticated = False
            return self._result(
                operation=operation,
                outcome=VTubeStudioTransportOutcome.FAILED,
                safe_message=(
                    "Closing the VTube Studio transport failed."
                ),
                reason="close_failed",
            )

        self._connected = False
        self._authenticated = False
        return self._result(
            operation=operation,
            outcome=VTubeStudioTransportOutcome.COMPLETED,
            safe_message="The VTube Studio transport is closed.",
            reason="transport_closed",
        )
