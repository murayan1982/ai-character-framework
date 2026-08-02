"""FW-VTS-0e exact eleven-file MotionSession composition checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "767a5f428998927c183a4c6040cb948b98f86711"

EXACT_SURFACE = {
    "README.md",
    "docs/public_facade.md",
    "docs/v550_motion_adapter_configuration_status.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_vtube_studio_transport_protocol_fake.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "framework/motion_session.py",
    "framework/vtube_studio_motion_composition.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "scripts/check_v550_motion_session_real_adapter_composition.py",
}

FROZEN_PATHS = {
    ".env.example",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_adapter_execution.py",
    "framework/vtube_studio_transport.py",
    "framework/vtube_studio_pyvts_transport.py",
    "live2d/vts_client.py",
    "requirements.txt",
    "scripts/build_v540_release_package.py",
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

DOC_MARKERS = (
    "FW-VTS-0e",
    EXPECTED_HEAD,
    "MotionSession Real-Adapter Composition",
    "persistent asyncio event loop",
    "asyncio.run_coroutine_threadsafe",
    "preflight",
    "single-flight",
    "late-completion suppression",
    "exact eleven-file surface",
    "real VTS execution: NOT_AUTHORIZED",
    "commit / push: NOT_AUTHORIZED",
    "exact-review-required-for-FW-VTS-0f",
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


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
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


def _validate_repository() -> None:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    _require(
        head == EXPECTED_HEAD,
        f"FW-VTS-0e requires HEAD {EXPECTED_HEAD}, found {head}",
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
        "FW-VTS-0e exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )
    frozen_hits = sorted(
        path
        for path in changed
        if path in FROZEN_PATHS
        or any(path.startswith(prefix) for prefix in FROZEN_PREFIXES)
    )
    _require(
        not frozen_hits,
        "frozen runtime/config/release surface changed: "
        + ", ".join(frozen_hits),
    )
    _ok("FW-VTS-0e baseline and exact eleven-file surface match")


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
    _ok("generated TTS inventory files remain outside repo")


def _validate_docs() -> None:
    combined = "\n".join(
        _read(path)
        for path in (
            "README.md",
            "docs/public_facade.md",
            "docs/v550_motion_adapter_configuration_status.md",
            "docs/v550_real_motion_adapter_readiness.md",
            "docs/v550_vtube_studio_transport_protocol_fake.md",
            "docs/v550_vtube_studio_pyvts_transport.md",
            "docs/v550_motion_session_real_adapter_composition.md",
        )
    )
    for marker in DOC_MARKERS:
        _require(marker in combined, f"FW-VTS-0e docs missing: {marker}")

    for forbidden in (
        "FW-VTS-0f: AUTHORIZED",
        "real VTS execution: AUTHORIZED",
        "token bootstrap is enabled",
        "automatic reconnect is enabled",
        "actual VTube Studio execution was performed",
    ):
        _require(
            forbidden not in combined,
            f"FW-VTS-0e docs contain forbidden authorization: {forbidden}",
        )
    _ok("FW-VTS-0e documentation contract is complete")


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _validate_motion_session_source() -> None:
    relative = "framework/motion_session.py"
    source = _read(relative)
    tree = ast.parse(source, filename=relative)

    _require('api_version: str = "5.5.0"' in source, "public motion API version not updated")
    for parameter in (
        "runtime_available",
        "model_selected",
        "vts_endpoint_host",
        "vts_endpoint_port",
        "vts_authentication_token",
        "vts_hotkey_bindings",
        "vts_connect_timeout_seconds",
        "vts_authenticate_timeout_seconds",
        "vts_request_timeout_seconds",
        "vts_close_timeout_seconds",
    ):
        _require(parameter in source, f"MotionSession missing parameter: {parameter}")

    _require(
        "from .vtube_studio_motion_composition import" in source,
        "MotionSession does not lazily import composition",
    )
    _require(
        "def _ensure_vts_composition" in source,
        "MotionSession composition factory boundary missing",
    )
    _require(
        "preflight_required" in source,
        "MotionSession does not require explicit preflight",
    )
    _require(
        "hotkey_binding_missing" in _read("framework/vtube_studio_motion_composition.py"),
        "missing hotkey binding normalization marker",
    )

    forbidden_text = (
        "import pyvts",
        "import websocket",
        "import websockets",
        "os.getenv",
        "os.environ",
        "dotenv",
        "read_token",
        "write_token",
        "request_authenticate_token",
        "asyncio.run(",
        "run_until_complete(",
    )
    for marker in forbidden_text:
        _require(marker not in source, f"MotionSession contains forbidden operation: {marker}")

    top_level_composition_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module
        and "vtube_studio_motion_composition" in node.module
    ]
    _require(
        not top_level_composition_imports,
        "MotionSession eagerly imports VTS composition",
    )
    _ok("MotionSession public composition source is explicit and lazy")


def _validate_composition_source() -> None:
    relative = "framework/vtube_studio_motion_composition.py"
    source = _read(relative)
    tree = ast.parse(source, filename=relative)
    roots = _import_roots(tree)

    _require("pyvts" not in roots, "composition eagerly imports actual pyvts")
    _require("websocket" not in roots, "composition imports websocket")
    _require("websockets" not in roots, "composition imports websockets")

    required_markers = (
        "asyncio.new_event_loop()",
        "loop.run_forever()",
        "asyncio.run_coroutine_threadsafe(",
        "threading.Thread(",
        "asyncio.all_tasks()",
        "await asyncio.gather(",
        "VTubeStudioPyvtsTransportConfig",
        "VTubeStudioPyvtsTransport(",
        "VTubeStudioHotkeyRequest(",
        "def resolve_request",
        "def preflight",
        "def trigger",
        "def close",
    )
    for marker in required_markers:
        _require(marker in source, f"composition source missing: {marker}")

    forbidden_markers = (
        "asyncio.run(",
        "run_until_complete(",
        "asyncio.create_task(",
        "asyncio.ensure_future(",
        "os.getenv",
        "os.environ",
        "dotenv",
        "open(",
        "read_text(",
        "read_bytes(",
        "write_text(",
        "write_bytes(",
        "read_token",
        "write_token",
        "request_authenticate_token",
        "reconnect(",
    )
    for marker in forbidden_markers:
        _require(marker not in source, f"composition contains forbidden operation: {marker}")

    class_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    _require(
        {"_PersistentAsyncBridge", "VTubeStudioMotionComposition"}.issubset(class_names),
        "composition class surface incomplete",
    )
    _ok("persistent sync/async bridge and internal composition source conform")


def _validate_root_and_frozen_boundaries() -> None:
    root_init = _read("framework/__init__.py")
    for internal_name in (
        "VTubeStudioMotionComposition",
        "create_vtube_studio_motion_composition",
        "VTubeStudioPyvtsTransport",
        "VTubeStudioTransport",
    ):
        _require(
            internal_name not in root_init,
            f"internal VTS symbol leaked into root source: {internal_name}",
        )

    protocol = _read("framework/vtube_studio_transport.py")
    pyvts_transport = _read("framework/vtube_studio_pyvts_transport.py")
    _require("class VTubeStudioTransport(Protocol)" in protocol, "frozen Protocol missing")
    _require("class VTubeStudioPyvtsTransport" in pyvts_transport, "accepted pyvts transport missing")
    _require("MotionSession composition remains deferred to FW-VTS-0e" in pyvts_transport, "FW-VTS-0d frozen source marker changed")
    _ok("root exports and accepted 0c/0d source boundaries remain frozen")


def _run_validation() -> None:
    _run(sys.executable, "-m", "compileall", "-q", "framework", "scripts", "examples")
    smoke = _run(
        sys.executable,
        "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    )
    required_output = (
        "v550_motion_session_real_adapter_composition_status: implemented-awaiting-review",
        "v550_persistent_session_event_loop: True",
        "v550_active_host_event_loop_safe: True",
        "v550_single_flight_enforced: True",
        "v550_bridge_thread_terminated: True",
        "v550_late_completion_suppressed: True",
        "v550_actual_pyvts_imported: False",
        "v550_network_executed: False",
        "v550_real_motion_executed: False",
        "v550_next_authorization: exact-review-required-for-FW-VTS-0f",
    )
    for marker in required_output:
        _require(marker in smoke.stdout, f"dedicated smoke missing output: {marker}")
    _ok("FW-VTS-0e dedicated smoke and compileall pass")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_docs()
    _validate_motion_session_source()
    _validate_composition_source()
    _validate_root_and_frozen_boundaries()
    _run_validation()

    print("v550_motion_session_real_adapter_composition_check: PASS")
    print("v550_exact_change_surface: True")
    print("v550_expected_head: " + EXPECTED_HEAD)
    print("v550_real_vts_execution_authorized: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print("v550_next_authorization: exact-review-required-for-FW-VTS-0f")
    _ok("FW-VTS-0e exact contract checker passed")


if __name__ == "__main__":
    main()
