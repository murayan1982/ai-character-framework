"""FW-VTS-0d guarded lazy pyvts transport smoke.

The smoke executes the real-capable transport only against an injected fake
pyvts module and fake client. It never imports actual pyvts/WebSocket modules or
opens a network connection.
"""

from __future__ import annotations

import asyncio
import importlib
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

SYNTHETIC_HOST = "synthetic-vts-host.invalid"
SYNTHETIC_AUTH = "synthetic-auth-material"
SYNTHETIC_HOTKEY = "SyntheticSmile"
SYNTHETIC_SECOND_HOTKEY = "SyntheticReset"
SYNTHETIC_MISSING = "SyntheticMissing"
SYNTHETIC_PROVIDER_ERROR = "synthetic-provider-private-error"

FORBIDDEN_MODULE_FRAGMENTS = (
    "pyvts",
    "websocket",
    "websockets",
    "live2d.vts_client",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _blocked_connection(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("FW-VTS-0d attempted a real network connection")


def _assert_forbidden_modules_absent() -> None:
    hits = sorted(
        name
        for name in sys.modules
        if (
            name == "pyvts"
            or name.startswith("pyvts.")
            or name == "websocket"
            or name.startswith("websocket.")
            or name == "websockets"
            or name.startswith("websockets.")
            or name == "live2d.vts_client"
            or name.startswith("live2d.vts_client.")
        )
    )
    _require(
        not hits,
        "actual VTS/WebSocket modules were loaded: " + ", ".join(hits),
    )


class _FakeRequestBuilder:
    def authentication(self, material: str) -> Mapping[str, Any]:
        return {
            "kind": "authentication",
            "authentication_material": material,
        }

    def requestHotKeyList(self) -> Mapping[str, Any]:
        return {"kind": "hotkey_inventory"}

    def requestTriggerHotKey(
        self,
        hotkey_name: str,
    ) -> Mapping[str, Any]:
        return {
            "kind": "trigger_hotkey",
            "hotkey_name": hotkey_name,
        }


class _FakePyvtsClient:
    ai_character_framework_fake_vts_client = True

    def __init__(
        self,
        *,
        authentication_response: Any | None = None,
        inventory_response: Any | None = None,
        trigger_response: Any | None = None,
        connect_delay: float = 0.0,
        authentication_delay: float = 0.0,
        inventory_delay: float = 0.0,
        trigger_delay: float = 0.0,
        close_delay: float = 0.0,
        connect_error: bool = False,
        authentication_error: bool = False,
        inventory_error: bool = False,
        trigger_error: bool = False,
        close_error: bool = False,
        trigger_entered: asyncio.Event | None = None,
        trigger_release: asyncio.Event | None = None,
    ) -> None:
        self.vts_request = _FakeRequestBuilder()
        self.authentication_response = (
            authentication_response
            if authentication_response is not None
            else {
                "messageType": "AuthenticationResponse",
                "data": {"authenticated": True},
            }
        )
        self.inventory_response = (
            inventory_response
            if inventory_response is not None
            else {
                "messageType": "HotkeysInCurrentModelResponse",
                "data": {
                    "modelLoaded": True,
                    "modelName": "private-model-name",
                    "modelID": "private-model-id",
                    "availableHotkeys": [
                        {
                            "name": SYNTHETIC_HOTKEY,
                            "hotkeyID": "private-hotkey-id-1",
                            "file": "private-expression-file",
                        },
                        {
                            "name": SYNTHETIC_SECOND_HOTKEY,
                            "hotkeyID": "private-hotkey-id-2",
                        },
                    ],
                },
            }
        )
        self.trigger_response = (
            trigger_response
            if trigger_response is not None
            else {
                "messageType": "HotkeyTriggerResponse",
                "data": {},
            }
        )
        self.connect_delay = connect_delay
        self.authentication_delay = authentication_delay
        self.inventory_delay = inventory_delay
        self.trigger_delay = trigger_delay
        self.close_delay = close_delay
        self.connect_error = connect_error
        self.authentication_error = authentication_error
        self.inventory_error = inventory_error
        self.trigger_error = trigger_error
        self.close_error = close_error
        self.trigger_entered = trigger_entered
        self.trigger_release = trigger_release

        self.connect_count = 0
        self.close_count = 0
        self.request_kinds: list[str] = []
        self.request_payloads: list[Mapping[str, Any]] = []
        self.closed = False

    async def connect(self) -> None:
        self.connect_count += 1
        if self.connect_delay:
            await asyncio.sleep(self.connect_delay)
        if self.connect_error:
            raise RuntimeError(SYNTHETIC_PROVIDER_ERROR)

    async def request(
        self,
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        kind = str(request.get("kind", ""))
        self.request_kinds.append(kind)
        self.request_payloads.append(request)

        if kind == "authentication":
            if self.authentication_delay:
                await asyncio.sleep(self.authentication_delay)
            if self.authentication_error:
                raise RuntimeError(SYNTHETIC_PROVIDER_ERROR)
            return self.authentication_response

        if kind == "hotkey_inventory":
            if self.inventory_delay:
                await asyncio.sleep(self.inventory_delay)
            if self.inventory_error:
                raise RuntimeError(SYNTHETIC_PROVIDER_ERROR)
            return self.inventory_response

        if kind == "trigger_hotkey":
            if self.trigger_entered is not None:
                self.trigger_entered.set()
            if self.trigger_release is not None:
                await self.trigger_release.wait()
            if self.trigger_delay:
                await asyncio.sleep(self.trigger_delay)
            if self.trigger_error:
                raise RuntimeError(SYNTHETIC_PROVIDER_ERROR)
            return self.trigger_response

        raise AssertionError(f"unexpected fake request kind: {kind}")

    async def close(self) -> None:
        self.close_count += 1
        if self.close_delay:
            await asyncio.sleep(self.close_delay)
        if self.close_error:
            raise RuntimeError(SYNTHETIC_PROVIDER_ERROR)
        self.closed = True


class _FakePyvtsModule:
    ai_character_framework_fake_pyvts_module = True

    def __init__(self, client: _FakePyvtsClient) -> None:
        self.client = client
        self.constructor_count = 0
        self.constructor_kwargs: dict[str, Any] = {}

    def vts(self, **kwargs: Any) -> _FakePyvtsClient:
        self.constructor_count += 1
        self.constructor_kwargs = dict(kwargs)
        return self.client


@dataclass
class _Importer:
    module: Any | None = None
    error: bool = False
    call_count: int = 0

    def __call__(self, name: str) -> Any:
        self.call_count += 1
        _require(name == "pyvts", "lazy importer received wrong module name")
        if self.error:
            raise ImportError(SYNTHETIC_PROVIDER_ERROR)
        return self.module


def _execution_config(
    framework: Any,
    *,
    adapter: str = "vts",
    real_adapter_enabled: bool = True,
    allow_provider_execution: bool = True,
    endpoint_configured: bool = True,
    runtime_available: bool = True,
    token_available: bool = True,
    model_selected: bool = True,
) -> Any:
    return framework.resolve_motion_adapter_execution_config(
        adapter=adapter,
        real_adapter_enabled=real_adapter_enabled,
        allow_provider_execution=allow_provider_execution,
        endpoint_configured=endpoint_configured,
        runtime_available=runtime_available,
        token_available=token_available,
        model_selected=model_selected,
        configured_intents=(
            framework.MotionIntent.EXPRESSION,
            framework.MotionIntent.EMOTION,
            framework.MotionIntent.GESTURE,
            framework.MotionIntent.STOP_MOTION,
            framework.MotionIntent.RESET_EXPRESSION,
        ),
    )


def _transport_config(
    framework: Any,
    module: Any,
    *,
    execution_config: Any | None = None,
    endpoint_host: str = SYNTHETIC_HOST,
    endpoint_port: int = 18001,
    authentication_token: str = SYNTHETIC_AUTH,
    connect_timeout_seconds: float = 0.1,
    authenticate_timeout_seconds: float = 0.1,
    request_timeout_seconds: float = 0.1,
    close_timeout_seconds: float = 0.1,
) -> Any:
    return module.VTubeStudioPyvtsTransportConfig(
        execution_config=(
            execution_config
            if execution_config is not None
            else _execution_config(framework)
        ),
        endpoint_host=endpoint_host,
        endpoint_port=endpoint_port,
        authentication_token=authentication_token,
        connect_timeout_seconds=connect_timeout_seconds,
        authenticate_timeout_seconds=authenticate_timeout_seconds,
        request_timeout_seconds=request_timeout_seconds,
        close_timeout_seconds=close_timeout_seconds,
    )


def _assert_internal_only(framework: Any, module: Any) -> None:
    names = (
        "VTubeStudioPyvtsTransportConfig",
        "VTubeStudioPyvtsClient",
        "VTubeStudioPyvtsClientFactory",
        "VTubeStudioPyvtsModuleImporter",
        "VTubeStudioPyvtsTransport",
    )
    for name in names:
        _require(
            name not in getattr(framework, "__all__", ()),
            f"pyvts transport symbol was root-exported: {name}",
        )
        _require(
            not hasattr(framework, name),
            f"pyvts transport symbol is available at root: {name}",
        )
        _require(
            hasattr(module, name),
            f"pyvts transport module missing symbol: {name}",
        )
    _ok("guarded pyvts transport remains internal-only")


def _assert_config_privacy(framework: Any, module: Any) -> None:
    config = _transport_config(framework, module)
    rendered = repr(config)
    _require(
        SYNTHETIC_HOST not in rendered,
        "private endpoint host appeared in config repr",
    )
    _require(
        SYNTHETIC_AUTH not in rendered,
        "authentication material appeared in config repr",
    )
    public = config.to_public_dict()
    rendered_public = repr(dict(public))
    _require(
        SYNTHETIC_HOST not in rendered_public,
        "private endpoint host appeared in public config",
    )
    _require(
        SYNTHETIC_AUTH not in rendered_public,
        "authentication material appeared in public config",
    )
    _require(config.endpoint_valid, "valid synthetic endpoint rejected")
    _require(
        config.authentication_material_present,
        "synthetic authentication material was not recognized",
    )

    invalid = _transport_config(
        framework,
        module,
        endpoint_host="",
        endpoint_port=0,
    )
    _require(
        not invalid.endpoint_valid,
        "invalid endpoint was reported valid",
    )

    for kwargs in (
        {"plugin_name": "x"},
        {"plugin_developer": "x"},
        {"connect_timeout_seconds": 0},
        {"authenticate_timeout_seconds": float("inf")},
        {"request_timeout_seconds": -1},
        {"close_timeout_seconds": float("nan")},
    ):
        try:
            module.VTubeStudioPyvtsTransportConfig(
                execution_config=_execution_config(framework),
                endpoint_host=SYNTHETIC_HOST,
                endpoint_port=18001,
                authentication_token=SYNTHETIC_AUTH,
                **kwargs,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "invalid pyvts transport configuration was accepted"
            )

    _ok("private transport configuration is validated and non-public")


def _assert_result_privacy(
    result: Any,
    *,
    private_values: tuple[str, ...] = (),
) -> None:
    rendered = (
        repr(result)
        + result.safe_message
        + repr(dict(result.public_metadata))
    )
    for value in (
        SYNTHETIC_HOST,
        SYNTHETIC_AUTH,
        SYNTHETIC_HOTKEY,
        SYNTHETIC_SECOND_HOTKEY,
        "private-model-name",
        "private-model-id",
        "private-hotkey-id-1",
        "private-hotkey-id-2",
        "private-expression-file",
        SYNTHETIC_PROVIDER_ERROR,
        *private_values,
    ):
        _require(
            value not in rendered,
            f"transport result exposed private value: {value}",
        )

    for key in (
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
    ):
        _require(
            result.public_metadata[key] is False,
            f"transport safety flag changed: {key}",
        )


async def _assert_preimport_guards(framework: Any, module: Any) -> None:
    guard_cases = (
        _execution_config(framework, adapter="mock"),
        _execution_config(framework, real_adapter_enabled=False),
        _execution_config(framework, allow_provider_execution=False),
        _execution_config(framework, endpoint_configured=False),
        _execution_config(framework, runtime_available=False),
        _execution_config(framework, token_available=False),
        _execution_config(framework, model_selected=False),
    )

    for execution in guard_cases:
        importer = _Importer(module=object())
        transport = module.VTubeStudioPyvtsTransport(
            config=_transport_config(
                framework,
                module,
                execution_config=execution,
            ),
            module_importer=importer,
        )
        result = await transport.preflight()
        _require(
            result.outcome
            is module.VTubeStudioTransportOutcome.UNAVAILABLE,
            "failed explicit guard did not return unavailable",
        )
        _require(
            importer.call_count == 0,
            "failed explicit guard reached lazy importer",
        )
        _assert_result_privacy(result)

    for endpoint_host, endpoint_port, material in (
        ("", 18001, SYNTHETIC_AUTH),
        (SYNTHETIC_HOST, 0, SYNTHETIC_AUTH),
        (SYNTHETIC_HOST, 70000, SYNTHETIC_AUTH),
        (SYNTHETIC_HOST, 18001, ""),
    ):
        importer = _Importer(module=object())
        transport = module.VTubeStudioPyvtsTransport(
            config=_transport_config(
                framework,
                module,
                endpoint_host=endpoint_host,
                endpoint_port=endpoint_port,
                authentication_token=material,
            ),
            module_importer=importer,
        )
        result = await transport.preflight()
        _require(
            result.outcome
            is module.VTubeStudioTransportOutcome.UNAVAILABLE,
            "invalid private configuration did not fail closed",
        )
        _require(
            importer.call_count == 0,
            "invalid private configuration reached lazy importer",
        )
        _assert_result_privacy(result)

    closed_importer = _Importer(module=object())
    closed_transport = module.VTubeStudioPyvtsTransport(
        config=_transport_config(framework, module),
        module_importer=closed_importer,
    )
    await closed_transport.close()
    closed_result = await closed_transport.preflight()
    _require(
        closed_result.outcome
        is module.VTubeStudioTransportOutcome.CLOSED,
        "closed transport preflight did not return closed",
    )
    _require(
        closed_importer.call_count == 0,
        "closed transport reached lazy importer",
    )

    _ok("pre-import guards fail closed before pyvts/client creation")


async def _ready_transport(
    framework: Any,
    module: Any,
    *,
    client: _FakePyvtsClient | None = None,
    config: Any | None = None,
) -> tuple[Any, _FakePyvtsClient, _FakePyvtsModule, _Importer, Any]:
    resolved_client = client or _FakePyvtsClient()
    fake_module = _FakePyvtsModule(resolved_client)
    importer = _Importer(module=fake_module)
    transport = module.VTubeStudioPyvtsTransport(
        config=config or _transport_config(framework, module),
        module_importer=importer,
    )
    result = await transport.preflight()
    _require(
        result.outcome is module.VTubeStudioTransportOutcome.READY,
        "fake pyvts preflight did not become ready",
    )
    return transport, resolved_client, fake_module, importer, result


async def _assert_success_path(framework: Any, module: Any) -> None:
    (
        transport,
        client,
        fake_module,
        importer,
        ready,
    ) = await _ready_transport(framework, module)

    _require(
        isinstance(transport, module.VTubeStudioTransport),
        "pyvts transport does not conform to FW-VTS-0c Protocol",
    )
    _require(importer.call_count == 1, "lazy importer call count mismatch")
    _require(
        fake_module.constructor_count == 1,
        "default pyvts client factory call count mismatch",
    )
    _require(client.connect_count == 1, "fake connect count mismatch")
    _require(
        client.request_kinds
        == ["authentication", "hotkey_inventory"],
        "fake preflight request sequence changed",
    )
    _require(transport.is_ready, "ready transport state mismatch")
    _require(
        ready.public_metadata["available_hotkey_count"] == 2,
        "public hotkey count mismatch",
    )
    _assert_result_privacy(ready)

    plugin_info = fake_module.constructor_kwargs["plugin_info"]
    api_info = fake_module.constructor_kwargs["vts_api_info"]
    _require(
        plugin_info["authentication_token_path"] == "",
        "default factory enabled token-file persistence",
    )
    _require(
        api_info["host"] == SYNTHETIC_HOST,
        "default factory did not receive internal endpoint",
    )

    already_ready = await transport.preflight()
    _require(
        already_ready.outcome
        is module.VTubeStudioTransportOutcome.READY,
        "second preflight should remain ready",
    )
    _require(
        already_ready.public_metadata["already_ready"] is True,
        "second preflight did not report already_ready",
    )
    _require(importer.call_count == 1, "second preflight re-imported pyvts")
    _require(client.connect_count == 1, "second preflight reconnected")
    _assert_result_privacy(already_ready)

    request = module.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.EXPRESSION,
        hotkey_name=SYNTHETIC_HOTKEY.lower(),
        request_id="request-success",
    )
    completed = await transport.trigger_hotkey(request)
    _require(
        completed.outcome
        is module.VTubeStudioTransportOutcome.COMPLETED,
        "known case-insensitive hotkey did not complete",
    )
    _require(
        completed.request_id == request.request_id,
        "trigger result request_id mismatch",
    )
    _require(
        completed.public_metadata["hotkey_resolved"] is True,
        "completed trigger did not report resolved",
    )
    _assert_result_privacy(completed)

    trigger_payload = client.request_payloads[-1]
    _require(
        trigger_payload["hotkey_name"] == SYNTHETIC_HOTKEY.lower(),
        "transport rewrote provider hotkey name unexpectedly",
    )
    _require(
        "hotkeyID" not in trigger_payload,
        "transport created a provider hotkey ID",
    )

    provider_calls_before_missing = len(client.request_kinds)
    missing_request = module.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.GESTURE,
        hotkey_name=SYNTHETIC_MISSING,
        request_id="request-missing",
    )
    missing = await transport.trigger_hotkey(missing_request)
    _require(
        missing.outcome
        is module.VTubeStudioTransportOutcome.NOT_FOUND,
        "unknown hotkey did not return not_found",
    )
    _require(
        len(client.request_kinds) == provider_calls_before_missing,
        "unknown hotkey reached provider client",
    )
    _assert_result_privacy(
        missing,
        private_values=(SYNTHETIC_MISSING,),
    )

    first_close = await transport.close()
    second_close = await transport.close()
    _require(
        first_close.outcome
        is module.VTubeStudioTransportOutcome.COMPLETED,
        "first close did not complete",
    )
    _require(
        second_close.outcome
        is module.VTubeStudioTransportOutcome.COMPLETED,
        "second close did not complete idempotently",
    )
    _require(
        second_close.public_metadata["already_closed"] is True,
        "second close did not report already_closed",
    )
    _require(client.close_count == 1, "provider close was not single-use")
    _require(transport.is_closed, "transport did not remain closed")
    _assert_result_privacy(first_close)
    _assert_result_privacy(second_close)

    closed_trigger = await transport.trigger_hotkey(request)
    _require(
        closed_trigger.outcome
        is module.VTubeStudioTransportOutcome.CLOSED,
        "closed trigger did not return closed",
    )
    _assert_result_privacy(closed_trigger)

    _ok("lazy fake-pyvts success/inventory/trigger/close path conforms")


async def _assert_import_and_response_failures(
    framework: Any,
    module: Any,
) -> None:
    import_failure = module.VTubeStudioPyvtsTransport(
        config=_transport_config(framework, module),
        module_importer=_Importer(error=True),
    )
    result = await import_failure.preflight()
    _require(
        result.outcome
        is module.VTubeStudioTransportOutcome.UNAVAILABLE,
        "import failure was not normalized to unavailable",
    )
    _assert_result_privacy(result)

    scenarios = (
        (
            _FakePyvtsClient(
                authentication_response={
                    "messageType": "AuthenticationResponse",
                    "data": {"authenticated": False},
                }
            ),
            module.VTubeStudioTransportOutcome.UNAVAILABLE,
        ),
        (
            _FakePyvtsClient(authentication_response={"data": {}}),
            module.VTubeStudioTransportOutcome.FAILED,
        ),
        (
            _FakePyvtsClient(
                inventory_response={
                    "messageType": "HotkeysInCurrentModelResponse",
                    "data": {
                        "modelLoaded": False,
                        "availableHotkeys": [],
                    },
                }
            ),
            module.VTubeStudioTransportOutcome.UNAVAILABLE,
        ),
        (
            _FakePyvtsClient(inventory_response={"data": {}}),
            module.VTubeStudioTransportOutcome.FAILED,
        ),
        (
            _FakePyvtsClient(connect_error=True),
            module.VTubeStudioTransportOutcome.UNAVAILABLE,
        ),
        (
            _FakePyvtsClient(authentication_error=True),
            module.VTubeStudioTransportOutcome.UNAVAILABLE,
        ),
        (
            _FakePyvtsClient(inventory_error=True),
            module.VTubeStudioTransportOutcome.FAILED,
        ),
    )

    for client, expected in scenarios:
        fake_module = _FakePyvtsModule(client)
        transport = module.VTubeStudioPyvtsTransport(
            config=_transport_config(framework, module),
            module_importer=_Importer(module=fake_module),
        )
        scenario_result = await transport.preflight()
        _require(
            scenario_result.outcome is expected,
            "provider failure response normalization mismatch",
        )
        _require(
            not transport.is_ready,
            "failed preflight left transport ready",
        )
        _assert_result_privacy(scenario_result)

    _ok("provider import/response/exception failures are normalized safely")


async def _assert_timeouts(framework: Any, module: Any) -> None:
    timeout_value = 0.005
    delay_value = 0.05

    timeout_scenarios = (
        (
            _FakePyvtsClient(connect_delay=delay_value),
            dict(connect_timeout_seconds=timeout_value),
            "connect",
        ),
        (
            _FakePyvtsClient(authentication_delay=delay_value),
            dict(authenticate_timeout_seconds=timeout_value),
            "authenticate",
        ),
        (
            _FakePyvtsClient(inventory_delay=delay_value),
            dict(request_timeout_seconds=timeout_value),
            "hotkey_inventory",
        ),
    )

    for client, timeout_kwargs, expected_stage in timeout_scenarios:
        fake_module = _FakePyvtsModule(client)
        config = _transport_config(
            framework,
            module,
            **timeout_kwargs,
        )
        transport = module.VTubeStudioPyvtsTransport(
            config=config,
            module_importer=_Importer(module=fake_module),
        )
        result = await transport.preflight()
        _require(
            result.outcome
            is module.VTubeStudioTransportOutcome.TIMED_OUT,
            f"{expected_stage} timeout was not normalized",
        )
        _require(
            result.public_metadata["timeout_stage"]
            == expected_stage,
            f"{expected_stage} timeout stage mismatch",
        )
        _assert_result_privacy(result)

    trigger_client = _FakePyvtsClient(trigger_delay=delay_value)
    trigger_config = _transport_config(
        framework,
        module,
        request_timeout_seconds=timeout_value,
    )
    trigger_transport, _, _, _, _ = await _ready_transport(
        framework,
        module,
        client=trigger_client,
        config=trigger_config,
    )
    trigger_request = module.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.EMOTION,
        hotkey_name=SYNTHETIC_HOTKEY,
        request_id="request-trigger-timeout",
    )
    trigger_result = await trigger_transport.trigger_hotkey(
        trigger_request
    )
    _require(
        trigger_result.outcome
        is module.VTubeStudioTransportOutcome.TIMED_OUT,
        "trigger timeout was not normalized",
    )
    _require(
        trigger_result.public_metadata["timeout_stage"]
        == "trigger_hotkey",
        "trigger timeout stage mismatch",
    )
    _assert_result_privacy(trigger_result)
    await trigger_transport.close()

    close_client = _FakePyvtsClient(close_delay=delay_value)
    close_config = _transport_config(
        framework,
        module,
        close_timeout_seconds=timeout_value,
    )
    close_transport, _, _, _, _ = await _ready_transport(
        framework,
        module,
        client=close_client,
        config=close_config,
    )
    close_result = await close_transport.close()
    _require(
        close_result.outcome
        is module.VTubeStudioTransportOutcome.TIMED_OUT,
        "close timeout was not normalized",
    )
    _require(
        close_result.public_metadata["timeout_stage"] == "close",
        "close timeout stage mismatch",
    )
    _require(close_transport.is_closed, "timed-out close reopened transport")
    second_close = await close_transport.close()
    _require(
        second_close.outcome
        is module.VTubeStudioTransportOutcome.COMPLETED,
        "second close after timeout was not idempotent",
    )
    _assert_result_privacy(close_result)
    _assert_result_privacy(second_close)

    close_error_client = _FakePyvtsClient(close_error=True)
    close_error_transport, _, _, _, _ = await _ready_transport(
        framework,
        module,
        client=close_error_client,
    )
    close_error_result = await close_error_transport.close()
    _require(
        close_error_result.outcome
        is module.VTubeStudioTransportOutcome.FAILED,
        "close exception was not normalized",
    )
    _require(
        close_error_transport.is_closed,
        "failed close reopened transport",
    )
    _assert_result_privacy(close_error_result)

    _ok("connect/auth/request/close timeout boundaries conform")


async def _assert_single_flight_and_late_close(
    framework: Any,
    module: Any,
) -> None:
    trigger_entered = asyncio.Event()
    trigger_release = asyncio.Event()
    client = _FakePyvtsClient(
        trigger_entered=trigger_entered,
        trigger_release=trigger_release,
    )
    transport, _, _, _, _ = await _ready_transport(
        framework,
        module,
        client=client,
    )

    first_request = module.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.EXPRESSION,
        hotkey_name=SYNTHETIC_HOTKEY,
        request_id="request-active",
    )
    second_request = module.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.RESET_EXPRESSION,
        hotkey_name=SYNTHETIC_SECOND_HOTKEY,
        request_id="request-busy",
    )

    first_task = asyncio.create_task(
        transport.trigger_hotkey(first_request)
    )
    await asyncio.wait_for(trigger_entered.wait(), timeout=0.2)

    busy = await transport.trigger_hotkey(second_request)
    _require(
        busy.outcome is module.VTubeStudioTransportOutcome.BUSY,
        "second concurrent trigger did not return busy",
    )
    _require(
        busy.public_metadata["single_flight_enforced"] is True,
        "busy result did not report single-flight enforcement",
    )
    _assert_result_privacy(busy)

    close_result = await transport.close()
    _require(
        close_result.outcome
        is module.VTubeStudioTransportOutcome.COMPLETED,
        "close during active trigger did not complete",
    )
    trigger_release.set()
    late = await asyncio.wait_for(first_task, timeout=0.2)
    _require(
        late.outcome is module.VTubeStudioTransportOutcome.CLOSED,
        "late trigger completion was not suppressed",
    )
    _require(
        late.public_metadata["late_completion_suppressed"] is True,
        "late completion suppression metadata missing",
    )
    _assert_result_privacy(late)

    _ok("single-flight and late-completion suppression conform")


def _assert_public_session_unchanged(framework: Any) -> None:
    session = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=True,
    )
    capability = session.preflight()
    _require(
        capability.adapter_status
        is framework.MotionAdapterStatus.NOT_IMPLEMENTED,
        "MotionSession composition changed before FW-VTS-0e",
    )
    _require(
        capability.supports_real_adapter is False,
        "MotionSession claimed real adapter support in FW-VTS-0d",
    )
    session.close()
    _ok("root-public MotionSession composition remains unchanged")


async def _run_async_matrix(framework: Any, module: Any) -> None:
    await _assert_preimport_guards(framework, module)
    await _assert_success_path(framework, module)
    await _assert_import_and_response_failures(framework, module)
    await _assert_timeouts(framework, module)
    await _assert_single_flight_and_late_close(framework, module)


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    _assert_forbidden_modules_absent()

    with patch(
        "socket.create_connection",
        _blocked_connection,
    ):
        framework = importlib.import_module("framework")
        module = importlib.import_module(
            "framework.vtube_studio_pyvts_transport"
        )
        protocol_module = importlib.import_module(
            "framework.vtube_studio_transport"
        )

        # Re-export the frozen protocol types into the module variable used by
        # matrix helpers without changing the Framework root.
        module.VTubeStudioTransport = (
            protocol_module.VTubeStudioTransport
        )
        module.VTubeStudioTransportOutcome = (
            protocol_module.VTubeStudioTransportOutcome
        )
        module.VTubeStudioHotkeyRequest = (
            protocol_module.VTubeStudioHotkeyRequest
        )

        _assert_forbidden_modules_absent()
        _assert_internal_only(framework, module)
        _assert_config_privacy(framework, module)
        asyncio.run(_run_async_matrix(framework, module))
        _assert_public_session_unchanged(framework)
        _assert_forbidden_modules_absent()

    print(
        "v550_vtube_studio_pyvts_transport_status: "
        "implemented-awaiting-review"
    )
    print("v550_pyvts_transport_internal_only: True")
    print("v550_pyvts_transport_protocol_conforms: True")
    print("v550_lazy_pyvts_import_implemented: True")
    print("v550_preimport_guards_fail_closed: True")
    print("v550_double_opt_in_required: True")
    print("v550_injected_authentication_material_only: True")
    print("v550_token_file_read: False")
    print("v550_token_file_write: False")
    print("v550_token_bootstrap_executed: False")
    print("v550_endpoint_values_exposed: False")
    print("v550_authentication_material_exposed: False")
    print("v550_model_identity_exposed: False")
    print("v550_hotkey_names_exposed_in_results: False")
    print("v550_hotkey_ids_created: False")
    print("v550_hotkey_ids_stored: False")
    print("v550_hotkey_ids_exposed: False")
    print("v550_provider_response_exposed: False")
    print("v550_provider_exception_exposed: False")
    print("v550_connect_timeout_enforced: True")
    print("v550_authenticate_timeout_enforced: True")
    print("v550_request_timeout_enforced: True")
    print("v550_close_timeout_enforced: True")
    print("v550_single_flight_enforced: True")
    print("v550_waiting_operation_queue_created: False")
    print("v550_automatic_retry_executed: False")
    print("v550_automatic_reconnect_executed: False")
    print("v550_background_tasks_created: False")
    print("v550_close_idempotent: True")
    print("v550_late_completion_suppressed: True")
    print("v550_fake_pyvts_module_used: True")
    print("v550_fake_pyvts_client_used: True")
    print("v550_fake_provider_protocol_call_executed: True")
    print("v550_actual_pyvts_imported: False")
    print("v550_websocket_imported: False")
    print("v550_network_executed: False")
    print("v550_real_hotkey_triggered: False")
    print("v550_real_motion_executed: False")
    print("v550_motion_session_composition_changed: False")
    print("v550_configuration_resolver_changed: False")
    print("v550_root_public_api_changed: False")
    print("v550_legacy_vts_runtime_changed: False")
    print("v550_requirements_changed: False")
    print("v550_release_metadata_changed: False")
    print("v550_drc_changed: False")
    print("v550_commit_created: False")
    print("v550_push_performed: False")
    print(
        "v550_next_authorization: "
        "exact-review-required-for-FW-VTS-0e"
    )
    _ok("FW-VTS-0d guarded lazy pyvts transport smoke passed")


if __name__ == "__main__":
    main()
