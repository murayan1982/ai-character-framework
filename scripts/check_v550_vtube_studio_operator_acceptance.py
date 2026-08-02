"""FW-VTS-0f1 exact eleven-file operator-tooling checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "48c25b4cd90478bb4bbd18f9a06daf2f4146c179"
EXACT_SURFACE = {
    "README.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
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


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
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
    return path.read_text(encoding="utf-8", errors="replace")


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
    _require(head == EXPECTED_HEAD, f"FW-VTS-0f1 requires HEAD {EXPECTED_HEAD}, found {head}")
    branch = _run("git", "branch", "--show-current").stdout.strip()
    _require(branch == "main", f"expected main branch, found: {branch}")
    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require("ai-character-framework" in origin.lower(), "origin is not AI Character Framework")

    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-VTS-0f1 exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )
    frozen_hits = sorted(
        path
        for path in changed
        if path in FROZEN_PATHS or any(path.startswith(prefix) for prefix in FROZEN_PREFIXES)
    )
    _require(not frozen_hits, "frozen runtime/config/release surface changed: " + ", ".join(frozen_hits))
    _ok("FW-VTS-0f1 baseline and exact eleven-file surface match")


def _validate_generated_files_absent() -> None:
    tracked = _git_lines("ls-files")
    for relative in GENERATED_TTS_INVENTORY:
        _require(relative not in tracked, f"generated TTS inventory file is tracked: {relative}")
        _require(not (ROOT / relative).exists(), f"generated TTS inventory file was restored: {relative}")
    _ok("generated TTS inventory files remain outside repo")


def _validate_docs() -> None:
    combined = "\n".join(
        _read(path)
        for path in (
            "README.md",
            "docs/public_facade.md",
            "docs/v550_real_motion_adapter_readiness.md",
            "docs/v550_motion_session_real_adapter_composition.md",
            "docs/v550_vtube_studio_pyvts_transport.md",
            "docs/v550_vtube_studio_operator_acceptance.md",
        )
    )
    for marker in (
        "FW-VTS-0f1",
        EXPECTED_HEAD,
        "operator-only",
        "pyvts 0.3.3",
        "loopback only",
        "exact eleven-file surface",
        "real VTS execution: NOT_AUTHORIZED",
        "private token bootstrap: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
        "exact-review-required-for-FW-VTS-0f2",
    ):
        _require(marker in combined, f"FW-VTS-0f1 docs missing marker: {marker}")
    _ok("FW-VTS-0f1 documentation contract is complete")


def _validate_source_boundaries() -> None:
    bootstrap = _read("scripts/operator_v550_vtube_studio_token_bootstrap.py")
    acceptance = _read("scripts/operator_v550_vtube_studio_real_motion_acceptance.py")
    verifier = _read("scripts/verify_v550_vtube_studio_private_evidence.py")
    bootstrap_tree = ast.parse(bootstrap)
    acceptance_tree = ast.parse(acceptance)

    top_bootstrap_imports = {
        alias.name
        for node in bootstrap_tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    _require("pyvts" not in top_bootstrap_imports, "operator bootstrap eagerly imports pyvts")
    _require('importlib.import_module("pyvts")' in bootstrap, "operator bootstrap lazy pyvts boundary missing")
    _require("_LOOPBACK_HOSTS" in bootstrap and "_LOOPBACK_HOSTS" in acceptance, "loopback-only guards missing")
    _require("EXPECTED_PYVTS_VERSION = \"0.3.3\"" in bootstrap, "bootstrap pyvts version pin missing")
    _require("EXPECTED_PYVTS_VERSION = \"0.3.3\"" in acceptance, "acceptance pyvts version pin missing")

    framework_imports = [
        node
        for node in ast.walk(acceptance_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "framework"
    ]
    _require(len(framework_imports) == 1, "real acceptance must import root framework exactly once")
    _require(
        {alias.name for alias in framework_imports[0].names}
        == {"MotionIntent", "MotionOutcome", "MotionRequest", "create_motion_session"},
        "real acceptance root-public import surface mismatch",
    )
    for forbidden in (
        "framework.motion",
        "framework.motion_session",
        "framework.vtube_studio",
        "live2d",
        "import pyvts",
        "import websocket",
        "import websockets",
    ):
        _require(forbidden not in acceptance, f"real acceptance contains forbidden import: {forbidden}")
    for source in (bootstrap, acceptance, verifier):
        for forbidden in ("print(token", "traceback.print_exc", "os.getenv(", "os.environ["):
            _require(forbidden not in source, f"operator tooling contains private-data risk: {forbidden}")
    _ok("operator source remains explicit, private, loopback-only, and root-public")


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
    _require(compile_result.returncode == 0, "compileall failed")
    smoke = _run(
        sys.executable,
        "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
        check=False,
    )
    if smoke.stdout:
        print(smoke.stdout, end="")
    if smoke.stderr:
        print(smoke.stderr, end="", file=sys.stderr)
    _require(smoke.returncode == 0, "FW-VTS-0f1 dedicated smoke failed")
    _require("v550_actual_pyvts_imported_in_smoke: False" in smoke.stdout, "smoke imported pyvts")
    _require("v550_websocket_connected_in_smoke: False" in smoke.stdout, "smoke connected WebSocket")
    _require("v550_real_motion_executed_in_smoke: False" in smoke.stdout, "smoke executed real motion")
    _ok("FW-VTS-0f1 dedicated smoke and compileall pass")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_docs()
    _validate_source_boundaries()
    _validate_smoke_and_compile()

    print("v550_vtube_studio_operator_acceptance_check: PASS")
    print("v550_exact_change_surface: True")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_real_vts_execution_authorized: False")
    print("v550_private_token_bootstrap_authorized: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print("v550_next_authorization: exact-review-required-for-FW-VTS-0f2")
    print("[OK] FW-VTS-0f1 exact contract checker passed")


if __name__ == "__main__":
    main()
