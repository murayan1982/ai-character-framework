"""v5.5.0 final release tag-readiness gate.

Local checkpoint mode:
    python scripts/smoke_v550_final_release_tag_readiness.py --allow-dirty

Strict pre-tag mode:
    python scripts/smoke_v550_final_release_tag_readiness.py \
        --require-clean-tree --require-package
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "5.5.0"
TAG = f"v{VERSION}"
BASELINE_HEAD = "77a6a679f35cbf03fffeff7e8fee8a1c8863fc26"
PACKAGE = ROOT / "release" / f"ai-character-framework_v{VERSION}.zip"
SIDECAR = PACKAGE.with_suffix(PACKAGE.suffix + ".sha256")

CHECKPOINT_SURFACE = {
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

REQUIRED_PACKAGE_ENTRIES = {
    "README.md",
    "docs/RELEASE_NOTES.md",
    "docs/release_notes_v5.5.0.md",
    "docs/v550_release_readiness_gate.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_release_package_gate.md",
    "docs/v550_final_release_tag_readiness.md",
    "docs/v550_drc_real_motion_release_handoff.md",
    "scripts/build_v550_release_package.py",
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/smoke_v550_release_package_gate.py",
    "scripts/smoke_v550_final_release_tag_readiness.py",
    "scripts/smoke_v550_drc_real_motion_release_handoff.py",
    "scripts/check_v550_final_release_tag_readiness.py",
}

FORBIDDEN_MODULES = ("pyvts", "websocket", "websockets", "live2d.vts_client")


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


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    result = _run(
        "git",
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        check=False,
    )
    return result.returncode == 0


def _load_builder():
    path = ROOT / "scripts" / "build_v550_release_package.py"
    spec = importlib.util.spec_from_file_location(
        "build_v550_release_package",
        path,
    )
    _require(
        spec is not None and spec.loader is not None,
        "could not load v5.5.0 release-package builder",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing final tag-readiness source: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _validate_docs() -> None:
    current_notes = _read("docs/RELEASE_NOTES.md")
    fixed_notes = _read("docs/release_notes_v5.5.0.md")
    readiness = _read("docs/v550_final_release_tag_readiness.md")
    handoff = _read("docs/v550_drc_real_motion_release_handoff.md")
    combined = "\n".join((current_notes, fixed_notes, readiness, handoff))

    for marker in (
        "CURRENT-RELEASE-v5.5.0:BEGIN",
        "# v5.5.0 - Real Motion Adapter / VTube Studio",
        "docs/release_notes_v5.5.0.md",
        "# AI Character Framework v5.5.0 Release Notes",
        "Real Motion Adapter / VTube Studio",
        "FW-VTS-0f4a: ACCEPTED / PUSHED",
        "FW-VTS-0f4b: IMPLEMENTED / AWAITING_REVIEW",
        "DRC RT-7: READY_AFTER_V5.5.0_TAG_PUSH",
        "v550_final_package_rebuild_required_after_checkpoint_commit: True",
        "v550_tag_authorization: ready-after-strict-package-verification",
        "v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag",
        "v550_drc_rt7_public_only_contract_fixed: True",
        "stop_motion_supported: False",
        "stop_motion_verified: False",
    ):
        _require(marker in combined, f"final tag-readiness docs missing: {marker}")

    _ok("v5.5.0 release notes, final readiness, and DRC handoff are present")


def _validate_git_state(
    *,
    allow_dirty: bool,
    require_clean_tree: bool,
) -> tuple[str, set[str], str]:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    branch = _run("git", "branch", "--show-current").stdout.strip()
    origin = _run("git", "remote", "get-url", "origin").stdout.strip()

    _require(branch == "main", f"expected main branch, found: {branch}")
    _require(
        "ai-character-framework" in origin.casefold(),
        "origin is not AI Character Framework",
    )
    _require(
        _is_ancestor(BASELINE_HEAD, head),
        "FW-VTS-0f4b baseline is not an ancestor of HEAD",
    )
    _require(
        _is_ancestor(BASELINE_HEAD, origin_main),
        "FW-VTS-0f4b baseline is not an ancestor of origin/main",
    )

    changed = _changed_paths()
    if allow_dirty:
        _require(head == BASELINE_HEAD, "dirty mode requires exact FW-VTS-0f4a HEAD")
        _require(
            origin_main == BASELINE_HEAD,
            "dirty mode requires origin/main at FW-VTS-0f4a",
        )
        _require(
            changed == CHECKPOINT_SURFACE,
            "local checkpoint surface differs from exact ten files: "
            + ", ".join(sorted(changed)),
        )
        mode = "checkpoint-worktree"
    elif require_clean_tree:
        _require(not changed, "strict final tag readiness requires a clean tree")
        _require(
            head == origin_main,
            "strict final tag readiness requires HEAD and origin/main to match",
        )
        mode = "clean-committed"
    else:
        _require(not changed, "working tree is dirty; use --allow-dirty only for checkpoint mode")
        _require(head == origin_main, "clean mode requires HEAD and origin/main to match")
        mode = "clean-committed"

    tag = _run("git", "tag", "--list", TAG).stdout.strip()
    _require(not tag, f"{TAG} already exists")

    return head, changed, mode


def _validate_package_set(builder, changed: set[str]) -> list[str]:
    files = builder.package_files(
        ROOT,
        additional_files=changed,
    )
    missing = sorted(REQUIRED_PACKAGE_ENTRIES - set(files))
    _require(
        not missing,
        "package set missing final tag-readiness entries: " + ", ".join(missing),
    )
    private_hits = builder.private_tracked_hits(files)
    _require(
        not private_hits,
        "package set contains private VTS paths: " + ", ".join(private_hits),
    )
    _ok("current package set includes all v5.5.0 final readiness sources")
    return files


def _parse_sidecar() -> tuple[str, str]:
    text = SIDECAR.read_text(encoding="utf-8", errors="strict").strip()
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s{2}(.+)", text)
    _require(match is not None, "SHA-256 sidecar format is invalid")
    assert match is not None
    return match.group(1).lower(), match.group(2)


def _run_dependency(script: str, *extra: str) -> None:
    completed = _run(
        sys.executable,
        script,
        *extra,
        check=False,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        raise AssertionError(f"strict final tag dependency failed: {script}")
    print(f"[OK] strict final tag dependency passed: {script}")


def _validate_final_package(builder, expected_files: list[str]) -> str:
    _require(PACKAGE.is_file(), f"missing final package: {PACKAGE}")
    _require(SIDECAR.is_file(), f"missing final SHA-256 sidecar: {SIDECAR}")

    expected_hash, sidecar_name = _parse_sidecar()
    _require(sidecar_name == PACKAGE.name, "sidecar filename does not match ZIP")

    final_bytes = PACKAGE.read_bytes()
    actual_hash = hashlib.sha256(final_bytes).hexdigest()
    _require(actual_hash == expected_hash, "final ZIP SHA-256 does not match sidecar")

    with zipfile.ZipFile(PACKAGE, "r") as archive:
        names = archive.namelist()
        bad = archive.testzip()

    _require(bad is None, f"ZIP integrity failure at: {bad}")
    _require(len(names) == len(set(names)), "final ZIP contains duplicate entries")
    _require(
        names == expected_files,
        "final ZIP membership/order does not match current committed package set",
    )

    missing = sorted(REQUIRED_PACKAGE_ENTRIES - set(names))
    _require(
        not missing,
        "final ZIP missing final readiness entries: " + ", ".join(missing),
    )
    _require(
        not builder.private_tracked_hits(names),
        "final ZIP contains private VTS path names",
    )
    _require(
        ".vscode/settings.json" not in names,
        "final ZIP contains local VS Code settings",
    )
    _require(
        not any(name.startswith("release/") for name in names),
        "final ZIP contains generated release artifacts",
    )
    _require(
        not any(name.casefold().endswith(".wav") for name in names),
        "final ZIP contains WAV audio",
    )

    with tempfile.TemporaryDirectory(
        prefix="acf_v550_final_tag_verify_"
    ) as temporary:
        rebuilt = Path(temporary) / builder.PACKAGE_BASENAME
        rebuilt_hash, rebuilt_count = builder.build_package(
            rebuilt,
            root=ROOT,
        )
        _require(
            rebuilt_count == len(expected_files),
            "deterministic rebuild file count mismatch",
        )
        _require(rebuilt_hash == actual_hash, "deterministic rebuild SHA-256 differs")
        _require(
            rebuilt.read_bytes() == final_bytes,
            "deterministic rebuild bytes differ from final ZIP",
        )

    _ok("final v5.5.0 ZIP and sidecar match current committed HEAD")
    _ok("final package exact membership and deterministic rebuild passed")
    return actual_hash


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run v5.5.0 final release tag-readiness checks"
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow only the exact uncommitted FW-VTS-0f4b ten-file surface",
    )
    parser.add_argument(
        "--require-clean-tree",
        action="store_true",
        help="require clean committed HEAD matching origin/main",
    )
    parser.add_argument(
        "--require-package",
        action="store_true",
        help="require and strictly verify final v5.5.0 ZIP and sidecar",
    )
    args = parser.parse_args(argv)

    _require(
        not (args.allow_dirty and args.require_clean_tree),
        "--allow-dirty and --require-clean-tree are mutually exclusive",
    )
    _require(
        args.require_package == args.require_clean_tree,
        "--require-package and --require-clean-tree must be used together",
    )

    for name in FORBIDDEN_MODULES:
        _require(name not in sys.modules, f"forbidden module loaded before gate: {name}")

    _validate_docs()
    head, changed, mode = _validate_git_state(
        allow_dirty=args.allow_dirty,
        require_clean_tree=args.require_clean_tree,
    )

    builder = _load_builder()
    expected_files = _validate_package_set(builder, changed)

    _run_dependency("scripts/smoke_v550_drc_real_motion_release_handoff.py")

    package_hash = "not-required-in-local-checkpoint"
    strict_ready = bool(args.require_clean_tree and args.require_package)
    if strict_ready:
        _run_dependency(
            "scripts/smoke_v550_release_package_gate.py",
            "--allow-final-package",
        )
        package_hash = _validate_final_package(builder, expected_files)
    else:
        _require(
            not PACKAGE.exists() and not SIDECAR.exists(),
            "checkpoint mode requires absent final v5.5.0 ZIP and sidecar",
        )
        _ok("final package rebuild and strict verification are deferred until commit")

    for name in FORBIDDEN_MODULES:
        _require(name not in sys.modules, f"forbidden module loaded during gate: {name}")

    print("v550_final_tag_readiness_status: accepted")
    print(f"v550_final_tag_readiness_head: {head}")
    print(f"v550_final_tag_readiness_worktree_mode: {mode}")
    print(f"v550_final_package_sha256: {package_hash}")
    print("v550_release_notes_present: True")
    print("v550_current_release_notes_version: 5.5.0")
    print("v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag")
    print("v550_drc_rt7_public_only_contract_fixed: True")
    print("v550_drc_stop_motion_optional: True")
    print(
        "v550_final_package_rebuild_required_after_checkpoint_commit:",
        not strict_ready,
    )
    print(
        "v550_final_package_verified_for_current_head:",
        strict_ready,
    )
    print("v550_actual_pyvts_imported_in_final_gate: False")
    print("v550_network_execution_in_final_gate: False")
    print("v550_private_token_read_in_final_gate: False")
    print("v550_private_evidence_read_in_final_gate: False")
    print("v550_real_motion_execution_in_final_gate: False")
    print("v550_drc_repo_changed: False")
    print("v550_tag_created: False")
    print("v550_push_performed: False")
    print("v550_publish_performed: False")
    print("v550_tag_authorization: ready-after-strict-package-verification")
    _ok("v5.5.0 final release tag-readiness gate passed")


if __name__ == "__main__":
    main()
