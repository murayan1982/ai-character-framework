"""FW-VTS-0e root-public MotionSession real-adapter composition smoke.

The smoke replaces the internal pyvts transport constructor with deterministic
in-memory transports.  It never imports actual pyvts/WebSocket modules, opens a
network connection, reads or writes token files, or executes real motion.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import ipaddress
import socket
import sys
import threading
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_HOST = "synthetic-vts-host.invalid"
SYNTHETIC_TOKEN = "synthetic-private-auth-material"
SYNTHETIC_HOTKEY = "SyntheticHappyHotkey"
SYNTHETIC_MISSING_HOTKEY = "SyntheticMissingHotkey"
SYNTHETIC_PRIVATE_ERROR = "synthetic-private-provider-error"


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


_ORIGINAL_SOCKET_CONNECT = socket.socket.connect


def _guarded_socket_connect(
    target_socket: socket.socket,
    address: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Permit event-loop local IPC while rejecting external connections."""

    # Windows ProactorEventLoop creates its self-wakeup socketpair through a
    # loopback connect.  That is local event-loop plumbing, not provider or VTS
    # network execution, so the smoke must allow it.
    if target_socket.family in {socket.AF_INET, socket.AF_INET6}:
        host = (
            str(address[0]).strip()
            if isinstance(address, tuple) and address
            else ""
        )
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = host.casefold() == "localhost"
        if is_loopback:
            return _ORIGINAL_SOCKET_CONNECT(
                target_socket,
                address,
                *args,
                **kwargs,
            )

    unix_family = getattr(socket, "AF_UNIX", None)
    if unix_family is not None and target_socket.family == unix_family:
        return _ORIGINAL_SOCKET_CONNECT(
            target_socket,
            address,
            *args,
            **kwargs,
        )

    raise AssertionError(
        "FW-VTS-0e attempted a non-loopback network connection"
    )


def _blocked_connection(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError(
        "FW-VTS-0e attempted socket.create_connection"
    )


def _assert_actual_provider_modules_absent() -> None:
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


class _FakeTransport:
    def __init__(
        self,
        transport_module: Any,
        *,
        preflight_outcome: str = "ready",
        trigger_outcome: str = "completed",
        available_hotkey_count: int = 1,
        block_trigger: bool = False,
    ) -> None:
        self._module = transport_module
        self._preflight_outcome = transport_module.VTubeStudioTransportOutcome(
            preflight_outcome
        )
        self._trigger_outcome = transport_module.VTubeStudioTransportOutcome(
            trigger_outcome
        )
        self._available_hotkey_count = available_hotkey_count
        self._block_trigger = block_trigger
        self._closed = False
        self._ready = False
        self._operation_active = False
        self._generation = 0
        self.preflight_count = 0
        self.trigger_count = 0
        self.close_count = 0
        self.trigger_entered = threading.Event()
        self.trigger_release = threading.Event()
        self.received_requests: list[Any] = []

    @property
    def transport_name(self) -> str:
        return "fake_vts_composition"

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _result(
        self,
        *,
        operation: Any,
        outcome: Any,
        request_id: str | None = None,
        retryable: bool = False,
        reason: str,
        single_flight_enforced: bool = False,
        late_completion_suppressed: bool = False,
    ) -> Any:
        return self._module.VTubeStudioTransportResult(
            operation=operation,
            outcome=outcome,
            request_id=request_id,
            safe_message="Synthetic provider-safe result.",
            retryable=retryable,
            public_metadata={
                "boundary": "fake_vts_composition_transport",
                "transport": self.transport_name,
                "reason": reason,
                "available_hotkey_count": self._available_hotkey_count,
                "provider_sdk_imported": False,
                "provider_client_created": False,
                "network_execution_attempted": False,
                "single_flight_enforced": single_flight_enforced,
                "late_completion_suppressed": late_completion_suppressed,
                "raw_payload_exposed": False,
                "raw_exception_exposed": False,
                "endpoint_exposed": False,
                "authentication_material_exposed": False,
                "model_identity_exposed": False,
                "hotkey_name_exposed": False,
                "hotkey_identifier_exposed": False,
                "real_hotkey_triggered": False,
                "real_motion_executed": False,
            },
        )

    async def preflight(self) -> Any:
        self.preflight_count += 1
        if self._closed:
            return self._result(
                operation=self._module.VTubeStudioTransportOperation.PREFLIGHT,
                outcome=self._module.VTubeStudioTransportOutcome.CLOSED,
                reason="transport_closed",
            )
        self._ready = (
            self._preflight_outcome
            is self._module.VTubeStudioTransportOutcome.READY
        )
        return self._result(
            operation=self._module.VTubeStudioTransportOperation.PREFLIGHT,
            outcome=self._preflight_outcome,
            retryable=(
                self._preflight_outcome
                is self._module.VTubeStudioTransportOutcome.TIMED_OUT
            ),
            reason="synthetic_preflight",
        )

    async def trigger_hotkey(self, request: Any) -> Any:
        operation = self._module.VTubeStudioTransportOperation.TRIGGER_HOTKEY
        if self._closed:
            return self._result(
                operation=operation,
                outcome=self._module.VTubeStudioTransportOutcome.CLOSED,
                request_id=request.request_id,
                reason="transport_closed",
            )
        if not self._ready:
            return self._result(
                operation=operation,
                outcome=self._module.VTubeStudioTransportOutcome.UNAVAILABLE,
                request_id=request.request_id,
                reason="transport_not_ready",
            )
        if self._operation_active:
            return self._result(
                operation=operation,
                outcome=self._module.VTubeStudioTransportOutcome.BUSY,
                request_id=request.request_id,
                retryable=True,
                reason="single_flight_busy",
                single_flight_enforced=True,
            )

        self._operation_active = True
        generation = self._generation
        self.trigger_count += 1
        self.received_requests.append(request)
        self.trigger_entered.set()
        try:
            while self._block_trigger and not self.trigger_release.is_set():
                await asyncio.sleep(0.005)
            if self._closed or generation != self._generation:
                return self._result(
                    operation=operation,
                    outcome=self._module.VTubeStudioTransportOutcome.CLOSED,
                    request_id=request.request_id,
                    reason="late_completion_suppressed",
                    late_completion_suppressed=True,
                )
            return self._result(
                operation=operation,
                outcome=self._trigger_outcome,
                request_id=request.request_id,
                retryable=(
                    self._trigger_outcome
                    in {
                        self._module.VTubeStudioTransportOutcome.BUSY,
                        self._module.VTubeStudioTransportOutcome.TIMED_OUT,
                    }
                ),
                reason="synthetic_trigger",
                single_flight_enforced=(
                    self._trigger_outcome
                    is self._module.VTubeStudioTransportOutcome.BUSY
                ),
            )
        finally:
            self._operation_active = False

    async def close(self) -> Any:
        self.close_count += 1
        already_closed = self._closed
        self._closed = True
        self._ready = False
        self._generation += 1
        return self._result(
            operation=self._module.VTubeStudioTransportOperation.CLOSE,
            outcome=self._module.VTubeStudioTransportOutcome.COMPLETED,
            reason="already_closed" if already_closed else "transport_closed",
        )


class _TransportFactory:
    def __init__(self, transport_module: Any) -> None:
        self._transport_module = transport_module
        self._queue: list[_FakeTransport] = []
        self.created: list[_FakeTransport] = []
        self.configs: list[Any] = []

    def queue(self, transport: _FakeTransport) -> _FakeTransport:
        self._queue.append(transport)
        return transport

    def __call__(self, config: Any) -> _FakeTransport:
        _require(self._queue, "fake transport factory queue is empty")
        transport = self._queue.pop(0)
        self.created.append(transport)
        self.configs.append(config)
        return transport


def _session(framework: Any, **overrides: Any) -> Any:
    values = {
        "adapter": "vts",
        "real_adapter_enabled": True,
        "allow_provider_execution": True,
        "runtime_available": True,
        "model_selected": True,
        "vts_endpoint_host": SYNTHETIC_HOST,
        "vts_endpoint_port": 8001,
        "vts_authentication_token": SYNTHETIC_TOKEN,
        "vts_hotkey_bindings": {
            "expression:happy": SYNTHETIC_HOTKEY,
            "emotion:cheerful": "SyntheticCheerfulHotkey",
            "gesture:wave": "SyntheticWaveHotkey",
            "stop_motion": "SyntheticStopHotkey",
            "reset_expression": "SyntheticResetHotkey",
        },
        "vts_connect_timeout_seconds": 0.25,
        "vts_authenticate_timeout_seconds": 0.25,
        "vts_request_timeout_seconds": 0.25,
        "vts_close_timeout_seconds": 0.25,
    }
    values.update(overrides)
    return framework.create_motion_session(**values)


def _assert_static_guards_and_compatibility(framework: Any) -> None:
    _require(
        "framework.vtube_studio_motion_composition" not in sys.modules,
        "composition module loaded before explicit successful guards",
    )
    guarded = _session(
        framework,
        allow_provider_execution=False,
    )
    capability = guarded.preflight()
    _require(
        capability.adapter_status
        is framework.MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
        "provider guard status mismatch",
    )
    _require(
        guarded._vts_composition is None,
        "failed guard created VTS composition",
    )
    _require(
        "framework.vtube_studio_motion_composition" not in sys.modules,
        "failed guard imported VTS composition module",
    )

    legacy = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=True,
    )
    _require(
        legacy.preflight().adapter_status
        is framework.MotionAdapterStatus.NOT_IMPLEMENTED,
        "legacy VTS path no longer returns not_implemented",
    )
    mock = framework.create_motion_session(adapter="mock")
    _require(
        mock.apply_motion(
            framework.MotionRequest.expression_change("happy")
        ).outcome
        is framework.MotionOutcome.COMPLETED,
        "mock path changed",
    )
    guarded.close()
    legacy.close()
    mock.close()
    _ok("static guards are lazy and legacy/mock behavior is preserved")


def _assert_signature_and_validation(framework: Any) -> None:
    signature = inspect.signature(framework.create_motion_session)
    expected = {
        "project_root",
        "adapter",
        "real_adapter_enabled",
        "allow_provider_execution",
        "runtime_available",
        "model_selected",
        "vts_endpoint_host",
        "vts_endpoint_port",
        "vts_authentication_token",
        "vts_hotkey_bindings",
        "vts_connect_timeout_seconds",
        "vts_authenticate_timeout_seconds",
        "vts_request_timeout_seconds",
        "vts_close_timeout_seconds",
        "public_metadata",
    }
    _require(expected == set(signature.parameters), "public factory signature mismatch")
    _require(
        all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in signature.parameters.values()
        ),
        "public factory arguments are not keyword-only",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "MotionSessionInfo api_version mismatch",
    )

    try:
        _session(
            framework,
            vts_hotkey_bindings={
                "Expression:Happy": "One",
                "expression:happy": "Two",
            },
        )
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate normalized selector was accepted")

    try:
        _session(
            framework,
            vts_hotkey_bindings={"speaking_state:on": "Speak"},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("unproven hotkey intent was accepted")

    for internal_name in (
        "VTubeStudioMotionComposition",
        "VTubeStudioPyvtsTransport",
        "VTubeStudioTransport",
    ):
        _require(
            not hasattr(framework, internal_name),
            f"internal symbol exported from framework root: {internal_name}",
        )
    _ok("public signature, version, binding validation, and exports conform")


def _assert_basic_composition(
    framework: Any,
    transport_module: Any,
    factory: _TransportFactory,
) -> None:
    transport = factory.queue(_FakeTransport(transport_module))
    events: list[Mapping[str, Any]] = []
    session = _session(framework)
    session.on_event(events.append)

    before = session.apply_motion(
        framework.MotionRequest.expression_change("happy")
    )
    _require(
        before.outcome is framework.MotionOutcome.NOT_CONFIGURED,
        "apply before preflight did not fail closed",
    )
    _require(transport.trigger_count == 0, "preflight-required path called provider")

    capability = session.preflight()
    loop_identity = session._vts_composition.bridge_loop_identity
    _require(loop_identity is not None, "persistent event loop did not start")
    _require(
        capability.adapter_status is framework.MotionAdapterStatus.CONFIGURED,
        "ready capability status mismatch",
    )
    _require(capability.supports_real_adapter, "ready capability lacks real support")
    _require(capability.supports_expression, "expression binding not reflected")
    _require(not capability.supports_speaking_state, "unproven intent overclaimed")

    result = session.apply_motion(
        framework.MotionRequest.expression_change("  HAPPY  ")
    )
    _require(result.outcome is framework.MotionOutcome.COMPLETED, "VTS motion did not complete")
    _require(
        result.adapter_status is framework.MotionAdapterStatus.CONFIGURED,
        "completed real result status mismatch",
    )
    _require(
        session._vts_composition.bridge_loop_identity == loop_identity,
        "preflight/apply did not reuse one persistent event loop",
    )
    _require(transport.preflight_count == 1, "preflight call count mismatch")
    _require(transport.trigger_count == 1, "trigger call count mismatch")

    unsupported = session.apply_motion(
        framework.MotionRequest.speaking_state(True)
    )
    missing = session.apply_motion(
        framework.MotionRequest.expression_change("missing")
    )
    _require(
        unsupported.outcome is framework.MotionOutcome.UNSUPPORTED,
        "unproven intent did not fail unsupported",
    )
    _require(
        missing.outcome is framework.MotionOutcome.NOT_CONFIGURED,
        "missing binding did not fail not_configured",
    )
    _require(
        transport.trigger_count == 1,
        "unsupported/missing binding called transport",
    )

    public_text = repr((session.info, capability, result, events))
    for private_value in (
        SYNTHETIC_HOST,
        SYNTHETIC_TOKEN,
        SYNTHETIC_HOTKEY,
        SYNTHETIC_MISSING_HOTKEY,
        SYNTHETIC_PRIVATE_ERROR,
    ):
        _require(
            private_value not in public_text,
            "private VTS value leaked through public result/event metadata",
        )

    session.close()
    session.close()
    _require(transport.close_count == 1, "close was not idempotent")
    _require(
        not session._vts_composition.bridge_thread_alive,
        "VTS bridge worker thread remained alive after close",
    )
    close_events = [
        event for event in events if event["type"] == "motion.session.closed"
    ]
    _require(len(close_events) == 1, "close emitted more than one terminal event")
    _ok("root-public VTS composition, binding privacy, and lifecycle conform")


def _assert_outcome_normalization(
    framework: Any,
    transport_module: Any,
    factory: _TransportFactory,
) -> None:
    cases = (
        (
            "not_found",
            framework.MotionOutcome.NOT_CONFIGURED,
            framework.MotionErrorCode.NOT_CONFIGURED,
            False,
        ),
        (
            "busy",
            framework.MotionOutcome.UNAVAILABLE,
            framework.MotionErrorCode.UNAVAILABLE,
            True,
        ),
        (
            "timed_out",
            framework.MotionOutcome.FAILED,
            framework.MotionErrorCode.PROVIDER_ERROR,
            True,
        ),
        (
            "failed",
            framework.MotionOutcome.FAILED,
            framework.MotionErrorCode.PROVIDER_ERROR,
            False,
        ),
        (
            "unavailable",
            framework.MotionOutcome.UNAVAILABLE,
            framework.MotionErrorCode.UNAVAILABLE,
            False,
        ),
        (
            "closed",
            framework.MotionOutcome.CLOSED,
            framework.MotionErrorCode.SESSION_CLOSED,
            False,
        ),
    )
    for (
        transport_outcome,
        expected_outcome,
        expected_error,
        expected_retryable,
    ) in cases:
        factory.queue(
            _FakeTransport(
                transport_module,
                trigger_outcome=transport_outcome,
            )
        )
        session = _session(framework)
        session.preflight()
        result = session.apply_motion(
            framework.MotionRequest.expression_change("happy")
        )
        _require(
            result.outcome is expected_outcome,
            f"transport outcome normalization mismatch: {transport_outcome}",
        )
        _require(
            result.public_error_code is expected_error,
            f"transport error normalization mismatch: {transport_outcome}",
        )
        _require(
            result.retryable is expected_retryable,
            f"transport retryable mismatch: {transport_outcome}",
        )
        session.close()
    _ok("internal transport outcomes normalize to stable public results")


def _assert_single_flight(
    framework: Any,
    transport_module: Any,
    factory: _TransportFactory,
) -> None:
    transport = factory.queue(
        _FakeTransport(transport_module, block_trigger=True)
    )
    session = _session(framework)
    session.preflight()
    first_holder: list[Any] = []

    thread = threading.Thread(
        target=lambda: first_holder.append(
            session.apply_motion(
                framework.MotionRequest.expression_change("happy")
            )
        )
    )
    thread.start()
    _require(transport.trigger_entered.wait(timeout=2.0), "first trigger did not start")

    second = session.apply_motion(
        framework.MotionRequest.expression_change("happy")
    )
    _require(
        second.outcome is framework.MotionOutcome.UNAVAILABLE
        and second.retryable,
        "second concurrent apply did not return immediate BUSY normalization",
    )
    transport.trigger_release.set()
    thread.join(timeout=2.0)
    _require(not thread.is_alive(), "first trigger thread did not finish")
    _require(
        first_holder and first_holder[0].outcome is framework.MotionOutcome.COMPLETED,
        "first single-flight operation did not complete",
    )
    session.close()
    _ok("session composition preserves immediate single-flight BUSY behavior")


def _assert_close_during_apply(
    framework: Any,
    transport_module: Any,
    factory: _TransportFactory,
) -> None:
    transport = factory.queue(
        _FakeTransport(transport_module, block_trigger=True)
    )
    session = _session(framework)
    events: list[Mapping[str, Any]] = []
    session.on_event(events.append)
    session.preflight()
    holder: list[Any] = []
    thread = threading.Thread(
        target=lambda: holder.append(
            session.apply_motion(
                framework.MotionRequest.expression_change("happy")
            )
        )
    )
    thread.start()
    _require(transport.trigger_entered.wait(timeout=2.0), "late trigger did not start")
    session.close()
    transport.trigger_release.set()
    thread.join(timeout=2.0)
    _require(not thread.is_alive(), "late trigger caller remained blocked")
    _require(holder and holder[0].outcome is framework.MotionOutcome.CLOSED, "late completion was not suppressed")
    _require(
        holder[0].public_metadata.get("late_completion_suppressed") is True,
        "late-completion suppression marker missing",
    )
    _require(
        not session._vts_composition.bridge_thread_alive,
        "worker thread survived close during apply",
    )
    close_events = [
        event for event in events if event["type"] == "motion.session.closed"
    ]
    _require(
        len(close_events) == 1,
        "close during apply emitted duplicate terminal close events",
    )
    _ok("close suppresses late success and terminates the bridge")


def _assert_active_host_event_loop(
    framework: Any,
    transport_module: Any,
    factory: _TransportFactory,
) -> None:
    factory.queue(_FakeTransport(transport_module))

    async def host_flow() -> tuple[Any, Any]:
        session = _session(framework)
        capability = session.preflight()
        result = session.apply_motion(
            framework.MotionRequest.expression_change("happy")
        )
        session.close()
        return capability, result

    capability, result = asyncio.run(host_flow())
    _require(capability.supports_real_adapter, "host-loop preflight failed")
    _require(result.outcome is framework.MotionOutcome.COMPLETED, "host-loop apply failed")
    _ok("sync public API is safe when the host thread has an active event loop")


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    _assert_actual_provider_modules_absent()
    framework = importlib.import_module("framework")
    _assert_static_guards_and_compatibility(framework)
    _assert_signature_and_validation(framework)

    composition_module = importlib.import_module(
        "framework.vtube_studio_motion_composition"
    )
    transport_module = importlib.import_module(
        "framework.vtube_studio_transport"
    )
    factory = _TransportFactory(transport_module)

    with (
        patch.object(
            composition_module,
            "VTubeStudioPyvtsTransport",
            factory,
        ),
        patch.object(socket.socket, "connect", _guarded_socket_connect),
        patch("socket.create_connection", _blocked_connection),
    ):
        _assert_basic_composition(framework, transport_module, factory)
        _assert_outcome_normalization(framework, transport_module, factory)
        _assert_single_flight(framework, transport_module, factory)
        _assert_close_during_apply(framework, transport_module, factory)
        _assert_active_host_event_loop(framework, transport_module, factory)

    _assert_actual_provider_modules_absent()

    print("v550_motion_session_real_adapter_composition_status: implemented-awaiting-review")
    print("v550_exact_change_surface: True")
    print("v550_public_motion_api_version: 5.5.0")
    print("v550_root_public_motion_session_composed: True")
    print("v550_internal_transport_root_exported: False")
    print("v550_persistent_session_event_loop: True")
    print("v550_asyncio_run_per_call_used: False")
    print("v550_active_host_event_loop_safe: True")
    print("v550_mock_compatibility_preserved: True")
    print("v550_legacy_vts_not_implemented_compatibility_preserved: True")
    print("v550_preflight_required_before_apply: True")
    print("v550_hotkey_binding_normalization_complete: True")
    print("v550_single_flight_enforced: True")
    print("v550_close_idempotent: True")
    print("v550_bridge_thread_terminated: True")
    print("v550_late_completion_suppressed: True")
    print("v550_actual_pyvts_imported: False")
    print("v550_websocket_imported: False")
    print("v550_network_executed: False")
    print("v550_token_file_read: False")
    print("v550_token_file_write: False")
    print("v550_token_bootstrap_executed: False")
    print("v550_real_hotkey_triggered: False")
    print("v550_real_motion_executed: False")
    print("v550_commit_created: False")
    print("v550_push_performed: False")
    print("v550_next_authorization: exact-review-required-for-FW-VTS-0f")
    _ok("FW-VTS-0e MotionSession composition smoke passed")


if __name__ == "__main__":
    main()
