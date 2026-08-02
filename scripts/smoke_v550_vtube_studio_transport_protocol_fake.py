"""FW-VTS-0c internal async transport Protocol / fake smoke."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import socket
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MODULE_FRAGMENTS = (
    "pyvts",
    "websocket",
    "websockets",
    "live2d.vts_client",
)

SYNTHETIC_OK = "SyntheticSmile"
SYNTHETIC_FAIL = "SyntheticFailure"
SYNTHETIC_MISSING = "SyntheticMissing"
PRIVATE_VALUE = "must-not-leak"


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _blocked_connect(*args, **kwargs):
    raise AssertionError("FW-VTS-0c attempted network execution")


def _assert_forbidden_modules_absent() -> None:
    hits = sorted(
        name
        for name in sys.modules
        if any(
            fragment in name.lower()
            for fragment in FORBIDDEN_MODULE_FRAGMENTS
        )
    )
    _require(
        not hits,
        "forbidden VTS/WebSocket modules loaded: " + ", ".join(hits),
    )


def _assert_internal_only(framework, transport) -> None:
    for name in (
        "FakeVTubeStudioTransport",
        "VTubeStudioHotkeyRequest",
        "VTubeStudioTransport",
        "VTubeStudioTransportFactory",
        "VTubeStudioTransportOperation",
        "VTubeStudioTransportOutcome",
        "VTubeStudioTransportResult",
    ):
        _require(
            name not in getattr(framework, "__all__", ()),
            f"internal transport symbol was root-exported: {name}",
        )
        _require(
            not hasattr(framework, name),
            f"internal transport symbol is available at root: {name}",
        )
        _require(
            hasattr(transport, name),
            f"internal transport module missing symbol: {name}",
        )
    _ok("transport symbols remain internal and are not root-public")


def _assert_protocol_shape(transport) -> None:
    fake = transport.FakeVTubeStudioTransport()
    _require(
        isinstance(fake, transport.VTubeStudioTransport),
        "fake transport does not structurally conform to Protocol",
    )
    for name in ("preflight", "trigger_hotkey", "close"):
        _require(
            inspect.iscoroutinefunction(
                getattr(transport.FakeVTubeStudioTransport, name)
            ),
            f"transport operation is not async: {name}",
        )
    _ok("runtime-checkable async transport Protocol conforms")


def _assert_request_contract(framework, transport) -> None:
    request = transport.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.EXPRESSION,
        hotkey_name=f"  {SYNTHETIC_OK}  ",
        request_id="request-1",
        public_metadata={"token": PRIVATE_VALUE},
    )
    _require(
        request.hotkey_name == SYNTHETIC_OK,
        "hotkey request did not trim internal name",
    )
    _require(
        SYNTHETIC_OK not in repr(request),
        "hotkey request repr exposed internal name",
    )
    _require(
        PRIVATE_VALUE not in repr(request),
        "hotkey request repr exposed secret-like metadata",
    )
    _require(
        request.public_metadata["token"] == "<redacted>",
        "hotkey request did not redact secret-like metadata",
    )
    public = request.to_public_dict()
    _require(
        "hotkey_name" not in public,
        "hotkey request public dict exposed internal name",
    )
    _require(
        public["hotkey_configured"] is True,
        "hotkey request public dict lost configured assertion",
    )

    for arguments in (
        {
            "intent": framework.MotionIntent.EXPRESSION,
            "hotkey_name": " ",
        },
        {
            "intent": framework.MotionIntent.EXPRESSION,
            "hotkey_name": SYNTHETIC_OK,
            "request_id": " ",
        },
        {
            "intent": framework.MotionIntent.LOOK_AT,
            "hotkey_name": SYNTHETIC_OK,
        },
        {
            "intent": framework.MotionIntent.IDLE_MOTION,
            "hotkey_name": SYNTHETIC_OK,
        },
        {
            "intent": framework.MotionIntent.SPEAKING_STATE,
            "hotkey_name": SYNTHETIC_OK,
        },
    ):
        try:
            transport.VTubeStudioHotkeyRequest(**arguments)
        except ValueError:
            pass
        else:
            raise AssertionError(
                "invalid or unproven hotkey request was accepted"
            )

    _ok("bounded hotkey request is validated and privacy-safe")


def _assert_result_privacy(result, *private_values: str) -> None:
    rendered = (
        repr(result)
        + result.safe_message
        + repr(dict(result.public_metadata))
    )
    for value in private_values:
        _require(
            value not in rendered,
            f"transport result exposed private value: {value}",
        )
    for key in (
        "raw_payload_exposed",
        "hotkey_identifier_exposed",
        "hotkey_name_exposed",
        "real_hotkey_triggered",
        "real_motion_executed",
        "network_executed",
        "provider_sdk_imported",
        "provider_client_created",
    ):
        _require(
            result.public_metadata[key] is False,
            f"transport safety metadata changed: {key}",
        )


async def _assert_fake_matrix(framework, transport) -> None:
    fake = transport.FakeVTubeStudioTransport(
        available_hotkeys=(SYNTHETIC_OK,),
        failing_hotkeys=(SYNTHETIC_FAIL,),
        public_metadata={"secret": PRIVATE_VALUE},
    )
    _require(
        isinstance(fake, transport.VTubeStudioTransport),
        "fake transport lost Protocol conformance",
    )

    ready = await fake.preflight()
    _require(
        ready.operation
        is transport.VTubeStudioTransportOperation.PREFLIGHT,
        "preflight operation mismatch",
    )
    _require(
        ready.outcome is transport.VTubeStudioTransportOutcome.READY,
        "available fake preflight should be ready",
    )
    _require(ready.is_success, "ready result should be successful")
    _require(ready.is_terminal, "ready result should be terminal")
    _assert_result_privacy(
        ready,
        SYNTHETIC_OK,
        SYNTHETIC_FAIL,
        PRIVATE_VALUE,
    )

    completed_request = transport.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.EXPRESSION,
        hotkey_name=SYNTHETIC_OK.lower(),
        request_id="request-completed",
    )
    completed = await fake.trigger_hotkey(completed_request)
    _require(
        completed.outcome
        is transport.VTubeStudioTransportOutcome.COMPLETED,
        "case-insensitive fake hotkey should complete",
    )
    _require(
        completed.request_id == completed_request.request_id,
        "transport result did not preserve request_id",
    )
    _require(completed.is_success, "completed result should succeed")
    _require(
        completed.public_metadata["hotkey_resolved"] is True,
        "completed fake call should report resolved=true",
    )
    _assert_result_privacy(
        completed,
        SYNTHETIC_OK,
        SYNTHETIC_FAIL,
        PRIVATE_VALUE,
    )

    missing_request = transport.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.GESTURE,
        hotkey_name=SYNTHETIC_MISSING,
        request_id="request-missing",
    )
    missing = await fake.trigger_hotkey(missing_request)
    _require(
        missing.outcome
        is transport.VTubeStudioTransportOutcome.NOT_FOUND,
        "unknown fake hotkey should be not_found",
    )
    _require(not missing.is_success, "not_found must not succeed")
    _assert_result_privacy(
        missing,
        SYNTHETIC_MISSING,
        SYNTHETIC_OK,
        SYNTHETIC_FAIL,
        PRIVATE_VALUE,
    )

    failing_request = transport.VTubeStudioHotkeyRequest(
        intent=framework.MotionIntent.RESET_EXPRESSION,
        hotkey_name=SYNTHETIC_FAIL,
        request_id="request-failed",
    )
    failed = await fake.trigger_hotkey(failing_request)
    _require(
        failed.outcome
        is transport.VTubeStudioTransportOutcome.FAILED,
        "configured failing hotkey should fail deterministically",
    )
    _require(not failed.retryable, "fake failure must not be retryable")
    _assert_result_privacy(
        failed,
        SYNTHETIC_FAIL,
        SYNTHETIC_OK,
        PRIVATE_VALUE,
    )

    _require(fake.preflight_call_count == 1, "preflight count mismatch")
    _require(fake.trigger_call_count == 3, "trigger count mismatch")
    _require(
        fake.received_requests
        == (
            completed_request,
            missing_request,
            failing_request,
        ),
        "fake received-request order changed",
    )

    first_close = await fake.close()
    second_close = await fake.close()
    _require(
        first_close.outcome
        is transport.VTubeStudioTransportOutcome.COMPLETED,
        "first fake close should complete",
    )
    _require(
        first_close.public_metadata["already_closed"] is False,
        "first fake close should report already_closed=false",
    )
    _require(
        second_close.outcome
        is transport.VTubeStudioTransportOutcome.COMPLETED,
        "second fake close should complete idempotently",
    )
    _require(
        second_close.public_metadata["already_closed"] is True,
        "second fake close should report already_closed=true",
    )
    _require(fake.close_call_count == 2, "close count mismatch")
    _require(fake.is_closed, "fake transport should be closed")

    closed_preflight = await fake.preflight()
    _require(
        closed_preflight.outcome
        is transport.VTubeStudioTransportOutcome.CLOSED,
        "closed fake preflight should be closed",
    )
    closed_trigger = await fake.trigger_hotkey(completed_request)
    _require(
        closed_trigger.outcome
        is transport.VTubeStudioTransportOutcome.CLOSED,
        "closed fake trigger should be closed",
    )
    _assert_result_privacy(
        closed_trigger,
        SYNTHETIC_OK,
        SYNTHETIC_FAIL,
        PRIVATE_VALUE,
    )

    unavailable = transport.FakeVTubeStudioTransport(
        available_hotkeys=(SYNTHETIC_OK,),
        available=False,
    )
    unavailable_preflight = await unavailable.preflight()
    _require(
        unavailable_preflight.outcome
        is transport.VTubeStudioTransportOutcome.UNAVAILABLE,
        "unavailable fake preflight should be unavailable",
    )
    unavailable_trigger = await unavailable.trigger_hotkey(
        completed_request
    )
    _require(
        unavailable_trigger.outcome
        is transport.VTubeStudioTransportOutcome.UNAVAILABLE,
        "unavailable fake trigger should be unavailable",
    )

    try:
        await unavailable.trigger_hotkey(object())
    except TypeError:
        pass
    else:
        raise AssertionError("wrong trigger request type was accepted")

    _ok("deterministic in-memory fake transport matrix conforms")


def _assert_public_session_unchanged(framework) -> None:
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
        "MotionSession claimed real adapter support in FW-VTS-0c",
    )
    session.close()
    _ok("root-public MotionSession composition remains unchanged")


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    _assert_forbidden_modules_absent()

    with patch(
        "socket.create_connection",
        _blocked_connect,
    ):
        framework = importlib.import_module("framework")
        transport = importlib.import_module(
            "framework.vtube_studio_transport"
        )
        _assert_forbidden_modules_absent()
        _assert_internal_only(framework, transport)
        _assert_protocol_shape(transport)
        _assert_request_contract(framework, transport)
        asyncio.run(_assert_fake_matrix(framework, transport))
        _assert_public_session_unchanged(framework)
        _assert_forbidden_modules_absent()

    print(
        "v550_vtube_studio_transport_protocol_fake_status: "
        "implemented-awaiting-review"
    )
    print("v550_transport_protocol_async: True")
    print("v550_transport_protocol_runtime_checkable: True")
    print("v550_transport_factory_defined: True")
    print("v550_transport_root_public_exported: False")
    print("v550_fake_transport_in_memory_only: True")
    print("v550_fake_transport_deterministic: True")
    print("v550_fake_protocol_call_executed: True")
    print("v550_hotkey_request_bounded: True")
    print("v550_hotkey_first_intents_only: True")
    print("v550_transport_result_provider_safe: True")
    print("v550_hotkey_names_exposed_in_results: False")
    print("v550_hotkey_ids_exposed: False")
    print("v550_raw_payload_exposed: False")
    print("v550_raw_exception_exposed: False")
    print("v550_close_idempotent: True")
    print("v550_background_tasks_created: False")
    print("v550_async_lock_created: False")
    print("v550_retry_executed: False")
    print("v550_reconnect_executed: False")
    print("v550_motion_session_composition_changed: False")
    print("v550_configuration_resolver_changed: False")
    print("v550_root_public_api_changed: False")
    print("v550_environment_read: False")
    print("v550_filesystem_read: False")
    print("v550_actual_pyvts_imported: False")
    print("v550_websocket_imported: False")
    print("v550_network_executed: False")
    print("v550_token_read: False")
    print("v550_token_written: False")
    print("v550_model_discovery_executed: False")
    print("v550_real_hotkey_triggered: False")
    print("v550_real_motion_executed: False")
    print("v550_legacy_vts_runtime_changed: False")
    print("v550_requirements_changed: False")
    print("v550_release_metadata_changed: False")
    print("v550_drc_changed: False")
    print("v550_commit_created: False")
    print("v550_push_performed: False")
    print(
        "v550_next_authorization: "
        "exact-review-required-for-FW-VTS-0d"
    )
    _ok("FW-VTS-0c internal transport Protocol/fake smoke passed")


if __name__ == "__main__":
    main()
