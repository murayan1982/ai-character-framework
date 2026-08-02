"""FW-VTS-0f2c1 VTube Studio constructor-call corrective checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "430bb5bf6315923d8a77bc16cdcec6e63ccf5a55"
EXACT_SURFACE = {
    "framework/vtube_studio_motion_composition.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "scripts/check_v550_vtube_studio_constructor_corrective.py",
}
GENERATED_TTS_INVENTORY = (
    "utils/available_tts_models.txt",
    "utils/available_voices.txt",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _run(
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        check=check,
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


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _validate_repository() -> None:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    _require(
        head == EXPECTED_HEAD,
        f"FW-VTS-0f2c1 requires HEAD {EXPECTED_HEAD}, found {head}",
    )
    branch = _run("git", "branch", "--show-current").stdout.strip()
    _require(branch == "main", f"expected main branch, found: {branch}")
    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require(
        "ai-character-framework" in origin.casefold(),
        "origin is not AI Character Framework",
    )
    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-VTS-0f2c1 exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )
    _ok("FW-VTS-0f2c1 baseline and exact three-file surface match")


def _find_calls(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


def _validate_runtime_constructor_call() -> None:
    relative = "framework/vtube_studio_motion_composition.py"
    source = _read(relative)
    tree = ast.parse(source, filename=relative)
    calls = _find_calls(tree, "VTubeStudioPyvtsTransport")
    _require(
        len(calls) == 1,
        "expected exactly one VTubeStudioPyvtsTransport constructor call",
    )
    call = calls[0]
    _require(
        not call.args,
        "VTubeStudioPyvtsTransport received a positional argument",
    )
    _require(
        len(call.keywords) == 1
        and call.keywords[0].arg == "config",
        "VTubeStudioPyvtsTransport must receive exactly config=...",
    )
    config_value = call.keywords[0].value
    _require(
        isinstance(config_value, ast.Call)
        and isinstance(config_value.func, ast.Name)
        and config_value.func.id == "VTubeStudioPyvtsTransportConfig",
        "config= must wrap VTubeStudioPyvtsTransportConfig(...)",
    )
    _require(
        "VTubeStudioPyvtsTransport(\n            VTubeStudioPyvtsTransportConfig("
        not in source.replace("\r\n", "\n"),
        "legacy positional constructor call remains",
    )
    _ok("runtime transport constructor uses the keyword-only config contract")


def _find_class(tree: ast.AST, name: str) -> ast.ClassDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == name
    ]
    _require(len(matches) == 1, f"expected exactly one class: {name}")
    return matches[0]


def _validate_regression_factory_signature() -> None:
    relative = "scripts/smoke_v550_motion_session_real_adapter_composition.py"
    source = _read(relative)
    tree = ast.parse(source, filename=relative)
    factory = _find_class(tree, "_TransportFactory")
    methods = [
        node
        for node in factory.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "__call__"
    ]
    _require(
        len(methods) == 1,
        "_TransportFactory must define exactly one __call__",
    )
    method = methods[0]
    positional = [argument.arg for argument in method.args.args]
    keyword_only = [argument.arg for argument in method.args.kwonlyargs]
    _require(
        positional == ["self"],
        "_TransportFactory.__call__ must not accept positional config",
    )
    _require(
        keyword_only == ["config"],
        "_TransportFactory.__call__ must require keyword-only config",
    )
    _require(
        method.args.vararg is None
        and method.args.kwarg is None,
        "_TransportFactory.__call__ must not accept variadic arguments",
    )
    _ok("composition smoke now rejects positional transport construction")


def _validate_generated_files_absent() -> None:
    tracked = _git_lines("ls-files")
    for relative in GENERATED_TTS_INVENTORY:
        _require(
            relative not in tracked,
            f"generated TTS inventory file is tracked: {relative}",
        )
        _require(
            not (ROOT / relative).exists(),
            f"generated TTS inventory file exists: {relative}",
        )
    _ok("generated TTS inventory files remain outside repo")


def _run_compileall_and_smoke() -> None:
    compile_result = _run(
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "framework",
        "scripts",
        check=False,
    )
    _require(
        compile_result.returncode == 0,
        "compileall failed without exposing raw output",
    )

    smoke = _run(
        sys.executable,
        "scripts/smoke_v550_motion_session_real_adapter_composition.py",
        check=False,
    )
    _require(
        smoke.returncode == 0,
        "FW-VTS-0e composition smoke failed without exposing raw output",
    )
    _require(
        "v550_motion_session_real_adapter_composition_status:"
        in smoke.stdout,
        "composition smoke completion marker missing",
    )
    _require(
        "[OK] FW-VTS-0e MotionSession composition smoke passed"
        in smoke.stdout,
        "composition smoke pass marker missing",
    )
    _ok("compileall and real-adapter composition smoke pass")


def main() -> None:
    _validate_repository()
    _validate_runtime_constructor_call()
    _validate_regression_factory_signature()
    _validate_generated_files_absent()
    _run_compileall_and_smoke()

    print("v550_vtube_studio_constructor_corrective_check: PASS")
    print("v550_exact_change_surface: True")
    print("v550_exact_change_file_count: 3")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_transport_constructor_keyword_only: True")
    print("v550_regression_factory_keyword_only: True")
    print("v550_actual_pyvts_imported: False")
    print("v550_network_execution: False")
    print("v550_real_motion_execution: False")
    print("v550_token_read: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print(
        "v550_next_authorization: "
        "review-and-commit-FW-VTS-0f2c1"
    )
    print("[OK] FW-VTS-0f2c1 exact constructor corrective passed")


if __name__ == "__main__":
    main()
