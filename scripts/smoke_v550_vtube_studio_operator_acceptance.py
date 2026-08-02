"""Source-only, network-free FW-VTS-0f1c optional-stop corrective smoke."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OPERATOR_PATH = (
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py"
)
VERIFIER_PATH = (
    "scripts/verify_v550_vtube_studio_private_evidence.py"
)
DOC_PATHS = (
    "README.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"Missing required file: {relative}")
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def _load_module(relative: str, name: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    _require(
        spec is not None and spec.loader is not None,
        f"Unable to load: {relative}",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _validate_docs() -> None:
    for relative in DOC_PATHS:
        source = _read(relative)
        for marker in (
            "FW-VTS-0f1c",
            "optional stop_motion",
            "four required intents",
            "supports_stop_motion == false",
            "exact ten-file surface",
            "real VTS execution: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(
                marker in source,
                f"{relative} missing corrective marker: {marker}",
            )
    _ok(
        "FW-VTS-0f1c docs supersede exact-five acceptance safely"
    )


def _validate_source_boundaries() -> None:
    operator = _read(OPERATOR_PATH)
    verifier = _read(VERIFIER_PATH)
    tree = ast.parse(operator, filename=OPERATOR_PATH)

    framework_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "framework"
    ]
    _require(
        len(framework_imports) == 1,
        "operator must use one root-public framework import",
    )
    _require(
        {
            alias.name
            for alias in framework_imports[0].names
        }
        == {
            "MotionIntent",
            "MotionOutcome",
            "MotionRequest",
            "create_motion_session",
        },
        "operator root-public import surface changed",
    )
    for forbidden in (
        "import pyvts",
        "import websocket",
        "import websockets",
        "framework.motion",
        "framework.motion_session",
        "framework.vtube_studio",
        "live2d",
        "print(token",
        "traceback.print_exc",
        "os.getenv(",
        "os.environ[",
    ):
        _require(
            forbidden not in operator,
            f"operator contains forbidden boundary: {forbidden}",
        )
    for marker in (
        "REQUIRED_INTENTS",
        'OPTIONAL_INTENT = "stop_motion"',
        "stop_motion_supported",
        "required_four_intents_verified",
        "optional_stop_motion_contract",
        "execution_intents",
        "_capability_matches_private",
        "_run_intents",
    ):
        _require(
            marker in operator,
            f"operator missing optional-stop marker: {marker}",
        )
    for marker in (
        "REQUIRED_INTENTS",
        'OPTIONAL_INTENT = "stop_motion"',
        "--expected-bootstrap-head",
        "--expected-acceptance-head",
        "merge-base",
        "BOOTSTRAP_OPERATOR_PATH",
        "stop_motion_supported",
        "optional_stop_motion_contract",
    ):
        _require(
            marker in verifier,
            f"verifier missing corrective marker: {marker}",
        )
    _ok(
        "operator and verifier remain private, root-public, and provider-safe"
    )


def _write_config(
    path: Path,
    *,
    token_path: Path,
    bindings: Mapping[str, str],
    schema: str,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": schema,
                "endpoint": {
                    "host": "localhost",
                    "port": 8001,
                },
                "authentication_token_file": str(token_path),
                "hotkey_bindings": dict(bindings),
            }
        ),
        encoding="utf-8",
    )


def _expect_config_rejected(
    operator: ModuleType,
    config_path: Path,
) -> None:
    try:
        operator._load_private_config(
            config_path,
            root=ROOT,
        )
    except ValueError:
        return
    raise AssertionError(
        "invalid optional-stop private config was accepted"
    )


def _validate_private_config(operator: ModuleType) -> None:
    required = {
        "expression:private-expression": "private-hotkey-a",
        "emotion:private-emotion": "private-hotkey-b",
        "gesture:private-gesture": "private-hotkey-c",
        "reset_expression": "private-hotkey-d",
    }
    with tempfile.TemporaryDirectory(
        prefix="fw-vts-0f1c-"
    ) as temporary:
        private_root = Path(temporary).resolve()
        _require(
            not operator._is_inside(private_root, ROOT),
            "temporary private root is inside repository",
        )
        token_path = private_root / "private-token.txt"
        token_path.write_text(
            "synthetic-not-a-real-token\n",
            encoding="utf-8",
        )

        four_path = private_root / "four.json"
        _write_config(
            four_path,
            token_path=token_path,
            bindings=required,
            schema=operator.CONFIG_SCHEMA,
        )
        four = operator._load_private_config(
            four_path,
            root=ROOT,
        )
        _require(
            len(four["bindings"]) == 4,
            "four-binding config did not validate",
        )
        _require(
            four["execution_intents"]
            == operator.REQUIRED_INTENTS,
            "four-binding execution intent order mismatch",
        )
        _require(
            four["stop_motion_supported"] is False,
            "four-binding config falsely supports stop_motion",
        )

        five_path = private_root / "five.json"
        _write_config(
            five_path,
            token_path=token_path,
            bindings={
                **required,
                "stop_motion": "private-hotkey-e",
            },
            schema=operator.CONFIG_SCHEMA,
        )
        five = operator._load_private_config(
            five_path,
            root=ROOT,
        )
        _require(
            len(five["bindings"]) == 5,
            "five-binding config did not validate",
        )
        _require(
            five["execution_intents"]
            == operator.REQUIRED_INTENTS
            + (operator.OPTIONAL_INTENT,),
            "five-binding execution intent order mismatch",
        )
        _require(
            five["stop_motion_supported"] is True,
            "five-binding config did not support stop_motion",
        )

        three_path = private_root / "three.json"
        _write_config(
            three_path,
            token_path=token_path,
            bindings={
                key: value
                for key, value in required.items()
                if key != "reset_expression"
            },
            schema=operator.CONFIG_SCHEMA,
        )
        _expect_config_rejected(operator, three_path)

        unknown_path = private_root / "unknown.json"
        _write_config(
            unknown_path,
            token_path=token_path,
            bindings={
                **required,
                "idle_motion": "private-hotkey-e",
            },
            schema=operator.CONFIG_SCHEMA,
        )
        _expect_config_rejected(operator, unknown_path)

    _ok(
        "private config accepts required four plus optional stop only"
    )


def _capability(*, stop_supported: bool) -> Any:
    return SimpleNamespace(
        adapter_status=SimpleNamespace(value="configured"),
        supports_real_adapter=True,
        supports_expression=True,
        supports_emotion=True,
        supports_gesture=True,
        supports_reset_expression=True,
        supports_stop_motion=stop_supported,
    )


def _ready_values() -> dict[str, bool]:
    return {
        "private_config_outside_repo": True,
        "private_token_outside_repo": True,
        "private_evidence_outside_repo": True,
        "actual_pyvts_imported": True,
        "actual_websocket_connected": True,
        "actual_vts_authenticated": True,
        "actual_model_loaded": True,
        "actual_hotkey_inventory_loaded": True,
    }


class _FakeSession:
    def __init__(self, operator: ModuleType) -> None:
        self._operator = operator
        self.intents: list[str] = []

    def apply_motion(self, request: Any) -> Any:
        self.intents.append(request.intent.value)
        return SimpleNamespace(
            outcome=self._operator.MotionOutcome.COMPLETED,
            public_metadata={
                "provider_protocol_call_executed": True,
                "hotkey_resolved": True,
            },
        )


def _private(
    operator: ModuleType,
    *,
    stop_supported: bool,
) -> dict[str, Any]:
    selectors = {
        "expression": "expression:private-expression",
        "emotion": "emotion:private-emotion",
        "gesture": "gesture:private-gesture",
        "reset_expression": "reset_expression",
    }
    intents = operator.REQUIRED_INTENTS
    if stop_supported:
        selectors["stop_motion"] = "stop_motion"
        intents = intents + (operator.OPTIONAL_INTENT,)
    return {
        "selector_by_intent": selectors,
        "execution_intents": intents,
        "stop_motion_supported": stop_supported,
    }


def _validate_optional_execution(operator: ModuleType) -> None:
    for stop_supported in (False, True):
        private = _private(
            operator,
            stop_supported=stop_supported,
        )
        _require(
            operator._capability_matches_private(
                _capability(stop_supported=stop_supported),
                private,
                _ready_values(),
            ),
            "matching capability was rejected",
        )
        _require(
            not operator._capability_matches_private(
                _capability(
                    stop_supported=not stop_supported
                ),
                private,
                _ready_values(),
            ),
            "mismatched stop capability was accepted",
        )

        session = _FakeSession(operator)
        observed: list[str] = []
        results, verified = operator._run_intents(
            session,
            private,
            observer=lambda name: (
                observed.append(name) is None
            ),
        )
        expected = set(operator.REQUIRED_INTENTS)
        if stop_supported:
            expected.add(operator.OPTIONAL_INTENT)
        _require(
            set(results) == expected,
            "operator executed unexpected intent set",
        )
        _require(
            set(observed) == expected,
            "operator requested unexpected observations",
        )
        _require(
            verified["stop_motion"] is stop_supported,
            "optional stop verification mismatch",
        )
        _require(
            ("stop_motion" in session.intents)
            is stop_supported,
            "stop request presence mismatch",
        )
    _ok(
        "four-intent flow omits stop; five-intent flow includes stop"
    )


def _intent_value() -> dict[str, Any]:
    return {
        "outcome": "completed",
        "provider_protocol_call_executed": True,
        "hotkey_resolved": True,
        "provider_request_completed": True,
        "operator_visual_confirmation": True,
        "real_hotkey_execution_verified": True,
        "real_motion_verified": True,
    }


def _valid_bootstrap(head: str) -> dict[str, Any]:
    return {
        "schema": (
            "ai-character-framework-v550-vts-"
            "bootstrap-evidence-v1"
        ),
        "run_id": "0" * 32,
        "created_at_utc": "2026-08-02T00:00:00+00:00",
        "repo_head": head,
        "pyvts_version": "0.3.3",
        "repo_clean_before": True,
        "repo_clean_after": True,
        "endpoint_loopback_only": True,
        "actual_pyvts_imported": True,
        "provider_client_created": True,
        "actual_websocket_connected": True,
        "token_request_executed": True,
        "new_token_authenticated": True,
        "provider_close_completed": True,
        "private_token_written": True,
        "private_token_outside_repo": True,
        "private_evidence_outside_repo": True,
        "token_material_exposed": False,
        "token_path_exposed": False,
        "endpoint_value_exposed": False,
        "provider_payload_exposed": False,
        "raw_exception_exposed": False,
        "drc_repo_changed": False,
    }


def _valid_acceptance(
    head: str,
    *,
    stop_supported: bool,
) -> dict[str, Any]:
    intents = {
        name: _intent_value()
        for name in (
            "expression",
            "emotion",
            "gesture",
            "reset_expression",
        )
    }
    if stop_supported:
        intents["stop_motion"] = _intent_value()
    return {
        "schema": (
            "ai-character-framework-v550-vts-"
            "operator-evidence-v1"
        ),
        "run_id": "1" * 32,
        "created_at_utc": "2026-08-02T00:00:00+00:00",
        "repo_head": head,
        "pyvts_version": "0.3.3",
        "repo_clean_before": True,
        "repo_clean_after": True,
        "private_config_outside_repo": True,
        "private_token_outside_repo": True,
        "private_evidence_outside_repo": True,
        "endpoint_loopback_only": True,
        "actual_pyvts_imported": True,
        "actual_websocket_connected": True,
        "actual_vts_authenticated": True,
        "actual_model_loaded": True,
        "actual_hotkey_inventory_loaded": True,
        "intent_results": intents,
        "required_four_intents_verified": True,
        "stop_motion_supported": stop_supported,
        "stop_motion_verified": stop_supported,
        "optional_stop_motion_contract": True,
        "real_hotkey_execution_verified": True,
        "real_motion_execution_verified": True,
        "operator_visual_confirmation_complete": True,
        "session_close_verified": True,
        "bridge_thread_terminated": True,
        "automatic_retry_executed": False,
        "automatic_reconnect_executed": False,
        "polling_loop_created": False,
        "token_material_exposed": False,
        "token_path_exposed": False,
        "hotkey_name_exposed": False,
        "hotkey_identifier_exposed": False,
        "model_identity_exposed": False,
        "provider_payload_exposed": False,
        "raw_exception_exposed": False,
        "drc_repo_changed": False,
    }


def _validate_evidence(verifier: ModuleType) -> None:
    head = "0" * 40
    verifier._validate_bootstrap(_valid_bootstrap(head))
    verifier._validate_acceptance(
        _valid_acceptance(
            head,
            stop_supported=False,
        )
    )
    verifier._validate_acceptance(
        _valid_acceptance(
            head,
            stop_supported=True,
        )
    )

    rejected = _valid_acceptance(
        head,
        stop_supported=False,
    )
    rejected["intent_results"]["stop_motion"] = (
        _intent_value()
    )
    try:
        verifier._validate_acceptance(rejected)
    except AssertionError:
        pass
    else:
        raise AssertionError(
            "verifier accepted unsupported stop evidence"
        )

    rejected = _valid_acceptance(
        head,
        stop_supported=True,
    )
    rejected["stop_motion_verified"] = False
    try:
        verifier._validate_acceptance(rejected)
    except AssertionError:
        pass
    else:
        raise AssertionError(
            "verifier accepted unverified supported stop"
        )

    _ok(
        "evidence validator accepts exact four or supported five"
    )


def main() -> None:
    _validate_docs()
    _validate_source_boundaries()

    pyvts_before = "pyvts" in sys.modules
    operator = _load_module(
        OPERATOR_PATH,
        "_fw_vts_0f1c_operator_smoke",
    )
    verifier = _load_module(
        VERIFIER_PATH,
        "_fw_vts_0f1c_verifier_smoke",
    )
    _require(
        ("pyvts" in sys.modules) is pyvts_before,
        "source-only smoke imported pyvts",
    )

    _validate_private_config(operator)
    _validate_optional_execution(operator)
    _validate_evidence(verifier)

    print(
        "v550_vtube_studio_optional_stop_corrective_smoke: PASS"
    )
    print("v550_required_four_intents: True")
    print("v550_optional_stop_motion_contract: True")
    print("v550_four_binding_config_accepted: True")
    print("v550_five_binding_config_accepted: True")
    print("v550_three_binding_config_rejected: True")
    print("v550_unknown_intent_rejected: True")
    print("v550_stop_absent_execution_omitted: True")
    print("v550_stop_present_execution_included: True")
    print("v550_actual_pyvts_imported_in_smoke: False")
    print("v550_websocket_connected_in_smoke: False")
    print("v550_real_motion_executed_in_smoke: False")
    print(
        "[OK] FW-VTS-0f1c optional-stop corrective smoke passed"
    )


if __name__ == "__main__":
    main()
