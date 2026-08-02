"""FW-VTS-0b exact nine-file configuration/status checker.

This checker validates the explicit-only provider-neutral configuration and
capability checkpoint against the pushed FW-VTS-0a baseline. It is fake-only,
source-tree-only, and execution-free.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "ab5b83cbbaeb88cff9bba352e6b4f46ef5d08294"

EXACT_SURFACE = {
    "README.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_motion_adapter_configuration_status.md",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_adapter_execution.py",
    "scripts/check_v550_motion_adapter_configuration_status.py",
    "scripts/smoke_v550_motion_adapter_configuration_status.py",
}

PROTECTED_PATHS = {
    ".env.example",
    "framework/motion_session.py",
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
}

DOC_MARKERS = (
    "FW-VTS-0b",
    "ab5b83cbbaeb88cff9bba352e6b4f46ef5d08294",
    "MotionAdapterExecutionConfig",
    "resolve_motion_adapter_execution_config",
    "get_motion_adapter_execution_capability",
    "explicit_arguments_only",
    "MotionAdapterStatus.CONFIGURED",
    "supports_idle_motion",
    "supports_reset_expression",
    "supports_intent",
    "Hotkey-first configured intents",
    "MotionSession composition remains deferred to FW-VTS-0e",
    "real VTS execution: NOT_AUTHORIZED",
    "commit / push: NOT_AUTHORIZED",
    "exact nine-file surface",
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
        f"FW-VTS-0b requires HEAD {EXPECTED_HEAD}, found {head}",
    )

    branch = _run("git", "branch", "--show-current").stdout.strip()
    _require(branch == "main", f"expected main branch, found: {branch}")

    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require(
        "ai-character-framework" in origin.lower(),
        "origin is not the AI Character Framework repository",
    )

    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-VTS-0b exact surface mismatch: "
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
    _ok("FW-VTS-0b baseline and exact nine-file surface match")


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
    _ok("previous generated TTS inventory files remain outside the repo")


def _validate_docs() -> None:
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/public_facade.md"),
            _read("docs/v550_real_motion_adapter_readiness.md"),
            _read("docs/v550_motion_adapter_configuration_status.md"),
        )
    )
    for marker in DOC_MARKERS:
        _require(marker in combined, f"FW-VTS-0b docs missing: {marker}")

    for forbidden in (
        "FW-VTS-0c: AUTHORIZED",
        "real VTS execution: AUTHORIZED",
        "host app may pass token values",
        "MotionSession now executes VTS",
    ):
        _require(
            forbidden not in combined,
            f"FW-VTS-0b docs contain forbidden authorization: {forbidden}",
        )
    _ok("FW-VTS-0b documentation contract is complete")


def _validate_source_boundary() -> None:
    relative = "framework/motion_adapter_execution.py"
    source = _read(relative)
    tree = ast.parse(source, filename=relative)

    imported_roots: set[str] = set()
    calls: set[str] = set()
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

    import_hits = sorted(imported_roots & FORBIDDEN_IMPORT_ROOTS)
    call_hits = sorted(calls & FORBIDDEN_CALLS)
    _require(
        not import_hits,
        "configuration module imports forbidden runtime modules: "
        + ", ".join(import_hits),
    )
    _require(
        not call_hits,
        "configuration module performs forbidden runtime calls: "
        + ", ".join(call_hits),
    )

    config_fields: set[str] = set()
    public_function_parameters: dict[str, set[str]] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "MotionAdapterExecutionConfig"
        ):
            for item in node.body:
                if (
                    isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                ):
                    config_fields.add(item.target.id)
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name
            in {
                "resolve_motion_adapter_execution_config",
                "get_motion_adapter_execution_capability",
            }
        ):
            public_function_parameters[node.name] = {
                argument.arg
                for argument in (
                    list(node.args.posonlyargs)
                    + list(node.args.args)
                    + list(node.args.kwonlyargs)
                )
            }

    expected_fields = {
        "adapter",
        "real_adapter_enabled",
        "allow_provider_execution",
        "endpoint_configured",
        "runtime_available",
        "token_available",
        "model_selected",
        "configured_intents",
    }
    _require(
        config_fields == expected_fields,
        "MotionAdapterExecutionConfig field surface changed: "
        + ", ".join(sorted(config_fields)),
    )

    forbidden_parameters = {
        "endpoint_url",
        "endpoint_host",
        "endpoint_port",
        "authentication_token",
        "token",
        "token_path",
        "model",
        "model_id",
        "model_path",
        "hotkey_name",
        "hotkey_id",
        "provider_client",
        "websocket",
    }
    parameter_hits = sorted(
        parameter
        for parameters in public_function_parameters.values()
        for parameter in parameters
        if parameter in forbidden_parameters
    )
    _require(
        not parameter_hits,
        "configuration public API accepts forbidden private detail: "
        + ", ".join(parameter_hits),
    )

    _ok("FW-VTS-0b source is explicit-only and execution-free")


def _validate_motion_additive_contract() -> None:
    source = _read("framework/motion.py")
    root_init = _read("framework/__init__.py")

    for marker in (
        'CONFIGURED = "configured"',
        "supports_idle_motion: bool = False",
        "supports_reset_expression: bool = False",
        "def supports_intent(",
        "supports_idle_motion=True",
        "supports_reset_expression=True",
    ):
        _require(marker in source, f"motion additive contract missing: {marker}")

    for marker in (
        "MotionAdapterExecutionConfig",
        "resolve_motion_adapter_execution_config",
        "get_motion_adapter_execution_capability",
    ):
        _require(marker in root_init, f"root export missing: {marker}")

    _require(
        "motion_adapter_execution" in root_init,
        "root import does not include motion_adapter_execution",
    )
    _ok("Motion capability and root exports are additive and complete")


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
        raise AssertionError(f"FW-VTS-0b dependency failed: {script}")

    print(completed.stdout, end="")
    _ok(f"dependency passed: {script}")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_docs()
    _validate_source_boundary()
    _validate_motion_additive_contract()

    for dependency in (
        "scripts/smoke_v550_motion_adapter_configuration_status.py",
        "scripts/smoke_v550_real_motion_adapter_readiness.py",
        "scripts/smoke_v520_motion_adapter_types.py",
    ):
        _run_dependency(dependency)

    print("v550_motion_adapter_configuration_status: implemented-awaiting-review")
    print("v550_exact_change_surface: True")
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
    _ok("FW-VTS-0b exact configuration/status check passed")


if __name__ == "__main__":
    main()
