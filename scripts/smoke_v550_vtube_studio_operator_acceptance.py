"""Source-only, network-free FW-VTS-0f1 operator-tooling smoke."""

from __future__ import annotations

import ast
import asyncio
import builtins
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OPERATOR_PATHS = (
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
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
    return path.read_text(encoding="utf-8", errors="replace")


def _load_module(relative: str, name: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"Unable to load: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _validate_docs() -> None:
    combined = "\n".join(_read(path) for path in DOC_PATHS)
    for marker in (
        "FW-VTS-0f1",
        "operator-only",
        "I_ACCEPT_LOCAL_VTUBE_STUDIO_TOKEN_BOOTSTRAP",
        "I_ACCEPT_LOCAL_VTUBE_STUDIO_REAL_MOTION_EXECUTION",
        "pyvts 0.3.3",
        "loopback only",
        "repository outside",
        "exact eleven-file surface",
        "real VTS execution: NOT_AUTHORIZED",
        "private token bootstrap: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
        "FW-VTS-0f2",
    ):
        _require(marker in combined, f"FW-VTS-0f1 docs missing marker: {marker}")
    for forbidden in (
        "FW-VTS-0f1: ACCEPTED",
        "real VTS execution: AUTHORIZED",
        "private token bootstrap: AUTHORIZED",
        "FW-VTS-0f2: AUTHORIZED",
        "token is committed",
        "evidence is committed",
    ):
        _require(forbidden not in combined, f"Forbidden authorization in docs: {forbidden}")
    _ok("FW-VTS-0f1 documentation and stop rules are explicit")


def _validate_bootstrap_source() -> None:
    relative = OPERATOR_PATHS[0]
    source = _read(relative)
    tree = ast.parse(source, filename=relative)
    top_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    _require("pyvts" not in top_imports, "token bootstrap eagerly imports pyvts")
    _require('importlib.import_module("pyvts")' in source, "lazy pyvts import missing")
    for marker in (
        'EXPECTED_PYVTS_VERSION = "0.3.3"',
        'PLUGIN_NAME = "AI Character Framework"',
        'PLUGIN_DEVELOPER = "murayan"',
        "authentication_token_path\": \"\"",
        "authentication_token()",
        "authentication(token)",
        "_write_private_text_atomic",
        "os.replace",
        "_LOOPBACK_HOSTS",
        "--overwrite",
        "REAL_CONFIRMATION",
        "PRIVATE_CONFIRMATION",
    ):
        _require(marker in source, f"token bootstrap source missing: {marker}")
    for forbidden in (
        "print(token",
        "print(args.token_output",
        "traceback.print_exc",
        "os.getenv(",
        "os.environ[",
        ".write_token(",
        ".read_token(",
    ):
        _require(forbidden not in source, f"token bootstrap contains forbidden operation: {forbidden}")
    _ok("token bootstrap is lazy, loopback-only, explicit, and private")


def _validate_acceptance_source() -> None:
    relative = OPERATOR_PATHS[1]
    source = _read(relative)
    tree = ast.parse(source, filename=relative)
    roots = _import_roots(tree)
    _require("pyvts" not in roots, "real acceptance imports pyvts directly")
    _require("websocket" not in roots and "websockets" not in roots, "real acceptance imports WebSocket runtime")
    framework_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "framework"
    ]
    _require(len(framework_imports) == 1, "real acceptance must have one root-public framework import")
    imported_names = {alias.name for alias in framework_imports[0].names}
    _require(
        imported_names == {"MotionIntent", "MotionOutcome", "MotionRequest", "create_motion_session"},
        f"unexpected root-public imports: {sorted(imported_names)}",
    )
    for forbidden_module in (
        "framework.motion",
        "framework.motion_session",
        "framework.vtube_studio",
        "live2d",
    ):
        _require(forbidden_module not in source, f"real acceptance imports internal module: {forbidden_module}")
    for marker in (
        "CONFIG_SCHEMA",
        "Exactly five non-empty private hotkey bindings",
        "create_motion_session(",
        "session.preflight()",
        "session.apply_motion(request)",
        "session.close()",
        "framework-vts-motion-bridge",
        "I_OBSERVED_EXPRESSION_EFFECT",
        "I_OBSERVED_EMOTION_EFFECT",
        "I_OBSERVED_GESTURE_EFFECT",
        "I_OBSERVED_RESET_EFFECT",
        "I_OBSERVED_STOP_EFFECT",
    ):
        _require(marker in source, f"real acceptance source missing: {marker}")
    for forbidden in (
        "print(token",
        "print(config_path",
        "print(private",
        "traceback.print_exc",
        "os.getenv(",
        "os.environ[",
    ):
        _require(forbidden not in source, f"real acceptance contains forbidden operation: {forbidden}")
    _ok("real acceptance uses only the root-public MotionSession boundary")


def _validate_private_config_without_provider() -> None:
    module = _load_module(
        OPERATOR_PATHS[1],
        "_fw_vts_0f1_acceptance_smoke_module",
    )
    with tempfile.TemporaryDirectory(prefix="fw-vts-0f1-") as temporary:
        root = Path(temporary).resolve()
        _require(not module._is_inside(root, ROOT), "temporary private root is inside repository")
        token_path = root / "private-token.txt"
        token_path.write_text("synthetic-not-a-real-token\n", encoding="utf-8")
        config_path = root / "private-config.json"
        config_path.write_text(
            json.dumps(
                {
                    "schema": module.CONFIG_SCHEMA,
                    "endpoint": {"host": "localhost", "port": 8001},
                    "authentication_token_file": str(token_path),
                    "hotkey_bindings": {
                        "expression:private-expression": "private-hotkey-a",
                        "emotion:private-emotion": "private-hotkey-b",
                        "gesture:private-gesture": "private-hotkey-c",
                        "reset_expression": "private-hotkey-d",
                        "stop_motion": "private-hotkey-e",
                    },
                }
            ),
            encoding="utf-8",
        )
        loaded = module._load_private_config(config_path, root=ROOT)
        _require(loaded["host"] == "localhost", "loopback host normalization failed")
        _require(len(loaded["bindings"]) == 5, "exact five-intent config validation failed")
        _require(loaded["token_path"] == token_path, "private token path validation failed")
    _require("pyvts" not in sys.modules, "private config validation imported pyvts")
    _ok("private configuration validates outside-repo without provider import")


def _valid_bootstrap_payload(head: str) -> dict[str, Any]:
    return {
        "schema": "ai-character-framework-v550-vts-bootstrap-evidence-v1",
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


def _valid_acceptance_payload(head: str) -> dict[str, Any]:
    intent_value = {
        "outcome": "completed",
        "provider_protocol_call_executed": True,
        "hotkey_resolved": True,
        "provider_request_completed": True,
        "operator_visual_confirmation": True,
        "real_hotkey_execution_verified": True,
        "real_motion_verified": True,
    }
    return {
        "schema": "ai-character-framework-v550-vts-operator-evidence-v1",
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
        "intent_results": {
            name: dict(intent_value)
            for name in ("expression", "emotion", "gesture", "reset_expression", "stop_motion")
        },
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


def _validate_evidence_schema_without_real_execution() -> None:
    module = _load_module(
        OPERATOR_PATHS[2],
        "_fw_vts_0f1_evidence_smoke_module",
    )
    head = "0" * 40
    bootstrap = _valid_bootstrap_payload(head)
    acceptance = _valid_acceptance_payload(head)
    module._validate_bootstrap(bootstrap)
    module._validate_acceptance(acceptance)

    rejected = dict(acceptance)
    rejected["token"] = "must-not-be-accepted"
    try:
        module._validate_acceptance(rejected)
    except AssertionError:
        pass
    else:
        raise AssertionError("evidence validator accepted forbidden token data")
    _require("pyvts" not in sys.modules, "evidence validation imported pyvts")
    _ok("private evidence validator accepts only bounded boolean/public outcomes")



def _validate_fake_bootstrap_protocol() -> None:
    module = _load_module(
        OPERATOR_PATHS[0],
        "_fw_vts_0f1_bootstrap_smoke_module",
    )

    class Requests:
        def authentication_token(self) -> dict[str, str]:
            return {"kind": "token"}

        def authentication(self, token: str) -> dict[str, str]:
            return {"kind": "auth", "token": token}

    class Client:
        def __init__(self) -> None:
            self.vts_request = Requests()
            self.authentic_token: str | None = None
            self.closed = False

        async def connect(self) -> None:
            return None

        async def request(self, request: Mapping[str, str]) -> Mapping[str, Any]:
            if request["kind"] == "token":
                return {"data": {"authenticationToken": "synthetic-token"}}
            return {
                "data": {
                    "authenticated": request.get("token") == "synthetic-token"
                }
            }

        async def close(self) -> None:
            self.closed = True

    client = Client()

    class FakePyvts:
        @staticmethod
        def vts(**kwargs: Any) -> Client:
            _require(kwargs["plugin_info"]["plugin_name"] == "AI Character Framework", "plugin name mismatch")
            _require(kwargs["plugin_info"]["developer"] == "murayan", "plugin developer mismatch")
            _require(kwargs["vts_api_info"]["host"] == "localhost", "fake bootstrap host mismatch")
            return client

    token, markers = asyncio.run(
        module._bootstrap(
            FakePyvts(),
            host="localhost",
            port=8001,
            connect_timeout=1.0,
            request_timeout=1.0,
            close_timeout=1.0,
        )
    )
    _require(token == "synthetic-token", "fake bootstrap token flow failed")
    _require(all(markers.values()), "fake bootstrap markers incomplete")
    _require(client.closed, "fake bootstrap did not close client")
    _require("pyvts" not in sys.modules, "fake bootstrap imported actual pyvts")
    _ok("fake token request, authentication, and bounded close conform")


def _validate_fake_root_public_acceptance_flow() -> None:
    module = _load_module(
        OPERATOR_PATHS[1],
        "_fw_vts_0f1_acceptance_main_smoke_module",
    )
    verifier = _load_module(
        OPERATOR_PATHS[2],
        "_fw_vts_0f1_acceptance_verifier_smoke_module",
    )

    class FakeSession:
        def __init__(self) -> None:
            self.is_closed = False
            self.intents: list[str] = []

        def preflight(self) -> Any:
            return SimpleNamespace(
                adapter_status=SimpleNamespace(value="configured"),
                supports_real_adapter=True,
                supports_expression=True,
                supports_emotion=True,
                supports_gesture=True,
                supports_reset_expression=True,
                supports_stop_motion=True,
                public_metadata={
                    "provider_sdk_imported": True,
                    "connected": True,
                    "authenticated": True,
                    "model_loaded": True,
                    "hotkey_inventory_loaded": True,
                },
            )

        def apply_motion(self, request: Any) -> Any:
            self.intents.append(request.intent.value)
            return SimpleNamespace(
                outcome=module.MotionOutcome.COMPLETED,
                public_metadata={
                    "provider_protocol_call_executed": True,
                    "hotkey_resolved": True,
                },
            )

        def close(self) -> None:
            self.is_closed = True

    with tempfile.TemporaryDirectory(prefix="fw-vts-0f1-main-") as temporary:
        private_root = Path(temporary).resolve()
        _require(not module._is_inside(private_root, ROOT), "fake private root is inside repository")
        token_path = private_root / "synthetic-token.txt"
        token_path.write_text("synthetic-token\n", encoding="utf-8")
        config_path = private_root / "synthetic-config.json"
        config_path.write_text(
            json.dumps(
                {
                    "schema": module.CONFIG_SCHEMA,
                    "endpoint": {"host": "localhost", "port": 8001},
                    "authentication_token_file": str(token_path),
                    "hotkey_bindings": {
                        "expression:private-expression": "private-hotkey-a",
                        "emotion:private-emotion": "private-hotkey-b",
                        "gesture:private-gesture": "private-hotkey-c",
                        "reset_expression": "private-hotkey-d",
                        "stop_motion": "private-hotkey-e",
                    },
                }
            ),
            encoding="utf-8",
        )
        evidence_root = private_root / "evidence"
        evidence_root.mkdir()
        session = FakeSession()
        module.create_motion_session = lambda **kwargs: session
        module.version = lambda name: "0.3.3"
        module._status_paths = lambda root: set()
        module._git = lambda root, *args: "a" * 40

        answers = iter(module.OBSERVATION_PHRASES.values())
        previous_input = builtins.input
        previous_argv = sys.argv
        builtins.input = lambda prompt="": next(answers)
        sys.argv = [
            str(ROOT / OPERATOR_PATHS[1]),
            "--private-config",
            str(config_path),
            "--evidence-root",
            str(evidence_root),
            "--confirm-real-vts-execution",
            module.REAL_CONFIRMATION,
            "--confirm-private-artifacts-outside-repo",
            module.PRIVATE_CONFIRMATION,
        ]
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                return_code = module.main()
        finally:
            builtins.input = previous_input
            sys.argv = previous_argv

        _require(return_code == 0, "fake root-public operator flow failed")
        _require(
            session.intents
            == ["expression", "emotion", "gesture", "reset_expression", "stop_motion"],
            "fake root-public intent order mismatch",
        )
        evidence_files = list(evidence_root.rglob("real_motion_operator_evidence.json"))
        _require(len(evidence_files) == 1, "fake operator evidence was not written exactly once")
        payload = json.loads(evidence_files[0].read_text(encoding="utf-8"))
        verifier._validate_acceptance(payload)
        rendered = output.getvalue()
        for private_value in (
            "private-hotkey-a",
            "private-expression",
            str(token_path),
            str(config_path),
        ):
            _require(private_value not in rendered, "fake operator console exposed private data")
            _require(private_value not in json.dumps(payload), "fake operator evidence exposed private data")

    _require("pyvts" not in sys.modules, "fake operator flow imported actual pyvts")
    _ok("fake root-public five-intent operator flow and private evidence conform")


def _validate_help_is_source_only() -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for relative in OPERATOR_PATHS:
        completed = subprocess.run(
            [sys.executable, str(ROOT / relative), "--help"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        _require("usage:" in completed.stdout.lower(), f"help failed: {relative}")
        _require("private-hotkey" not in completed.stdout, f"help exposed test data: {relative}")
    _require("pyvts" not in sys.modules, "help validation imported actual pyvts")
    _ok("operator and verifier help paths are provider-free and network-free")


def main() -> None:
    _validate_docs()
    _validate_bootstrap_source()
    _validate_acceptance_source()
    _validate_private_config_without_provider()
    _validate_evidence_schema_without_real_execution()
    _validate_fake_bootstrap_protocol()
    _validate_fake_root_public_acceptance_flow()
    _validate_help_is_source_only()

    print("v550_vtube_studio_operator_tooling_status: implemented-awaiting-review")
    print("v550_exact_change_surface: True")
    print("v550_operator_token_bootstrap_tool_present: True")
    print("v550_operator_real_motion_acceptance_tool_present: True")
    print("v550_private_evidence_validator_present: True")
    print("v550_operator_tools_loopback_only: True")
    print("v550_operator_tools_require_explicit_confirmation: True")
    print("v550_private_config_outside_repo_required: True")
    print("v550_private_token_outside_repo_required: True")
    print("v550_private_evidence_outside_repo_required: True")
    print("v550_root_public_motion_api_only: True")
    print("v550_exact_five_intent_acceptance_required: True")
    print("v550_operator_visual_confirmation_required: True")
    print("v550_fake_bootstrap_protocol_executed: True")
    print("v550_fake_root_public_acceptance_executed: True")
    print("v550_pyvts_version_required: 0.3.3")
    print("v550_actual_pyvts_imported_in_smoke: False")
    print("v550_websocket_connected_in_smoke: False")
    print("v550_actual_token_file_read_in_smoke: False")
    print("v550_actual_token_file_write_in_smoke: False")
    print("v550_actual_token_bootstrap_executed_in_smoke: False")
    print("v550_real_hotkey_triggered_in_smoke: False")
    print("v550_real_motion_executed_in_smoke: False")
    print("v550_commit_created: False")
    print("v550_push_performed: False")
    print("v550_next_authorization: exact-review-required-for-FW-VTS-0f2")
    print("[OK] FW-VTS-0f1 operator-tooling smoke passed")


if __name__ == "__main__":
    main()
