"""FW-VTS-0f2 exact eight-file public acceptance-sync checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "b7b9639dfa1f675ba04a33cd8ce297429f98fd15"

EXACT_SURFACE = {
    "README.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/check_v550_vtube_studio_real_motion_acceptance_sync.py",
}

DOC_PATHS = (
    "README.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
)

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
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
    "scripts/check_v550_vtube_studio_operator_acceptance.py",
    "scripts/check_v550_vtube_studio_constructor_corrective.py",
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

SYNC_SMOKE = (
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py"
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
    return path.read_text(encoding="utf-8", errors="strict")


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
        f"FW-VTS-0f2 requires HEAD {EXPECTED_HEAD}, found {head}",
    )
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    _require(
        origin_main == EXPECTED_HEAD,
        "origin/main does not match the accepted FW-VTS-0f2 baseline",
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
        "FW-VTS-0f2 exact surface mismatch: "
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
        "frozen runtime/operator/release surface changed: "
        + ", ".join(frozen_hits),
    )
    _ok("FW-VTS-0f2 baseline and exact eight-file surface match")


def _validate_generated_files_absent() -> None:
    tracked = _git_lines("ls-files")
    for relative in GENERATED_TTS_INVENTORY:
        _require(
            relative not in tracked,
            f"generated TTS inventory is tracked: {relative}",
        )
        _require(
            not (ROOT / relative).exists(),
            f"generated TTS inventory exists: {relative}",
        )
    _ok("generated TTS inventory files remain outside repo")


def _validate_sync_smoke_source() -> None:
    source = _read(SYNC_SMOKE)
    tree = ast.parse(source, filename=SYNC_SMOKE)
    import_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
        ):
            import_roots.add(node.module.split(".", 1)[0])

    forbidden_roots = {
        "pyvts",
        "websocket",
        "websockets",
        "socket",
        "asyncio",
        "json",
        "subprocess",
        "framework",
        "live2d",
    }
    _require(
        not (import_roots & forbidden_roots),
        "acceptance-sync smoke imports runtime/network/private-evidence modules",
    )

    for forbidden in (
        "open(",
        "read_bytes(",
        "write_text(",
        "write_bytes(",
        "os.getenv",
        "os.environ",
        "LOCALAPPDATA",
        "v550_vts_acceptance_",
        "bootstrap_evidence.json",
        "real_motion_operator_evidence.json",
    ):
        _require(
            forbidden not in source,
            f"acceptance-sync smoke contains forbidden private operation: {forbidden}",
        )
    _ok("acceptance-sync smoke remains static and source-only")


def _validate_docs() -> None:
    for relative in DOC_PATHS:
        source = _read(relative)
        for marker in (
            "FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:BEGIN",
            "checkpoint: FW-VTS-0f2",
            "private evidence: ACCEPTED_BY_VALIDATOR",
            "required four intents: VERIFIED",
            "stop_motion_supported: False",
            "stop_motion_verified: False",
            "private values recorded in repository: False",
            "commit / push: NOT_AUTHORIZED",
            "FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:END",
        ):
            _require(
                marker in source,
                f"{relative} missing acceptance-sync marker: {marker}",
            )
    _ok("six public documents contain the accepted safe marker block")


def _run_validation() -> None:
    commands = (
        (
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "framework",
            "scripts",
            "examples",
        ),
        (
            sys.executable,
            "scripts/smoke_v550_motion_session_real_adapter_composition.py",
        ),
        (
            sys.executable,
            "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
        ),
        (
            sys.executable,
            SYNC_SMOKE,
        ),
    )

    outputs: list[str] = []
    for command in commands:
        result = _run(*command, check=False)
        _require(
            result.returncode == 0,
            "source-only validation command failed without exposing raw output",
        )
        outputs.append(result.stdout)

    composition_output = outputs[1]
    operator_output = outputs[2]
    sync_output = outputs[3]

    _require(
        "[OK] FW-VTS-0e MotionSession composition smoke passed"
        in composition_output,
        "composition smoke pass marker missing",
    )
    for marker in (
        "v550_vtube_studio_optional_stop_corrective_smoke: PASS",
        "v550_required_four_intents: True",
        "v550_optional_stop_motion_contract: True",
        "v550_actual_pyvts_imported_in_smoke: False",
        "v550_websocket_connected_in_smoke: False",
        "v550_real_motion_executed_in_smoke: False",
    ):
        _require(
            marker in operator_output,
            f"optional-stop smoke marker missing: {marker}",
        )
    for marker in (
        "v550_vtube_studio_real_motion_acceptance_sync_smoke: PASS",
        "v550_acceptance_sync_blocks_identical: True",
        "v550_private_values_recorded: False",
        "v550_network_execution_in_smoke: False",
        "v550_real_motion_execution_in_smoke: False",
        "v550_private_evidence_read_in_smoke: False",
    ):
        _require(
            marker in sync_output,
            f"acceptance-sync smoke marker missing: {marker}",
        )
    _ok("compileall and all FW-VTS source-only smokes pass")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_sync_smoke_source()
    _validate_docs()
    _run_validation()

    print("v550_vtube_studio_real_motion_acceptance_sync_check: PASS")
    print("v550_exact_change_surface: True")
    print("v550_exact_change_file_count: 8")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_document_count: 6")
    print("v550_runtime_changed: False")
    print("v550_operator_changed: False")
    print("v550_verifier_changed: False")
    print("v550_token_bootstrap_changed: False")
    print("v550_constructor_corrective_changed: False")
    print("v550_private_file_tracked: False")
    print("v550_acceptance_sync_blocks_consistent: True")
    print("v550_actual_pyvts_imported_during_sync: False")
    print("v550_network_execution_during_sync: False")
    print("v550_real_motion_execution_during_sync: False")
    print("v550_private_evidence_read_during_sync: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print("v550_next_authorization: review-and-commit-FW-VTS-0f2")
    print("[OK] FW-VTS-0f2 exact acceptance-sync checker passed")


if __name__ == "__main__":
    main()
