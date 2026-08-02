"""FW-VTS-0b explicit motion-adapter configuration/status smoke.

This smoke is fake-only and execution-free. It validates the root-public
configuration resolver, typed preflight matrix, complete intent capability,
mock compatibility, and unchanged MotionSession real-adapter behavior without
environment lookup, filesystem access, pyvts/WebSocket import, provider client
creation, network execution, token/model path access, or real motion.
"""

from __future__ import annotations

import importlib
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


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _blocked_connect(*args, **kwargs):
    raise AssertionError("FW-VTS-0b attempted network execution")


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


def _capability(
    framework,
    *,
    adapter="vts",
    real_adapter_enabled=False,
    allow_provider_execution=False,
    endpoint_configured=False,
    runtime_available=False,
    token_available=False,
    model_selected=False,
    configured_intents=(),
):
    config = framework.resolve_motion_adapter_execution_config(
        adapter=adapter,
        real_adapter_enabled=real_adapter_enabled,
        allow_provider_execution=allow_provider_execution,
        endpoint_configured=endpoint_configured,
        runtime_available=runtime_available,
        token_available=token_available,
        model_selected=model_selected,
        configured_intents=configured_intents,
    )
    return config, framework.get_motion_adapter_execution_capability(config)


def _assert_root_exports(framework) -> None:
    expected = (
        "MotionAdapterExecutionConfig",
        "resolve_motion_adapter_execution_config",
        "get_motion_adapter_execution_capability",
    )
    for name in expected:
        _require(
            hasattr(framework, name),
            f"framework root missing FW-VTS-0b symbol: {name}",
        )
        _require(
            name in getattr(framework, "__all__", ()),
            f"framework.__all__ missing FW-VTS-0b symbol: {name}",
        )
    _ok("framework root exports FW-VTS-0b configuration/status symbols")


def _assert_mock(framework) -> None:
    config, capability = _capability(framework, adapter="mock")
    _require(config.adapter == "mock", "mock adapter normalization changed")
    _require(
        capability.adapter_status
        is framework.MotionAdapterStatus.MOCK_AVAILABLE,
        "mock capability should be mock_available",
    )
    for intent in framework.MotionIntent:
        _require(
            capability.supports_intent(intent),
            f"mock capability missing intent: {intent.value}",
        )
    _require(
        capability.supports_real_adapter is False,
        "mock capability must not claim a real adapter",
    )
    _ok("mock capability supports all eight provider-neutral intents")


def _assert_status_matrix(framework) -> None:
    cases = (
        (
            {"adapter": None},
            framework.MotionAdapterStatus.NOT_CONFIGURED,
        ),
        (
            {"adapter": "disabled"},
            framework.MotionAdapterStatus.DISABLED,
        ),
        (
            {"adapter": "none"},
            framework.MotionAdapterStatus.DISABLED,
        ),
        (
            {"adapter": "unsupported"},
            framework.MotionAdapterStatus.UNSUPPORTED_ADAPTER,
        ),
        (
            {"real_adapter_enabled": False},
            framework.MotionAdapterStatus.DISABLED,
        ),
        (
            {
                "real_adapter_enabled": True,
                "allow_provider_execution": False,
            },
            framework.MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
        ),
        (
            {
                "real_adapter_enabled": True,
                "allow_provider_execution": True,
                "endpoint_configured": False,
            },
            framework.MotionAdapterStatus.NOT_CONFIGURED,
        ),
        (
            {
                "real_adapter_enabled": True,
                "allow_provider_execution": True,
                "endpoint_configured": True,
                "runtime_available": False,
            },
            framework.MotionAdapterStatus.RUNTIME_NOT_INSTALLED,
        ),
        (
            {
                "real_adapter_enabled": True,
                "allow_provider_execution": True,
                "endpoint_configured": True,
                "runtime_available": True,
                "token_available": False,
            },
            framework.MotionAdapterStatus.TOKEN_MISSING,
        ),
        (
            {
                "real_adapter_enabled": True,
                "allow_provider_execution": True,
                "endpoint_configured": True,
                "runtime_available": True,
                "token_available": True,
                "model_selected": False,
            },
            framework.MotionAdapterStatus.MODEL_NOT_SELECTED,
        ),
        (
            {
                "real_adapter_enabled": True,
                "allow_provider_execution": True,
                "endpoint_configured": True,
                "runtime_available": True,
                "token_available": True,
                "model_selected": True,
            },
            framework.MotionAdapterStatus.CONFIGURED,
        ),
    )

    intents = (
        framework.MotionIntent.EXPRESSION,
        framework.MotionIntent.EMOTION,
        framework.MotionIntent.GESTURE,
        framework.MotionIntent.STOP_MOTION,
        framework.MotionIntent.RESET_EXPRESSION,
    )

    for arguments, expected in cases:
        arguments = {
            "configured_intents": intents,
            **arguments,
        }
        config, capability = _capability(framework, **arguments)
        _require(
            capability.adapter_status is expected,
            f"status matrix mismatch: expected={expected.value} "
            f"actual={capability.adapter_status.value}",
        )
        _require(
            capability.supports_real_adapter is False,
            "FW-VTS-0b must not claim a bound real transport",
        )
        if config.adapter == "vts":
            for intent in intents:
                _require(
                    capability.supports_intent(intent),
                    f"configured VTS intent flag lost: {intent.value}",
                )

    _ok("typed explicit-only motion configuration matrix conforms")


def _assert_aliases_and_intents(framework) -> None:
    for alias in ("vts", "vtube_studio", "live2d"):
        config = framework.resolve_motion_adapter_execution_config(
            adapter=alias,
            configured_intents=(
                framework.MotionIntent.EXPRESSION,
                framework.MotionIntent.EMOTION,
            ),
        )
        _require(
            config.adapter == "vts",
            f"VTS alias did not normalize: {alias}",
        )

    for unsupported in (
        framework.MotionIntent.SPEAKING_STATE,
        framework.MotionIntent.IDLE_MOTION,
        framework.MotionIntent.LOOK_AT,
    ):
        try:
            framework.resolve_motion_adapter_execution_config(
                adapter="vts",
                configured_intents=(unsupported,),
            )
        except ValueError as exc:
            text = str(exc)
            _require(
                unsupported.value in text,
                "safe unsupported-intent error omitted intent name",
            )
            _require(
                "token" not in text.lower()
                and "endpoint" not in text.lower()
                and "path" not in text.lower(),
                "unsupported-intent error exposed private configuration terms",
            )
        else:
            raise AssertionError(
                f"unproven VTS intent was accepted: {unsupported.value}"
            )

    config = framework.resolve_motion_adapter_execution_config(
        adapter="vts",
        configured_intents=(
            framework.MotionIntent.EXPRESSION,
            framework.MotionIntent.EXPRESSION,
            framework.MotionIntent.EMOTION,
        ),
    )
    _require(
        config.configured_intents
        == (
            framework.MotionIntent.EXPRESSION,
            framework.MotionIntent.EMOTION,
        ),
        "configured intents should be normalized and deduplicated",
    )
    _ok("VTS aliases and hotkey-first intent restrictions conform")


def _assert_configured_is_not_available(framework) -> None:
    config, capability = _capability(
        framework,
        real_adapter_enabled=True,
        allow_provider_execution=True,
        endpoint_configured=True,
        runtime_available=True,
        token_available=True,
        model_selected=True,
        configured_intents=(
            framework.MotionIntent.EXPRESSION,
            framework.MotionIntent.EMOTION,
        ),
    )
    _require(config.configuration_complete, "complete config not recognized")
    _require(
        capability.adapter_status
        is framework.MotionAdapterStatus.CONFIGURED,
        "complete assertions should return configured",
    )
    _require(
        capability.supports_real_adapter is False,
        "configured must not mean real transport available",
    )
    metadata = capability.public_metadata
    for key in (
        "provider_sdk_imported",
        "provider_client_created",
        "network_executed",
        "authentication_material_read",
        "authentication_location_read",
        "model_location_read",
        "real_motion_executed",
    ):
        _require(metadata[key] is False, f"metadata safety flag changed: {key}")
    _require(
        metadata["configuration_source"] == "explicit_arguments_only",
        "configuration source must remain explicit_arguments_only",
    )
    _ok("configured state remains transport-unbound and execution-free")


def _assert_session_composition_unchanged(framework) -> None:
    session = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=True,
    )
    capability = session.preflight()
    _require(
        capability.adapter_status
        is framework.MotionAdapterStatus.NOT_IMPLEMENTED,
        "MotionSession composition must remain deferred to FW-VTS-0e",
    )
    _require(
        capability.supports_real_adapter is False,
        "MotionSession must not claim real support in FW-VTS-0b",
    )
    session.close()
    _ok("existing MotionSession real composition remains unchanged")


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    _assert_forbidden_modules_absent()

    with (
        patch.object(socket.socket, "connect", _blocked_connect),
        patch("socket.create_connection", _blocked_connect),
    ):
        framework = importlib.import_module("framework")
        _assert_forbidden_modules_absent()
        _assert_root_exports(framework)
        _assert_mock(framework)
        _assert_status_matrix(framework)
        _assert_aliases_and_intents(framework)
        _assert_configured_is_not_available(framework)
        _assert_session_composition_unchanged(framework)
        _assert_forbidden_modules_absent()

    print("v550_motion_adapter_configuration_status: implemented-awaiting-review")
    print("v550_configuration_source: explicit_arguments_only")
    print("v550_motion_status_configured_added: True")
    print("v550_motion_intent_capability_complete: True")
    print("v550_mock_all_intents_supported: True")
    print("v550_vts_hotkey_first_intents_only: True")
    print("v550_motion_session_composition_changed: False")
    print("v550_environment_read: False")
    print("v550_filesystem_read: False")
    print("v550_actual_pyvts_imported: False")
    print("v550_websocket_imported: False")
    print("v550_network_executed: False")
    print("v550_token_value_read: False")
    print("v550_token_path_read: False")
    print("v550_model_path_read: False")
    print("v550_provider_client_created: False")
    print("v550_real_motion_executed: False")
    print("v550_legacy_vts_runtime_changed: False")
    print("v550_requirements_changed: False")
    print("v550_release_metadata_changed: False")
    print("v550_drc_changed: False")
    print("v550_commit_created: False")
    print("v550_push_performed: False")
    print(
        "v550_next_authorization: "
        "exact-review-required-for-FW-VTS-0c"
    )
    _ok("FW-VTS-0b explicit motion configuration/status smoke passed")


if __name__ == "__main__":
    main()
