"""FW-VTS-0a v5.5.0 candidate real-motion readiness smoke.

This smoke is credential-free and fail-closed. It exercises only the existing
root-public MotionSession mock/not-implemented boundary. It must not import
pyvts, open a socket, access VTS token paths, discover models, trigger hotkeys,
update parameters, execute real motion, modify DRC, commit, or push.
"""

from __future__ import annotations

import builtins
import importlib
import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOKEN_MARKERS = (
    "config/tokens",
    "config\\tokens",
    "vts_token.json",
    "_token.json",
)
FORBIDDEN_LOADED_MODULE_FRAGMENTS = (
    "pyvts",
    "websockets",
    "live2d.vts_client",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _is_token_target(value: object) -> bool:
    try:
        text = os.fspath(value)
    except TypeError:
        text = str(value)
    lowered = text.replace("\\", "/").lower()
    return any(
        marker.replace("\\", "/").lower() in lowered
        for marker in TOKEN_MARKERS
    )


def _deny_token_path(operation: str, value: object) -> None:
    if _is_token_target(value):
        raise AssertionError(
            f"FW-VTS-0a attempted forbidden token path {operation}"
        )


def _guarded_open(original):
    def wrapper(file, *args, **kwargs):
        _deny_token_path("open", file)
        return original(file, *args, **kwargs)

    return wrapper


def _guarded_exists(original):
    def wrapper(path):
        _deny_token_path("exists", path)
        return original(path)

    return wrapper


def _guarded_getsize(original):
    def wrapper(path):
        _deny_token_path("getsize", path)
        return original(path)

    return wrapper


def _guarded_makedirs(original):
    def wrapper(name, *args, **kwargs):
        _deny_token_path("makedirs", name)
        return original(name, *args, **kwargs)

    return wrapper


def _guarded_remove(original):
    def wrapper(path, *args, **kwargs):
        _deny_token_path("remove", path)
        return original(path, *args, **kwargs)

    return wrapper


def _blocked_connect(*args, **kwargs):
    raise AssertionError("FW-VTS-0a attempted a network connection")


def _assert_forbidden_modules_absent() -> None:
    loaded = sorted(
        name
        for name in sys.modules
        if any(
            fragment in name.lower()
            for fragment in FORBIDDEN_LOADED_MODULE_FRAGMENTS
        )
    )
    _require(
        not loaded,
        "forbidden VTS/WebSocket modules loaded: " + ", ".join(loaded),
    )


def _assert_public_exports(framework) -> None:
    expected = (
        "MotionAdapterStatus",
        "MotionCapability",
        "MotionErrorCode",
        "MotionEventType",
        "MotionIntent",
        "MotionOutcome",
        "MotionRequest",
        "MotionResult",
        "MotionState",
        "MotionSession",
        "MotionSessionInfo",
        "create_motion_session",
    )
    for name in expected:
        _require(
            hasattr(framework, name),
            f"framework root missing public motion symbol: {name}",
        )
        _require(
            name in getattr(framework, "__all__", ()),
            f"framework.__all__ missing public motion symbol: {name}",
        )
    _ok("framework root exports the frozen public motion skeleton")


def _assert_mock_session(framework) -> None:
    session = framework.create_motion_session(adapter="mock")
    capability = session.preflight()

    _require(
        capability.adapter_status
        is framework.MotionAdapterStatus.MOCK_AVAILABLE,
        "mock preflight should remain mock_available",
    )
    _require(
        capability.supports_real_adapter is False,
        "mock capability must not claim real-adapter support",
    )

    requests = (
        framework.MotionRequest.emotion_update("happy"),
        framework.MotionRequest.speaking_state(True),
        framework.MotionRequest.stop_motion(),
    )
    for request in requests:
        result = session.apply_motion(request)
        _require(
            result.outcome is framework.MotionOutcome.COMPLETED,
            f"mock request did not complete: {request.intent.value}",
        )
        _require(
            result.public_error_code is framework.MotionErrorCode.NONE,
            f"mock request exposed an error: {request.intent.value}",
        )

    session.close()
    session.close()
    _require(session.is_closed, "mock session close should be idempotent")
    _ok("existing mock MotionSession behavior remains compatible")


def _assert_guard_closed(framework) -> None:
    session = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=False,
    )
    capability = session.preflight()
    _require(
        capability.adapter_status
        is framework.MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
        "closed execution guard should be typed provider_execution_not_allowed",
    )
    result = session.apply_motion(
        framework.MotionRequest.emotion_update("happy")
    )
    _require(
        result.outcome is framework.MotionOutcome.UNAVAILABLE,
        "closed execution guard should return unavailable",
    )
    _require(
        result.public_error_code
        is framework.MotionErrorCode.PROVIDER_EXECUTION_NOT_ALLOWED,
        "closed execution guard returned wrong public error code",
    )
    session.close()
    _ok("VTS execution guard remains typed and fail-closed")


def _assert_guard_open_not_implemented(framework) -> None:
    for adapter in ("vts", "vtube_studio", "live2d"):
        session = framework.create_motion_session(
            adapter=adapter,
            real_adapter_enabled=True,
            allow_provider_execution=True,
        )
        capability = session.preflight()
        _require(
            capability.adapter_status
            is framework.MotionAdapterStatus.NOT_IMPLEMENTED,
            f"{adapter} must remain typed not_implemented in FW-VTS-0a",
        )
        _require(
            capability.supports_real_adapter is False,
            f"{adapter} must not claim real-adapter support in FW-VTS-0a",
        )
        result = session.apply_motion(
            framework.MotionRequest.emotion_update("happy")
        )
        _require(
            result.outcome is framework.MotionOutcome.NOT_IMPLEMENTED,
            f"{adapter} should return typed not_implemented",
        )
        _require(
            result.public_error_code
            is framework.MotionErrorCode.NOT_IMPLEMENTED,
            f"{adapter} returned wrong public error code",
        )
        session.close()
    _ok("real adapter aliases remain honest not-implemented boundaries")


def main() -> None:
    _require(
        str(ROOT) not in {"", "."},
        "repository root could not be resolved",
    )
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    original_open = builtins.open
    original_exists = os.path.exists
    original_getsize = os.path.getsize
    original_makedirs = os.makedirs
    original_remove = os.remove

    guard_env = {
        "FRAMEWORK_MOTION_REAL_ADAPTER": "0",
        "FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION": "0",
        "FRAMEWORK_MOTION_ADAPTER": "mock",
    }

    _assert_forbidden_modules_absent()

    with (
        patch.dict(os.environ, guard_env, clear=False),
        patch("builtins.open", _guarded_open(original_open)),
        patch("os.path.exists", _guarded_exists(original_exists)),
        patch("os.path.getsize", _guarded_getsize(original_getsize)),
        patch("os.makedirs", _guarded_makedirs(original_makedirs)),
        patch("os.remove", _guarded_remove(original_remove)),
        patch.object(socket.socket, "connect", _blocked_connect),
        patch("socket.create_connection", _blocked_connect),
    ):
        framework = importlib.import_module("framework")
        _assert_forbidden_modules_absent()
        _assert_public_exports(framework)
        _assert_mock_session(framework)
        _assert_guard_closed(framework)
        _assert_guard_open_not_implemented(framework)
        _assert_forbidden_modules_absent()

    print("v550_real_motion_adapter_readiness_status: implemented-awaiting-review")
    print("v550_framework_runtime_changed: False")
    print("v550_legacy_vts_runtime_changed: False")
    print("v550_requirements_changed: False")
    print("v550_release_metadata_changed: False")
    print("v550_drc_changed: False")
    print("v550_public_motion_skeleton_frozen: True")
    print("v550_motion_guards_default_off: True")
    print("v550_actual_pyvts_imported: False")
    print("v550_websocket_connection_executed: False")
    print("v550_token_read: False")
    print("v550_token_written: False")
    print("v550_model_discovery_executed: False")
    print("v550_hotkey_triggered: False")
    print("v550_parameter_update_executed: False")
    print("v550_real_motion_executed: False")
    print("v550_commit_created: False")
    print("v550_push_performed: False")
    print(
        "v550_next_authorization: "
        "exact-review-required-for-FW-VTS-0b"
    )
    _ok("FW-VTS-0a v5.5.0 candidate readiness smoke passed")


if __name__ == "__main__":
    main()
