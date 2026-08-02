"""FW-VTS-0f4a exact seven-file package-gate checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "a83f7efe85d489887b1d97122b2756e2a1b57ff5"

EXACT_SURFACE = {
    "README.md",
    "docs/v550_release_readiness_gate.md",
    "docs/v550_release_package_gate.md",
    "scripts/build_v550_release_package.py",
    "scripts/smoke_v550_release_package_gate.py",
    "scripts/check_v550_release_package_gate.py",
    "scripts/smoke_v550_release_readiness_gate.py",
}

FROZEN_PREFIXES = (
    "framework/",
    "live2d/",
    "config/",
    "release/",
)

FROZEN_FILES = {
    "requirements.txt",
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
}

BEGIN_MARKER = "<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:BEGIN -->"
END_MARKER = "<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:END -->"

BUILDER_PATH = "scripts/build_v550_release_package.py"
READINESS_PATH = "scripts/smoke_v550_release_readiness_gate.py"
PACKAGE_SMOKE_PATH = "scripts/smoke_v550_release_package_gate.py"


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
    _require(path.is_file(), f"missing FW-VTS-0f4a source: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _assignment(tree: ast.AST, name: str) -> Any:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise AssertionError(f"assignment not found: {name}")


def _validate_repository() -> None:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    branch = _run("git", "branch", "--show-current").stdout.strip()

    _require(head == EXPECTED_HEAD, f"expected HEAD {EXPECTED_HEAD}, found {head}")
    _require(
        origin_main == EXPECTED_HEAD,
        "origin/main does not match FW-VTS-0f4a baseline",
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
        "FW-VTS-0f4a exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )

    frozen_hits = sorted(
        path
        for path in changed
        if path in FROZEN_FILES
        or any(path.startswith(prefix) for prefix in FROZEN_PREFIXES)
    )
    _require(
        not frozen_hits,
        "frozen runtime/operator/release path changed: " + ", ".join(frozen_hits),
    )
    _ok("FW-VTS-0f4a baseline and exact seven-file surface match")


def _validate_docs() -> None:
    for relative in (
        "README.md",
        "docs/v550_release_readiness_gate.md",
        "docs/v550_release_package_gate.md",
    ):
        source = _read(relative)
        _require(
            source.count(BEGIN_MARKER) == 1,
            f"package-gate begin marker count is wrong in {relative}",
        )
        _require(
            source.count(END_MARKER) == 1,
            f"package-gate end marker count is wrong in {relative}",
        )
        for marker in (
            "checkpoint: FW-VTS-0f4a",
            f"baseline head: {EXPECTED_HEAD}",
            "tracked private VTS artifact rejection: REQUIRED",
            "final release ZIP created: False",
            "next authorization: READY_FOR_FW-VTS-0f4b_AFTER_REVIEW",
        ):
            _require(
                marker in source,
                f"package-gate documentation marker missing: {marker}",
            )
    _ok("FW-VTS-0f4a public package-gate documentation is complete")


def _validate_builder() -> None:
    source = _read(BUILDER_PATH)
    tree = ast.parse(source, filename=BUILDER_PATH)

    _require(_assignment(tree, "VERSION") == "5.5.0", "builder version is not 5.5.0")
    required = set(_assignment(tree, "REQUIRED_PACKAGE_FILES"))
    for relative in (
        "docs/v550_release_package_gate.md",
        "scripts/build_v550_release_package.py",
        "scripts/smoke_v550_release_package_gate.py",
        "scripts/check_v550_release_package_gate.py",
        "scripts/smoke_v550_release_readiness_gate.py",
        "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
        "scripts/verify_v550_vtube_studio_private_evidence.py",
    ):
        _require(
            relative in required,
            f"builder required-package set missing: {relative}",
        )

    prefixes = set(_assignment(tree, "PRIVATE_TRACKED_PREFIXES"))
    basenames = set(_assignment(tree, "PRIVATE_TRACKED_BASENAMES"))
    _require("config/tokens/" in prefixes, "builder does not reject config/tokens/")
    _require("operator_evidence/" in prefixes, "builder does not reject operator_evidence/")
    for basename in (
        "vts_private_config.json",
        "bootstrap_evidence.json",
        "real_motion_operator_evidence.json",
    ):
        _require(
            basename in basenames,
            f"builder private basename missing: {basename}",
        )

    for marker in (
        'basename.endswith("_token.json")',
        "ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)",
        "compresslevel=9",
        "private_tracked_hits(tracked)",
        "source.read_bytes()",
        'f"{digest}  {output.name}\\n"',
    ):
        _require(marker in source, f"builder deterministic/private marker missing: {marker}")

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported_roots.add(node.module.split(".", 1)[0])
    _require(
        not imported_roots & {"pyvts", "websocket", "websockets", "live2d"},
        "builder imports provider/VTS runtime modules",
    )
    _ok("v5.5.0 builder is deterministic and hard-rejects tracked private VTS paths")


def _validate_readiness_update() -> None:
    source = _read(READINESS_PATH)
    tree = ast.parse(source, filename=READINESS_PATH)

    package_surface = set(_assignment(tree, "PACKAGE_GATE_SURFACE"))
    package_baseline = _assignment(tree, "PACKAGE_GATE_BASELINE_HEAD")
    _require(package_surface == EXACT_SURFACE, "readiness package-gate surface is not exact")
    _require(package_baseline == EXPECTED_HEAD, "readiness package-gate baseline is wrong")

    for marker in (
        "--allow-final-package",
        "v550_release_readiness_final_package_allowed:",
        "v550_release_readiness_final_artifacts_unchanged: True",
        "package-gate-worktree",
        "_assert_release_artifacts_unchanged",
    ):
        _require(marker in source, f"readiness final-package marker missing: {marker}")
    _ok("source-tree readiness supports package-gate and strict final-package modes")


def _validate_source_only() -> None:
    for relative in (PACKAGE_SMOKE_PATH, "scripts/check_v550_release_package_gate.py"):
        source = _read(relative)
        tree = ast.parse(source, filename=relative)
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".", 1)[0])
        _require(
            not roots & {"pyvts", "websocket", "websockets", "live2d"},
            f"package-gate source imports provider/VTS runtime: {relative}",
        )
    _ok("package-gate smoke and checker remain source-only")


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

    readiness = _run(
        sys.executable,
        READINESS_PATH,
        check=False,
    )
    if readiness.returncode != 0:
        if readiness.stdout:
            print(readiness.stdout)
        if readiness.stderr:
            print(readiness.stderr, file=sys.stderr)
        raise AssertionError("updated v5.5.0 source-tree readiness gate failed")

    for marker in (
        "v550_release_readiness_gate_status: accepted",
        "v550_release_readiness_worktree_mode: package-gate-worktree",
        "v550_release_readiness_final_package_allowed: False",
        "v550_release_readiness_final_artifacts_unchanged: True",
        "v550_actual_pyvts_imported_in_gate: False",
        "v550_network_execution_in_gate: False",
        "v550_real_motion_execution_in_gate: False",
    ):
        _require(marker in readiness.stdout, f"readiness marker missing: {marker}")

    package = _run(
        sys.executable,
        PACKAGE_SMOKE_PATH,
        check=False,
    )
    if package.returncode != 0:
        if package.stdout:
            print(package.stdout)
        if package.stderr:
            print(package.stderr, file=sys.stderr)
        raise AssertionError("FW-VTS-0f4a package-gate smoke failed")

    for marker in (
        "v550_release_package_gate_status: accepted",
        "v550_release_package_dry_run_succeeded: True",
        "v550_release_package_deterministic: True",
        "v550_release_package_file_set_exact: True",
        "v550_release_package_created_in_release_dir: False",
        "v550_release_package_rejects_config_tokens: True",
        "v550_release_package_rejects_token_json: True",
        "v550_release_package_rejects_private_config: True",
        "v550_release_package_rejects_private_evidence: True",
        "v550_actual_pyvts_imported_in_package_gate: False",
        "v550_network_execution_in_package_gate: False",
        "v550_private_token_read_in_package_gate: False",
        "v550_private_evidence_read_in_package_gate: False",
        "v550_real_motion_execution_in_package_gate: False",
        "v550_next_authorization: ready-for-FW-VTS-0f4b",
        "[OK] FW-VTS-0f4a deterministic release-package gate passed",
    ):
        _require(marker in package.stdout, f"package-gate marker missing: {marker}")

    _ok("compileall, readiness, and deterministic package gate pass")


def main() -> None:
    _validate_repository()
    _validate_docs()
    _validate_builder()
    _validate_readiness_update()
    _validate_source_only()
    _run_validation()

    print("v550_release_package_gate_exact_contract_check: PASS")
    print("v550_exact_change_surface: True")
    print("v550_exact_change_file_count: 7")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_document_change_count: 3")
    print("v550_new_builder_count: 1")
    print("v550_new_smoke_count: 1")
    print("v550_new_checker_count: 1")
    print("v550_runtime_changed: False")
    print("v550_operator_changed: False")
    print("v550_private_verifier_changed: False")
    print("v550_requirements_changed: False")
    print("v550_release_artifact_changed: False")
    print("v550_private_vts_artifact_tracked: False")
    print("v550_actual_pyvts_imported_during_gate: False")
    print("v550_network_execution_during_gate: False")
    print("v550_private_evidence_read_during_gate: False")
    print("v550_real_motion_execution_during_gate: False")
    print("v550_release_package_created: False")
    print("v550_tag_created: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print("v550_next_authorization: review-and-commit-FW-VTS-0f4a")
    _ok("FW-VTS-0f4a exact package-gate checker passed")


if __name__ == "__main__":
    main()
