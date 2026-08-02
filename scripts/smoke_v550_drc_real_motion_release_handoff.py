"""v5.5.0 DRC real-motion release-handoff source-only smoke."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = "77a6a679f35cbf03fffeff7e8fee8a1c8863fc26"

EXACT_CHECKPOINT_SURFACE = {
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

CHECKPOINT_BEGIN = "<!-- FW-VTS-0f4b-FINAL-TAG-READINESS:BEGIN -->"
CHECKPOINT_END = "<!-- FW-VTS-0f4b-FINAL-TAG-READINESS:END -->"

DOC_PATH = "docs/v550_drc_real_motion_release_handoff.md"
RELEASE_NOTES_PATH = "docs/release_notes_v5.5.0.md"

PUBLIC_SYMBOLS = (
    "MotionRequest",
    "MotionResult",
    "MotionCapability",
    "MotionErrorCode",
    "MotionIntent",
    "create_motion_session",
)

FORBIDDEN_PUBLIC_HANDOFF_TEXT = (
    "from framework.motion import",
    "from framework.motion_session import",
    "from framework.vtube_studio",
    "from live2d import",
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


def _validate_repository() -> str:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    branch = _run("git", "branch", "--show-current").stdout.strip()

    _require(branch == "main", f"expected main branch, found: {branch}")
    _require(
        _is_ancestor(BASELINE_HEAD, head),
        "FW-VTS-0f4b baseline is not an ancestor of HEAD",
    )
    _require(
        _is_ancestor(BASELINE_HEAD, origin_main),
        "FW-VTS-0f4b baseline is not an ancestor of origin/main",
    )

    changed = _changed_paths()
    if changed:
        _require(
            head == BASELINE_HEAD,
            "dirty DRC-handoff mode requires exact FW-VTS-0f4a HEAD",
        )
        _require(
            origin_main == BASELINE_HEAD,
            "dirty DRC-handoff mode requires origin/main at FW-VTS-0f4a",
        )
        _require(
            changed == EXACT_CHECKPOINT_SURFACE,
            "DRC handoff worktree is not exact: " + ", ".join(sorted(changed)),
        )
        return "checkpoint-worktree"

    _require(
        head == origin_main,
        "clean DRC-handoff mode requires HEAD and origin/main to match",
    )
    return "clean-committed"


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing DRC handoff source: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _validate_docs() -> None:
    handoff = _read(DOC_PATH)
    notes = _read(RELEASE_NOTES_PATH)
    combined = handoff + "\n" + notes

    for marker in (
        "DRC RT-7: READY_AFTER_V5.5.0_TAG_PUSH",
        "DRC pins a fixed released Framework artifact or tag",
        "from framework import",
        'create_motion_session(',
        'adapter="vts"',
        "real_adapter_enabled=True",
        "allow_provider_execution=True",
        "expression: VERIFIED",
        "emotion: VERIFIED",
        "gesture: VERIFIED",
        "reset_expression: VERIFIED",
        "stop_motion_supported: False",
        "stop_motion_verified: False",
        "speaking_state: do not assume support",
        "idle_motion: do not assume support",
        "look_at: do not assume support",
        "DRC must not",
        "v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag",
        "v550_drc_rt7_public_only_contract_fixed: True",
        "v550_drc_stop_motion_optional: True",
    ):
        _require(marker in combined, f"DRC handoff marker missing: {marker}")

    for forbidden in FORBIDDEN_PUBLIC_HANDOFF_TEXT:
        _require(
            forbidden not in handoff,
            f"DRC handoff contains an internal import example: {forbidden}",
        )

    for relative in (
        "README.md",
        "docs/v550_release_readiness_gate.md",
        "docs/v550_real_motion_adapter_readiness.md",
        "docs/v550_final_release_tag_readiness.md",
    ):
        source = _read(relative)
        _require(
            source.count(CHECKPOINT_BEGIN) == 1,
            f"FW-VTS-0f4b begin marker count is wrong in {relative}",
        )
        _require(
            source.count(CHECKPOINT_END) == 1,
            f"FW-VTS-0f4b end marker count is wrong in {relative}",
        )

    _ok("DRC release-handoff documentation is fixed and public-only")


def _validate_public_import() -> None:
    for name in ("pyvts", "websocket", "websockets"):
        _require(name not in sys.modules, f"{name} loaded before root import")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import framework

    public = getattr(framework, "__all__", ())
    for symbol in PUBLIC_SYMBOLS:
        _require(hasattr(framework, symbol), f"Framework root missing {symbol}")
        _require(symbol in public, f"framework.__all__ missing {symbol}")

    for name in ("pyvts", "websocket", "websockets"):
        _require(
            name not in sys.modules,
            f"Framework root import loaded provider/VTS module: {name}",
        )

    _ok("Framework root-public motion import remains provider-safe")


def main() -> None:
    mode = _validate_repository()
    _validate_docs()
    _validate_public_import()

    print("v550_drc_real_motion_handoff_status: ready-after-v5.5.0-tag")
    print(f"v550_drc_handoff_worktree_mode: {mode}")
    print("v550_drc_rt7_public_only_contract_fixed: True")
    print("v550_drc_fixed_release_artifact_required: True")
    print("v550_drc_required_four_intents_fixed: True")
    print("v550_drc_stop_motion_optional: True")
    print("v550_drc_unsupported_intents_not_assumed: True")
    print("v550_drc_internal_import_allowed: False")
    print("v550_drc_pyvts_ownership_allowed: False")
    print("v550_drc_websocket_ownership_allowed: False")
    print("v550_drc_token_ownership_allowed: False")
    print("v550_drc_raw_payload_handling_allowed: False")
    print("v550_actual_pyvts_imported_in_handoff_smoke: False")
    print("v550_network_execution_in_handoff_smoke: False")
    print("v550_real_motion_execution_in_handoff_smoke: False")
    print("v550_private_evidence_read_in_handoff_smoke: False")
    print("v550_drc_repository_changed: False")
    _ok("v5.5.0 DRC real-motion release handoff passed")


if __name__ == "__main__":
    main()
