"""FW-VTS-0f3c1 dependency-sync corrective checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "4f643b7cfa4e77c71ba6a0a857ceb390beb7397e"

EXACT_SURFACE = {
    "docs/v550_release_readiness_gate.md",
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/check_v550_release_readiness_dependency_sync_corrective.py",
}

EXPECTED_DEPENDENCIES = (
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v550_vtube_studio_transport_protocol_fake.py",
    "scripts/smoke_v550_vtube_studio_pyvts_transport.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/check_release_package.py",
)

HISTORICAL_INCOMPATIBLE_DEPENDENCIES = (
    "scripts/smoke_public_facade.py",
    "scripts/smoke_v550_real_motion_adapter_readiness.py",
    "scripts/smoke_v550_motion_adapter_configuration_status.py",
)

DOC_PATH = "docs/v550_release_readiness_gate.md"
SMOKE_PATH = "scripts/smoke_v550_release_readiness_gate.py"
BEGIN_MARKER = "<!-- FW-VTS-0f3c1-DEPENDENCY-SYNC:BEGIN -->"
END_MARKER = "<!-- FW-VTS-0f3c1-DEPENDENCY-SYNC:END -->"


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
    _require(path.is_file(), f"missing corrective file: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _assignment(tree: ast.AST, name: str) -> Any:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"smoke assignment not found: {name}")


def _validate_repository() -> None:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    branch = _run("git", "branch", "--show-current").stdout.strip()

    _require(
        head == EXPECTED_HEAD,
        f"FW-VTS-0f3c1 requires HEAD {EXPECTED_HEAD}, found {head}",
    )
    _require(
        origin_main == EXPECTED_HEAD,
        "origin/main does not match the FW-VTS-0f3c1 baseline",
    )
    _require(branch == "main", f"expected main branch, found: {branch}")

    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require(
        "ai-character-framework" in origin.casefold(),
        "origin is not AI Character Framework",
    )

    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-VTS-0f3c1 exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )
    _ok("FW-VTS-0f3c1 baseline and exact three-file surface match")


def _validate_smoke_contract() -> None:
    source = _read(SMOKE_PATH)
    tree = ast.parse(source, filename=SMOKE_PATH)

    dependencies = tuple(_assignment(tree, "DEPENDENCIES"))
    historical = tuple(
        _assignment(tree, "HISTORICAL_INCOMPATIBLE_DEPENDENCIES")
    )
    corrective_surface = set(_assignment(tree, "CORRECTIVE_SURFACE"))
    corrective_baseline = _assignment(tree, "CORRECTIVE_BASELINE_HEAD")

    _require(
        dependencies == EXPECTED_DEPENDENCIES,
        "readiness dependency tuple does not match exact seven-file contract",
    )
    _require(
        historical == HISTORICAL_INCOMPATIBLE_DEPENDENCIES,
        "historical dependency exclusions do not match the corrective contract",
    )
    _require(
        not set(dependencies) & set(historical),
        "historical incompatible dependency remains executable",
    )
    _require(
        corrective_surface == EXACT_SURFACE,
        "readiness smoke corrective surface is not exact",
    )
    _require(
        corrective_baseline == EXPECTED_HEAD,
        "readiness smoke corrective baseline is incorrect",
    )

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
        ):
            imported_roots.add(node.module.split(".", 1)[0])

    _require(
        not imported_roots
        & {"pyvts", "websocket", "websockets", "live2d"},
        "corrected readiness smoke imports provider/VTS runtime modules",
    )
    _ok("readiness smoke has exact current-compatible dependencies")


def _validate_documentation() -> None:
    source = _read(DOC_PATH)
    _require(
        source.count(BEGIN_MARKER) == 1,
        "dependency-sync begin marker must appear exactly once",
    )
    _require(
        source.count(END_MARKER) == 1,
        "dependency-sync end marker must appear exactly once",
    )
    _, remainder = source.split(BEGIN_MARKER, 1)
    section, _ = remainder.split(END_MARKER, 1)

    for relative in EXPECTED_DEPENDENCIES:
        _require(
            relative in section,
            f"public dependency list missing: {relative}",
        )
    for relative in HISTORICAL_INCOMPATIBLE_DEPENDENCIES:
        _require(
            relative in section,
            f"historical exclusion missing: {relative}",
        )

    for reason in (
        "pre-v5.2 exact",
        "pre-real-adapter",
        "earlier configuration checkpoint",
        "executable dependency tuple and this public list must remain identical",
    ):
        _require(
            reason in section,
            f"dependency rationale missing: {reason}",
        )

    _ok("public dependency documentation matches the executable tuple")


def _run_validation() -> None:
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
        SMOKE_PATH,
        check=False,
    )
    if smoke.returncode != 0:
        if smoke.stdout:
            print(smoke.stdout)
        if smoke.stderr:
            print(smoke.stderr, file=sys.stderr)
        raise AssertionError("corrected FW-VTS-0f3 readiness smoke failed")

    for marker in (
        "v550_release_readiness_gate_status: accepted",
        "v550_release_readiness_worktree_mode: corrective-worktree",
        "v550_release_readiness_dependency_count: 7",
        "v550_release_readiness_dependency_docs_synced: True",
        "v550_release_readiness_historical_exclusions_recorded: True",
        "v550_release_readiness_obsolete_dependency_executed: False",
        "v550_release_readiness_corrective_baseline_ancestor: True",
        "v550_actual_pyvts_imported_in_gate: False",
        "v550_network_execution_in_gate: False",
        "v550_private_token_read_in_gate: False",
        "v550_private_evidence_read_in_gate: False",
        "v550_real_motion_execution_in_gate: False",
        "v550_release_package_created: False",
        "v550_tag_created: False",
        "[OK] FW-VTS-0f3 v5.5.0 release-readiness gate passed",
    ):
        _require(
            marker in smoke.stdout,
            f"corrected readiness marker missing: {marker}",
        )

    _ok("compileall and corrected readiness gate pass")


def main() -> None:
    _validate_repository()
    _validate_smoke_contract()
    _validate_documentation()
    _run_validation()

    print("v550_release_readiness_dependency_sync_corrective: PASS")
    print("v550_exact_change_surface: True")
    print("v550_exact_change_file_count: 3")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_dependency_count: 7")
    print("v550_dependency_docs_synced: True")
    print("v550_historical_incompatible_dependencies_executed: False")
    print("v550_runtime_changed: False")
    print("v550_operator_changed: False")
    print("v550_private_verifier_changed: False")
    print("v550_package_builder_changed: False")
    print("v550_release_artifact_changed: False")
    print("v550_actual_pyvts_imported_during_corrective: False")
    print("v550_network_execution_during_corrective: False")
    print("v550_private_evidence_read_during_corrective: False")
    print("v550_real_motion_execution_during_corrective: False")
    print("v550_release_package_created: False")
    print("v550_tag_created: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print("v550_next_authorization: review-and-commit-FW-VTS-0f3c1")
    _ok("FW-VTS-0f3c1 dependency-sync corrective checker passed")


if __name__ == "__main__":
    main()
