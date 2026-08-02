"""FW-VTS-0f4b exact ten-file final-readiness checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "77a6a679f35cbf03fffeff7e8fee8a1c8863fc26"

EXACT_SURFACE = {
    'README.md',
    'docs/RELEASE_NOTES.md',
    'docs/release_notes_v5.5.0.md',
    'docs/v550_release_readiness_gate.md',
    'docs/v550_real_motion_adapter_readiness.md',
    'docs/v550_final_release_tag_readiness.md',
    'docs/v550_drc_real_motion_release_handoff.md',
    'scripts/smoke_v550_final_release_tag_readiness.py',
    'scripts/smoke_v550_drc_real_motion_release_handoff.py',
    'scripts/check_v550_final_release_tag_readiness.py'
}

FROZEN_PREFIXES = (
    "framework/",
    "live2d/",
    "config/",
    "release/",
)

FROZEN_FILES = {
    "requirements.txt",
    "scripts/build_v550_release_package.py",
    "scripts/smoke_v550_release_package_gate.py",
    "scripts/check_v550_release_package_gate.py",
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
}

FINAL_SMOKE = "scripts/smoke_v550_final_release_tag_readiness.py"
DRC_SMOKE = "scripts/smoke_v550_drc_real_motion_release_handoff.py"


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
    _require(path.is_file(), f"missing FW-VTS-0f4b source: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _validate_repository() -> None:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    branch = _run("git", "branch", "--show-current").stdout.strip()

    _require(head == EXPECTED_HEAD, f"expected HEAD {EXPECTED_HEAD}, found {head}")
    _require(
        origin_main == EXPECTED_HEAD,
        "origin/main does not match the FW-VTS-0f4b baseline",
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
        "FW-VTS-0f4b exact surface mismatch: "
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
        "frozen runtime/package/operator path changed: " + ", ".join(frozen_hits),
    )

    tag = _run("git", "tag", "--list", "v5.5.0").stdout.strip()
    _require(not tag, "v5.5.0 tag already exists")

    final_zip = ROOT / "release" / "ai-character-framework_v5.5.0.zip"
    sidecar = final_zip.with_suffix(final_zip.suffix + ".sha256")
    _require(
        not final_zip.exists() and not sidecar.exists(),
        "FW-VTS-0f4b checkpoint must not contain final release artifacts",
    )
    _ok("FW-VTS-0f4b baseline and exact ten-file surface match")


def _validate_docs() -> None:
    current = _read("docs/RELEASE_NOTES.md")
    fixed = _read("docs/release_notes_v5.5.0.md")
    final_doc = _read("docs/v550_final_release_tag_readiness.md")
    handoff = _read("docs/v550_drc_real_motion_release_handoff.md")
    combined = "\n".join((current, fixed, final_doc, handoff))

    for marker in (
        "CURRENT-RELEASE-v5.5.0:BEGIN",
        "# v5.5.0 - Real Motion Adapter / VTube Studio",
        "# AI Character Framework v5.5.0 Release Notes",
        "checkpoint: FW-VTS-0f4b",
        f"baseline head: {EXPECTED_HEAD}",
        "final package rebuild required after checkpoint commit: True",
        "DRC RT-7: READY_AFTER_V5.5.0_TAG_PUSH",
        "v550_tag_authorization: ready-after-strict-package-verification",
        "v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag",
    ):
        _require(marker in combined, f"FW-VTS-0f4b documentation missing: {marker}")

    for relative in (
        "README.md",
        "docs/v550_release_readiness_gate.md",
        "docs/v550_real_motion_adapter_readiness.md",
        "docs/v550_final_release_tag_readiness.md",
    ):
        source = _read(relative)
        _require(
            source.count("<!-- FW-VTS-0f4b-FINAL-TAG-READINESS:BEGIN -->") == 1,
            f"FW-VTS-0f4b begin marker count wrong in {relative}",
        )
        _require(
            source.count("<!-- FW-VTS-0f4b-FINAL-TAG-READINESS:END -->") == 1,
            f"FW-VTS-0f4b end marker count wrong in {relative}",
        )

    _ok("v5.5.0 release notes, final tag readiness, and DRC handoff are complete")


def _validate_scripts_source_only() -> None:
    for relative in (FINAL_SMOKE, DRC_SMOKE, "scripts/check_v550_final_release_tag_readiness.py"):
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
            f"FW-VTS-0f4b source imports provider/VTS runtime: {relative}",
        )

    _ok("FW-VTS-0f4b smokes and checker remain source-only")


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

    drc = _run(sys.executable, DRC_SMOKE, check=False)
    if drc.returncode != 0:
        if drc.stdout:
            print(drc.stdout)
        if drc.stderr:
            print(drc.stderr, file=sys.stderr)
        raise AssertionError("v5.5.0 DRC handoff smoke failed")

    for marker in (
        "v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag",
        "v550_drc_handoff_worktree_mode: checkpoint-worktree",
        "v550_drc_rt7_public_only_contract_fixed: True",
        "v550_drc_stop_motion_optional: True",
        "v550_actual_pyvts_imported_in_handoff_smoke: False",
        "v550_network_execution_in_handoff_smoke: False",
        "v550_real_motion_execution_in_handoff_smoke: False",
    ):
        _require(marker in drc.stdout, f"DRC handoff marker missing: {marker}")

    final = _run(
        sys.executable,
        FINAL_SMOKE,
        "--allow-dirty",
        check=False,
    )
    if final.returncode != 0:
        if final.stdout:
            print(final.stdout)
        if final.stderr:
            print(final.stderr, file=sys.stderr)
        raise AssertionError("v5.5.0 final tag-readiness checkpoint smoke failed")

    for marker in (
        "v550_final_tag_readiness_status: accepted",
        "v550_final_tag_readiness_worktree_mode: checkpoint-worktree",
        "v550_release_notes_present: True",
        "v550_current_release_notes_version: 5.5.0",
        "v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag",
        "v550_final_package_rebuild_required_after_checkpoint_commit: True",
        "v550_final_package_verified_for_current_head: False",
        "v550_actual_pyvts_imported_in_final_gate: False",
        "v550_network_execution_in_final_gate: False",
        "v550_private_evidence_read_in_final_gate: False",
        "v550_tag_created: False",
        "v550_tag_authorization: ready-after-strict-package-verification",
        "[OK] v5.5.0 final release tag-readiness gate passed",
    ):
        _require(marker in final.stdout, f"final readiness marker missing: {marker}")

    _ok("compileall, DRC handoff, and final tag-readiness checkpoint pass")


def main() -> None:
    _validate_repository()
    _validate_docs()
    _validate_scripts_source_only()
    _run_validation()

    print("v550_final_release_tag_readiness_exact_contract_check: PASS")
    print("v550_exact_change_surface: True")
    print("v550_exact_change_file_count: 10")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_modified_existing_file_count: 4")
    print("v550_new_file_count: 6")
    print("v550_release_notes_present: True")
    print("v550_drc_handoff_present: True")
    print("v550_runtime_changed: False")
    print("v550_operator_changed: False")
    print("v550_private_verifier_changed: False")
    print("v550_requirements_changed: False")
    print("v550_package_builder_changed: False")
    print("v550_package_gate_changed: False")
    print("v550_release_artifact_changed: False")
    print("v550_actual_pyvts_imported_during_checkpoint: False")
    print("v550_network_execution_during_checkpoint: False")
    print("v550_private_evidence_read_during_checkpoint: False")
    print("v550_real_motion_execution_during_checkpoint: False")
    print("v550_release_package_created: False")
    print("v550_tag_created: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print("v550_next_authorization: review-and-commit-FW-VTS-0f4b")
    _ok("FW-VTS-0f4b exact final-readiness checker passed")


if __name__ == "__main__":
    main()
