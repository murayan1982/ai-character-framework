"""FW-VTS-0c exact eight-file internal transport checker."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "31a6f6abcd4096a07a3719fb937e3a907fd044cd"

EXACT_SURFACE = {
    "README.md",
    "docs/public_facade.md",
    "docs/v550_motion_adapter_configuration_status.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_vtube_studio_transport_protocol_fake.md",
    "framework/vtube_studio_transport.py",
    "scripts/check_v550_vtube_studio_transport_protocol_fake.py",
    "scripts/smoke_v550_vtube_studio_transport_protocol_fake.py",
}

PROTECTED_PATHS = {
    ".env.example",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_session.py",
    "framework/motion_adapter_execution.py",
    "requirements.txt",
    "scripts/build_v540_release_package.py",
}

PROTECTED_PREFIXES = (
    "live2d/",
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
    "asyncio",
    "os",
    "pathlib",
    "importlib",
    "socket",
    "pyvts",
    "websocket",
    "websockets",
    "live2d",
}

FORBIDDEN_CALLS = {
    "getenv",
    "open",
    "exists",
    "is_file",
    "read_text",
    "read_bytes",
    "import_module",
    "find_spec",
    "connect",
    "create_connection",
    "create_task",
    "sleep",
    "Lock",
}

DOC_MARKERS = (
    "FW-VTS-0c",
    "31a6f6abcd4096a07a3719fb937e3a907fd044cd",
    "VTubeStudioTransport",
    "VTubeStudioTransportFactory",
    "VTubeStudioHotkeyRequest",
    "VTubeStudioTransportResult",
    "FakeVTubeStudioTransport",
    "internal async",
    "Hotkey-first",
    "not exported from the Framework root",
    "MotionSession composition remains deferred to FW-VTS-0e",
    "exact eight-file surface",
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
        f"FW-VTS-0c requires HEAD {EXPECTED_HEAD}, found {head}",
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
        "FW-VTS-0c exact surface mismatch: "
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
    _ok("FW-VTS-0c baseline and exact eight-file surface match")


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
        )
    )
    for marker in DOC_MARKERS:
        _require(marker in combined, f"FW-VTS-0c docs missing: {marker}")

    for forbidden in (
        "FW-VTS-0d: AUTHORIZED",
        "real VTS execution: AUTHORIZED",
        "transport symbols are exported from framework",
        "MotionSession now executes VTS",
    ):
        _require(
            forbidden not in combined,
            f"FW-VTS-0c docs contain forbidden authorization: {forbidden}",
        )
    _ok("FW-VTS-0c documentation contract is complete")


def _validate_source_boundary() -> None:
    relative = "framework/vtube_studio_transport.py"
    source = _read(relative)
    tree = ast.parse(source, filename=relative)

    imported_roots: set[str] = set()
    calls: set[str] = set()
    class_names: set[str] = set()
    async_methods: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level == 0:
                imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
        elif isinstance(node, ast.ClassDef):
            class_names.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            async_methods.add(node.name)

    import_hits = sorted(imported_roots & FORBIDDEN_IMPORT_ROOTS)
    call_hits = sorted(calls & FORBIDDEN_CALLS)
    _require(
        not import_hits,
        "transport module imports forbidden runtime modules: "
        + ", ".join(import_hits),
    )
    _require(
        not call_hits,
        "transport module performs forbidden runtime calls: "
        + ", ".join(call_hits),
    )

    expected_classes = {
        "VTubeStudioTransportOperation",
        "VTubeStudioTransportOutcome",
        "VTubeStudioHotkeyRequest",
        "VTubeStudioTransportResult",
        "VTubeStudioTransport",
        "FakeVTubeStudioTransport",
    }
    _require(
        expected_classes.issubset(class_names),
        "transport module class surface incomplete: "
        + ", ".join(sorted(expected_classes - class_names)),
    )
    _require(
        {"preflight", "trigger_hotkey", "close"}.issubset(async_methods),
        "transport async operation surface incomplete",
    )

    declared_names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        ):
            declared_names.add(node.target.id)
        elif isinstance(node, ast.arg):
            declared_names.add(node.arg)

    forbidden_declared_names = {
        "authentication_token",
        "token_path",
        "model_path",
        "endpoint_url",
        "endpoint_host",
        "endpoint_port",
        "hotkey_id",
        "provider_client",
        "websocket",
    }
    declared_hits = sorted(
        declared_names & forbidden_declared_names
    )
    _require(
        not declared_hits,
        "transport source declares forbidden private field/parameter: "
        + ", ".join(declared_hits),
    )

    _ok("FW-VTS-0c transport source is fake-only and bounded")


def _validate_root_api_unchanged() -> None:
    root_init = _read("framework/__init__.py")
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
            name not in root_init,
            f"internal transport symbol added to root API: {name}",
        )
    _ok("FW-VTS-0c does not change the root-public API")


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
        raise AssertionError(f"FW-VTS-0c dependency failed: {script}")

    print(completed.stdout, end="")
    _ok(f"dependency passed: {script}")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_docs()
    _validate_source_boundary()
    _validate_root_api_unchanged()

    for dependency in (
        "scripts/smoke_v550_vtube_studio_transport_protocol_fake.py",
        "scripts/smoke_v550_motion_adapter_configuration_status.py",
        "scripts/smoke_v550_real_motion_adapter_readiness.py",
        "scripts/smoke_v520_motion_adapter_types.py",
    ):
        _run_dependency(dependency)

    print(
        "v550_vtube_studio_transport_protocol_fake_status: "
        "implemented-awaiting-review"
    )
    print("v550_exact_change_surface: True")
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
    _ok("FW-VTS-0c exact internal transport check passed")


if __name__ == "__main__":
    main()
