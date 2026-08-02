"""FW-VTS-0d exact nine-file guarded lazy pyvts transport checker."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "9b22985c5b3b1bf53cea5397baf28e970a5b01a1"

EXACT_SURFACE = {
    "README.md",
    "docs/public_facade.md",
    "docs/v550_motion_adapter_configuration_status.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_vtube_studio_transport_protocol_fake.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "framework/vtube_studio_pyvts_transport.py",
    "scripts/check_v550_vtube_studio_pyvts_transport.py",
    "scripts/smoke_v550_vtube_studio_pyvts_transport.py",
}

PROTECTED_PATHS = {
    ".env.example",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_session.py",
    "framework/motion_adapter_execution.py",
    "framework/vtube_studio_transport.py",
    "live2d/vts_client.py",
    "requirements.txt",
    "scripts/build_v540_release_package.py",
}

PROTECTED_PREFIXES = (
    "core/",
    "plugins/",
    "presets/",
    "characters/",
    "config/",
)

GENERATED_TTS_INVENTORY = (
    "utils/available_tts_models.txt",
    "utils/available_voices.txt",
)

FORBIDDEN_IMPORT_ROOTS = {
    "os",
    "pathlib",
    "socket",
    "pyvts",
    "websocket",
    "websockets",
    "live2d",
}

FORBIDDEN_CALL_NAMES = {
    "getenv",
    "open",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "create_task",
    "sleep",
    "Lock",
    "reconnect",
    "read_token",
    "write_token",
    "authentication_token",
    "request_authenticate_token",
    "requestAuthenticationToken",
}

DOC_MARKERS = (
    "FW-VTS-0d",
    "9b22985c5b3b1bf53cea5397baf28e970a5b01a1",
    "VTubeStudioPyvtsTransportConfig",
    "VTubeStudioPyvtsClient",
    "VTubeStudioPyvtsClientFactory",
    "VTubeStudioPyvtsModuleImporter",
    "VTubeStudioPyvtsTransport",
    "lazy pyvts",
    "single-flight",
    "late-completion suppression",
    "MotionSession composition remains deferred to FW-VTS-0e",
    "exact nine-file surface",
    "real VTS execution: NOT_AUTHORIZED",
    "commit / push: NOT_AUTHORIZED",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="replace")


def _run(
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        check=check,
        env=env,
        capture_output=True,
        text=True,
    )


def _git_lines(*args: str) -> set[str]:
    output = _run("git", *args).stdout
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def _changed_paths() -> set[str]:
    return (
        _git_lines("diff", "--name-only")
        | _git_lines("diff", "--cached", "--name-only")
        | _git_lines("ls-files", "--others", "--exclude-standard")
    ) - {".vscode/settings.json"}


def _validate_repository() -> None:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    _require(
        head == EXPECTED_HEAD,
        f"FW-VTS-0d requires HEAD {EXPECTED_HEAD}, found {head}",
    )
    branch = _run("git", "branch", "--show-current").stdout.strip()
    _require(branch == "main", f"expected main branch, found: {branch}")
    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require(
        "ai-character-framework" in origin.lower(),
        "origin is not AI Character Framework",
    )

    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-VTS-0d exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )

    protected_hits = sorted(
        path
        for path in changed
        if path in PROTECTED_PATHS
        or any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
    )
    _require(
        not protected_hits,
        "protected runtime/config surface changed: "
        + ", ".join(protected_hits),
    )
    _ok("FW-VTS-0d baseline and exact nine-file surface match")


def _validate_generated_files_absent() -> None:
    tracked = _git_lines("ls-files")
    for relative in GENERATED_TTS_INVENTORY:
        _require(
            relative not in tracked,
            f"generated TTS inventory file is tracked: {relative}",
        )
        _require(
            not (ROOT / relative).exists(),
            f"generated TTS inventory file was restored: {relative}",
        )
    _ok("previous generated TTS inventory files remain outside repo")


def _validate_docs() -> None:
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/public_facade.md"),
            _read("docs/v550_motion_adapter_configuration_status.md"),
            _read("docs/v550_real_motion_adapter_readiness.md"),
            _read("docs/v550_vtube_studio_transport_protocol_fake.md"),
            _read("docs/v550_vtube_studio_pyvts_transport.md"),
        )
    )
    for marker in DOC_MARKERS:
        _require(marker in combined, f"FW-VTS-0d docs missing: {marker}")

    for forbidden in (
        "FW-VTS-0e: AUTHORIZED",
        "real VTS execution: AUTHORIZED",
        "MotionSession now executes VTube Studio",
        "token bootstrap is enabled",
        "automatic reconnect is enabled",
    ):
        _require(
            forbidden not in combined,
            f"FW-VTS-0d docs contain forbidden authorization: {forbidden}",
        )
    _ok("FW-VTS-0d documentation contract is complete")


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _validate_source_boundary() -> None:
    relative = "framework/vtube_studio_pyvts_transport.py"
    source = _read(relative)
    tree = ast.parse(source, filename=relative)

    imported_roots: set[str] = set()
    calls: list[ast.Call] = []
    class_names: set[str] = set()
    async_methods: set[str] = set()
    import_module_calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level == 0:
                imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            calls.append(node)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            ):
                import_module_calls.append(node)
        elif isinstance(node, ast.ClassDef):
            class_names.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            async_methods.add(node.name)

    import_hits = sorted(imported_roots & FORBIDDEN_IMPORT_ROOTS)
    _require(
        not import_hits,
        "pyvts transport eagerly imports forbidden modules: "
        + ", ".join(import_hits),
    )

    forbidden_call_hits = sorted(
        {
            name
            for call in calls
            if (name := _call_name(call)) in FORBIDDEN_CALL_NAMES
        }
    )
    _require(
        not forbidden_call_hits,
        "pyvts transport performs forbidden calls: "
        + ", ".join(forbidden_call_hits),
    )

    _require(
        len(import_module_calls) == 1,
        "lazy pyvts transport must contain exactly one import_module call",
    )
    import_call = import_module_calls[0]
    _require(
        len(import_call.args) == 1
        and isinstance(import_call.args[0], ast.Name)
        and import_call.args[0].id == "name",
        "lazy importer must import only its explicit module-name argument",
    )

    expected_classes = {
        "VTubeStudioPyvtsClient",
        "VTubeStudioPyvtsTransportConfig",
        "VTubeStudioPyvtsTransport",
    }
    _require(
        expected_classes.issubset(class_names),
        "pyvts transport class surface incomplete: "
        + ", ".join(sorted(expected_classes - class_names)),
    )
    _require(
        {"preflight", "trigger_hotkey", "close"}.issubset(async_methods),
        "pyvts transport async Protocol surface incomplete",
    )

    _require(
        source.count("asyncio.wait_for(") >= 5,
        "pyvts transport does not bound all provider operations",
    )
    _require(
        "requestHotKeyList()" in source,
        "pyvts transport does not request the hotkey inventory",
    )
    _require(
        "requestTriggerHotKey(" in source,
        "pyvts transport does not build hotkey trigger requests",
    )
    _require(
        "request.hotkey_name" in source,
        "pyvts transport does not use the internal hotkey name",
    )
    _require(
        "hotkeyID" not in source,
        "pyvts transport creates or stores provider hotkey IDs",
    )
    _require(
        '"authentication_token_path": ""' in source,
        "default client factory does not disable token-file persistence",
    )
    _require(
        "self._operation_active" in source,
        "pyvts transport does not enforce single-flight",
    )
    _require(
        "self._lifecycle_generation" in source,
        "pyvts transport does not suppress late completion",
    )

    _ok("FW-VTS-0d source is lazy, bounded, single-flight, and token-file-free")


def _validate_root_and_session_unchanged() -> None:
    root_init = _read("framework/__init__.py")
    motion_session = _read("framework/motion_session.py")

    for name in (
        "VTubeStudioPyvtsTransportConfig",
        "VTubeStudioPyvtsClient",
        "VTubeStudioPyvtsClientFactory",
        "VTubeStudioPyvtsModuleImporter",
        "VTubeStudioPyvtsTransport",
    ):
        _require(
            name not in root_init,
            f"internal pyvts transport symbol added to root API: {name}",
        )
        _require(
            name not in motion_session,
            f"MotionSession composed pyvts transport before FW-VTS-0e: {name}",
        )
    _ok("FW-VTS-0d does not change root-public API or MotionSession")


def _run_dependency(script: str) -> None:
    env = dict(os.environ)
    for name in (
        "FRAMEWORK_MOTION_REAL_ADAPTER",
        "FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION",
        "FRAMEWORK_MOTION_ADAPTER",
    ):
        env.pop(name, None)

    completed = _run(
        sys.executable,
        script,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        raise AssertionError(f"FW-VTS-0d dependency failed: {script}")

    print(completed.stdout, end="")
    _ok(f"dependency passed: {script}")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_docs()
    _validate_source_boundary()
    _validate_root_and_session_unchanged()

    for dependency in (
        "scripts/smoke_v550_vtube_studio_pyvts_transport.py",
        "scripts/smoke_v550_vtube_studio_transport_protocol_fake.py",
        "scripts/smoke_v550_motion_adapter_configuration_status.py",
        "scripts/smoke_v550_real_motion_adapter_readiness.py",
        "scripts/smoke_v520_motion_adapter_types.py",
    ):
        _run_dependency(dependency)

    print(
        "v550_vtube_studio_pyvts_transport_status: "
        "implemented-awaiting-review"
    )
    print("v550_exact_change_surface: True")
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
    _ok("FW-VTS-0d exact guarded lazy pyvts transport check passed")


if __name__ == "__main__":
    main()
