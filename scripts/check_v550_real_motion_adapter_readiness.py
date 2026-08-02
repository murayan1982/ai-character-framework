"""FW-VTS-0a v5.5.0 candidate exact readiness checker.

This checker validates the exact seven-file docs/test-only surface against the
released v5.4.0 baseline. It is source-tree-only and credential-free. It does
not import pyvts, connect to VTube Studio, access token files, execute real
motion, modify DRC, commit, push, or publish.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "d313eb6acb643103fe25988720ebee5976a04f78"

EXACT_SURFACE = {
    ".env.example",
    "README.md",
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "scripts/check_v550_real_motion_adapter_readiness.py",
    "scripts/smoke_v550_real_motion_adapter_readiness.py",
}

PROTECTED_RUNTIME_PREFIXES = (
    "framework/",
    "live2d/",
    "plugins/",
    "presets/",
    "characters/",
    "config/",
    "core/",
    "requirements",
    "pyproject",
    "setup.",
)

GENERATED_TTS_INVENTORY = (
    "utils/available_tts_models.txt",
    "utils/available_voices.txt",
)

FORBIDDEN_IMPORT_ROOTS = {
    "pyvts",
    "websocket",
    "websockets",
    "live2d",
}

DOC_MARKERS = (
    "FW-VTS-0a",
    "v5.5.0 candidate",
    "d313eb6acb643103fe25988720ebee5976a04f78",
    "Public motion skeleton freeze",
    "Legacy VTS call graph",
    "Hotkey-first initial scope",
    "FW-VTS-0b",
    "FW-VTS-0c",
    "FW-VTS-0d",
    "FW-VTS-0e",
    "FW-VTS-0f",
    "DRC RT-7 stop rule",
    "FRAMEWORK_MOTION_REAL_ADAPTER=0",
    "FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION=0",
    "FRAMEWORK_MOTION_ADAPTER=mock",
    "exact seven-file surface",
    "real VTS execution: NOT_AUTHORIZED",
    "commit / push: NOT_AUTHORIZED",
)

ROOT_IMPORT_MARKERS = (
    "from framework import (",
    "MotionRequest",
    "MotionResult",
    "create_motion_session",
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
        f"FW-VTS-0a requires HEAD {EXPECTED_HEAD}, found {head}",
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
        "FW-VTS-0a exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )

    protected_hits = sorted(
        path
        for path in changed
        if path != ".env.example"
        and any(path.startswith(prefix) for prefix in PROTECTED_RUNTIME_PREFIXES)
    )
    _require(
        not protected_hits,
        "protected runtime/config surface changed: "
        + ", ".join(protected_hits),
    )

    _ok("FW-VTS-0a repository baseline and exact seven-file surface match")


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


def _validate_documents() -> None:
    readiness = _read("docs/v550_real_motion_adapter_readiness.md")
    readme = _read("README.md")
    public_facade = _read("docs/public_facade.md")
    app_contract = _read("docs/app_integration_contract.md")
    env_example = _read(".env.example")
    combined = "\n".join(
        (readiness, readme, public_facade, app_contract, env_example)
    )

    for marker in DOC_MARKERS:
        _require(marker in combined, f"FW-VTS-0a docs missing: {marker}")

    for marker in ROOT_IMPORT_MARKERS:
        _require(
            marker in public_facade or marker in app_contract,
            f"root-public host import marker missing: {marker}",
        )

    for forbidden in (
        "host app may import pyvts",
        "DRC may implement its own VTS client",
        "token values may be logged",
        "raw VTS payloads are public",
        "FW-VTS-0b: AUTHORIZED",
        "real VTS execution: AUTHORIZED",
    ):
        _require(
            forbidden not in combined,
            f"FW-VTS-0a docs contain forbidden authorization: {forbidden}",
        )

    expected_env = {
        "FRAMEWORK_MOTION_REAL_ADAPTER": "0",
        "FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION": "0",
        "FRAMEWORK_MOTION_ADAPTER": "mock",
    }
    for name, value in expected_env.items():
        _require(
            f"{name}={value}" in env_example,
            f".env.example missing default-off guard: {name}={value}",
        )

    _ok("FW-VTS-0a documentation and default-off guard reservation are complete")


def _validate_python_import_safety() -> None:
    for relative in (
        "scripts/check_v550_real_motion_adapter_readiness.py",
        "scripts/smoke_v550_real_motion_adapter_readiness.py",
    ):
        source = _read(relative)
        tree = ast.parse(source, filename=relative)
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])

        hits = sorted(roots & FORBIDDEN_IMPORT_ROOTS)
        _require(
            not hits,
            f"{relative} imports forbidden real VTS modules: {hits}",
        )

    _ok("FW-VTS-0a scripts contain no pyvts/WebSocket/Live2D imports")


def _validate_public_and_legacy_inventory() -> None:
    motion = _read("framework/motion.py")
    session = _read("framework/motion_session.py")
    root_init = _read("framework/__init__.py")
    legacy_vts = _read("live2d/vts_client.py")
    runtime = _read("core/runtime.py")
    plugin = _read("plugins/builtin/emotion_vts.py")
    emotion = _read("core/emotion.py")
    text_vts = _read("presets/text_vts.json")
    voice_vts = _read("presets/voice_vts.json")
    requirements = _read("requirements.txt")

    for marker in (
        "MotionAdapterStatus",
        "MotionCapability",
        "MotionErrorCode",
        "MotionEventType",
        "MotionIntent",
        "MotionOutcome",
        "MotionRequest",
        "MotionResult",
        "MotionState",
        "MotionSession",
        "MotionSessionInfo",
        "create_motion_session",
    ):
        _require(
            marker in root_init,
            f"frozen public motion root export missing: {marker}",
        )

    for marker in (
        'api_version: str = "5.2.0"',
        '"live2d"',
        '"vts"',
        '"vtube_studio"',
        "PROVIDER_EXECUTION_NOT_ALLOWED",
        "NOT_IMPLEMENTED",
        "supports_real_adapter",
    ):
        _require(
            marker in session,
            f"public MotionSession skeleton marker missing: {marker}",
        )

    for marker in (
        "TOKEN_MISSING",
        "RUNTIME_NOT_INSTALLED",
        "MODEL_NOT_SELECTED",
        "NOT_IMPLEMENTED",
        "PROVIDER_ERROR",
        "SPEAKING_STATE",
        "LOOK_AT",
        "RESET_EXPRESSION",
    ):
        _require(
            marker in motion,
            f"public motion type inventory marker missing: {marker}",
        )

    for marker in (
        "import pyvts",
        "pyvts.vts",
        "authentication_token_path",
        "await self.vts.connect()",
        "await self.vts.read_token()",
        "await self.vts.write_token()",
        "requestHotKeyList",
        "requestTriggerHotKey",
        "asyncio.Lock",
        "async def close",
    ):
        _require(
            marker in legacy_vts,
            f"legacy VTS ownership marker missing: {marker}",
        )

    for marker in (
        "VTSClient",
        "await vts.connect()",
        "await vts.close()",
        '"vts": vts',
    ):
        _require(marker in runtime, f"legacy runtime marker missing: {marker}")

    for marker in (
        "EmotionVTSPlugin",
        "resolve_emotion_hotkey",
        "await vts.trigger_hotkey",
    ):
        location = plugin if marker != "resolve_emotion_hotkey" else (
            plugin + "\n" + emotion
        )
        _require(marker in location, f"legacy emotion/VTS marker missing: {marker}")

    for preset_name, preset_text in (
        ("text_vts", text_vts),
        ("voice_vts", voice_vts),
    ):
        for marker in (
            '"vts_enabled": true',
            '"emotion_enabled": true',
            '"vts_emotion_enabled": true',
        ):
            _require(
                marker in preset_text,
                f"{preset_name} missing legacy VTS preset marker: {marker}",
            )

    _require(
        "pyvts==0.3.3" in requirements,
        "requirements pin changed: pyvts==0.3.3",
    )
    _require(
        "websockets==16.0" in requirements,
        "requirements pin changed: websockets==16.0",
    )

    _ok("public skeleton and legacy VTS call graph inventory are fixed")


def _validate_token_and_package_inventory() -> None:
    ignore = _read(".gitignore")
    settings = _read("config/settings.py")
    builder = _read("scripts/build_v540_release_package.py")
    readiness = _read("docs/v550_real_motion_adapter_readiness.md")
    tracked = _git_lines("ls-files")

    _require(
        "config/tokens/" in ignore,
        ".gitignore no longer excludes config/tokens/",
    )
    _require(
        "*_token.json" in ignore,
        ".gitignore no longer excludes *_token.json",
    )
    _require(
        'VTS_TOKEN_PATH = os.path.join("config", "tokens", "vts_token.json")'
        in settings,
        "legacy VTS token path inventory changed",
    )

    tracked_token_hits = sorted(
        item
        for item in tracked
        if item.startswith("config/tokens/")
        or item.lower().endswith("_token.json")
        or item.lower().endswith("vts_token.json")
    )
    _require(
        not tracked_token_hits,
        "tracked VTS token artifact found: " + ", ".join(tracked_token_hits),
    )

    _require(
        '["git", "ls-files", "-z"]' in builder,
        "v5.4 package builder no longer uses tracked-file membership",
    )
    _require(
        '"config/tokens/"' not in builder,
        "package hardening gap changed unexpectedly during FW-VTS-0a",
    )
    _require(
        "package hardening gap" in readiness,
        "readiness doc does not record the tracked-token package gap",
    )
    _require(
        "FW-VTS-0f" in readiness
        and "config/tokens/" in readiness
        and "*_token.json" in readiness,
        "FW-VTS-0f package-hardening ownership is missing",
    )

    _ok("token ignore, tracked-source state, and package hardening gap are recorded")


def _run_smoke() -> None:
    env = dict(os.environ)
    for name in (
        "FRAMEWORK_MOTION_REAL_ADAPTER",
        "FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION",
        "FRAMEWORK_MOTION_ADAPTER",
    ):
        env.pop(name, None)

    completed = _run(
        sys.executable,
        "scripts/smoke_v550_real_motion_adapter_readiness.py",
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        raise AssertionError("FW-VTS-0a readiness smoke failed")

    required = (
        "v550_real_motion_adapter_readiness_status: implemented-awaiting-review",
        "v550_actual_pyvts_imported: False",
        "v550_websocket_connection_executed: False",
        "v550_token_read: False",
        "v550_token_written: False",
        "v550_real_motion_executed: False",
        "v550_commit_created: False",
        "v550_push_performed: False",
        "exact-review-required-for-FW-VTS-0b",
    )
    for marker in required:
        _require(
            marker in completed.stdout,
            f"FW-VTS-0a smoke output missing: {marker}",
        )

    print(completed.stdout, end="")
    _ok("FW-VTS-0a credential-free smoke dependency passed")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_documents()
    _validate_python_import_safety()
    _validate_public_and_legacy_inventory()
    _validate_token_and_package_inventory()
    _run_smoke()

    print("v550_real_motion_adapter_readiness_status: implemented-awaiting-review")
    print("v550_exact_change_surface: True")
    print("v550_framework_runtime_changed: False")
    print("v550_legacy_vts_runtime_changed: False")
    print("v550_requirements_changed: False")
    print("v550_release_metadata_changed: False")
    print("v550_drc_changed: False")
    print("v550_public_motion_skeleton_frozen: True")
    print("v550_legacy_vts_inventory_complete: True")
    print("v550_hotkey_first_scope_fixed: True")
    print("v550_motion_guards_default_off: True")
    print("v550_actual_pyvts_imported: False")
    print("v550_websocket_connection_executed: False")
    print("v550_token_read: False")
    print("v550_token_written: False")
    print("v550_model_discovery_executed: False")
    print("v550_hotkey_triggered: False")
    print("v550_parameter_update_executed: False")
    print("v550_real_motion_executed: False")
    print("v550_commit_created: False")
    print("v550_push_performed: False")
    print(
        "v550_next_authorization: "
        "exact-review-required-for-FW-VTS-0b"
    )
    _ok("FW-VTS-0a v5.5.0 exact readiness check passed")


if __name__ == "__main__":
    main()
