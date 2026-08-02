"""FW-VTS-0f1c exact ten-file optional-stop corrective checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "1f737128554d701150427da4ce1c146759881255"
EXACT_SURFACE = {
    "README.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
    "scripts/check_v550_vtube_studio_operator_acceptance.py",
}
FROZEN_PATHS = {
    ".env.example",
    ".gitignore",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_session.py",
    "framework/motion_adapter_execution.py",
    "framework/vtube_studio_transport.py",
    "framework/vtube_studio_pyvts_transport.py",
    "framework/vtube_studio_motion_composition.py",
    "live2d/vts_client.py",
    "requirements.txt",
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
}
FROZEN_PREFIXES = (
    "core/",
    "plugins/",
    "presets/",
    "characters/",
    "config/",
    "release/",
)
GENERATED_TTS_INVENTORY = (
    "utils/available_tts_models.txt",
    "utils/available_voices.txt",
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


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing required file: {relative}")
    return path.read_text(
        encoding="utf-8",
        errors="replace",
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
        | _git_lines(
            "ls-files",
            "--others",
            "--exclude-standard",
        )
    ) - {".vscode/settings.json"}


def _validate_repository() -> None:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    _require(
        head == EXPECTED_HEAD,
        "FW-VTS-0f1c requires baseline "
        f"{EXPECTED_HEAD}, found {head}",
    )
    origin_main = _run(
        "git",
        "rev-parse",
        "origin/main",
    ).stdout.strip()
    _require(
        origin_main == EXPECTED_HEAD,
        "origin/main does not match corrective baseline",
    )
    branch = _run(
        "git",
        "branch",
        "--show-current",
    ).stdout.strip()
    _require(
        branch == "main",
        f"expected main branch, found: {branch}",
    )
    origin = _run(
        "git",
        "remote",
        "get-url",
        "origin",
    ).stdout.strip()
    _require(
        "ai-character-framework" in origin.lower(),
        "origin is not AI Character Framework",
    )

    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-VTS-0f1c exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} "
        f"actual={sorted(changed)}",
    )
    frozen_hits = sorted(
        path
        for path in changed
        if path in FROZEN_PATHS
        or any(
            path.startswith(prefix)
            for prefix in FROZEN_PREFIXES
        )
    )
    _require(
        not frozen_hits,
        "frozen runtime/config/release surface changed: "
        + ", ".join(frozen_hits),
    )
    _ok(
        "FW-VTS-0f1c baseline and exact ten-file surface match"
    )


def _validate_generated_files_absent() -> None:
    tracked = _git_lines("ls-files")
    for relative in GENERATED_TTS_INVENTORY:
        _require(
            relative not in tracked,
            f"generated TTS inventory is tracked: {relative}",
        )
        _require(
            not (ROOT / relative).exists(),
            f"generated TTS inventory restored: {relative}",
        )
    _ok("generated TTS inventory files remain outside repo")


def _validate_docs() -> None:
    for relative in DOC_PATHS:
        source = _read(relative)
        for marker in (
            "FW-VTS-0f1c",
            EXPECTED_HEAD,
            "optional stop_motion",
            "four required intents",
            "supports_stop_motion == false",
            "exact ten-file surface",
            "private token bootstrap: COMPLETED / ACCEPTED / REUSE",
            "real VTS execution: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
            "implementation: COMPLETED / AWAITING REVIEW",
        ):
            _require(
                marker in source,
                f"{relative} missing marker: {marker}",
            )
    _ok(
        "FW-VTS-0f1c documentation contract is complete"
    )


def _validate_source_boundaries() -> None:
    operator = _read(
        "scripts/"
        "operator_v550_vtube_studio_real_motion_acceptance.py"
    )
    verifier = _read(
        "scripts/"
        "verify_v550_vtube_studio_private_evidence.py"
    )
    smoke = _read(
        "scripts/"
        "smoke_v550_vtube_studio_operator_acceptance.py"
    )
    operator_tree = ast.parse(operator)

    framework_imports = [
        node
        for node in ast.walk(operator_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "framework"
    ]
    _require(
        len(framework_imports) == 1,
        "real acceptance must import root framework once",
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
        "real acceptance root-public import mismatch",
    )
    for forbidden in (
        "framework.motion",
        "framework.motion_session",
        "framework.vtube_studio",
        "live2d",
        "import pyvts",
        "import websocket",
        "import websockets",
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
    ):
        _require(
            marker in operator,
            f"operator missing corrective marker: {marker}",
        )
    for marker in (
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
    for marker in (
        "four_binding_config_accepted",
        "five_binding_config_accepted",
        "stop_absent_execution_omitted",
        "stop_present_execution_included",
    ):
        _require(
            marker in smoke,
            f"smoke missing corrective marker: {marker}",
        )
    _ok(
        "operator source remains root-public, private, and optional-stop aware"
    )


def _validate_smoke_and_compile() -> None:
    compile_result = _run(
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "framework",
        "scripts",
        "examples",
        check=False,
    )
    if compile_result.stdout:
        print(compile_result.stdout, end="")
    if compile_result.stderr:
        print(
            compile_result.stderr,
            end="",
            file=sys.stderr,
        )
    _require(
        compile_result.returncode == 0,
        "compileall failed",
    )

    smoke = _run(
        sys.executable,
        "scripts/"
        "smoke_v550_vtube_studio_operator_acceptance.py",
        check=False,
    )
    if smoke.stdout:
        print(smoke.stdout, end="")
    if smoke.stderr:
        print(smoke.stderr, end="", file=sys.stderr)
    _require(
        smoke.returncode == 0,
        "FW-VTS-0f1c dedicated smoke failed",
    )
    for marker in (
        "v550_vtube_studio_optional_stop_corrective_smoke: PASS",
        "v550_required_four_intents: True",
        "v550_optional_stop_motion_contract: True",
        "v550_four_binding_config_accepted: True",
        "v550_five_binding_config_accepted: True",
        "v550_stop_absent_execution_omitted: True",
        "v550_stop_present_execution_included: True",
        "v550_actual_pyvts_imported_in_smoke: False",
        "v550_websocket_connected_in_smoke: False",
        "v550_real_motion_executed_in_smoke: False",
    ):
        _require(
            marker in smoke.stdout,
            f"dedicated smoke missing marker: {marker}",
        )
    _ok(
        "FW-VTS-0f1c dedicated smoke and compileall pass"
    )


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_docs()
    _validate_source_boundaries()
    _validate_smoke_and_compile()

    print(
        "v550_vtube_studio_optional_stop_corrective_check: PASS"
    )
    print("v550_exact_change_surface: True")
    print("v550_exact_change_file_count: 10")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_runtime_changed: False")
    print("v550_token_bootstrap_changed: False")
    print("v550_required_four_intents: True")
    print("v550_optional_stop_motion_contract: True")
    print("v550_real_vts_execution_authorized: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print(
        "v550_next_authorization: "
        "review-and-commit-FW-VTS-0f1c"
    )
    print(
        "[OK] FW-VTS-0f1c exact contract checker passed"
    )


if __name__ == "__main__":
    main()
