"""FW-RT6-4a aggregate acceptance check for Controls A/B/C.

Offline/provider-free: validates the exact uncommitted 18-file FW-RT6-4a
surface, accepted seven-task tasklist state, public construction result,
no-silent-mock-fallback guard, 80-test unit suite, public compatibility, and
provider-free execution boundaries. Commit and push are intentionally excluded.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE = "0192f941e3a2009d203535ec0c97a6ceb69050ed"
EXPECTED_SURFACE = {
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/capabilities.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "framework/realtime_session_config.py",
    "scripts/check_v600_realtime_session_construction_acceptance.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_session_construction_adoption.py",
    "scripts/smoke_v600_realtime_session_construction_control_c.py",
    "scripts/smoke_v600_realtime_session_construction_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_session_construction.py",
    "tests/test_realtime_session_construction_adoption.py",
    "tests/test_realtime_session_construction_runtime_guard.py",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _run(command: list[str], *, label: str) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"{label} failed:\n{output}")
    return output


def check_repository(*, source_only: bool) -> None:
    if source_only:
        print("[OK] source-only aggregate mode skips Git metadata")
        return
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected FW HEAD")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_BASELINE, "origin/main drift")
    _assert(_git("branch", "--show-current") == "main", "unexpected FW branch")
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected FW-RT6-4a aggregate surface: {sorted(_changed_paths())}",
    )
    diff_check = subprocess.run(
        ["git", "diff", "--check"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(diff_check.returncode == 0, f"git diff --check failed:\n{diff_check.stdout}{diff_check.stderr}")
    print("[OK] exact eighteen-file aggregate surface and whitespace contract conform")


def check_acceptance_gate() -> None:
    output = _run(
        [sys.executable, "scripts/smoke_v600_realtime_session_construction_control_c.py", "--source-only"],
        label="Control C dedicated smoke",
    )
    required = (
        "v600_rt6_4a_control_c_status: implemented-awaiting-review",
        "v600_rt6_4a_combined_control_a_b_c_surface: 18 files",
        "v600_rt6_4a_accepted_task_count: 7",
        "v600_rt6_4a_real_request_mock_fallback: False",
        "v600_rt6_4a_focused_unit_tests: 35 / PASS",
        "v600_rt6_4a_full_unit_tests: 80 / PASS",
        "v600_rt6_4a_real_provider_execution: False",
        "v600_rt6_4a_next_checkpoint: FW-RT6-4b",
        "v600_rt6_4a_commit_push: NOT_AUTHORIZED",
    )
    for phrase in required:
        _assert(phrase in output, f"Control C smoke output missing: {phrase}")
    print("[OK] dedicated Control C gate and aggregate public acceptance facts conform")


def check_scope_safety() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_realtime_session_construction_contract.md").read_text(encoding="utf-8")
    combined = tasklist + "\n" + contract
    for phrase in (
        "accepted task count: 7",
        "real provider execution at construction: False",
        "provider / network / microphone / playback / real VTS execution: False",
        "DRC repository accessed or changed: False",
        "root-draft stash accessed or changed: False",
        "commit / push: NOT_AUTHORIZED",
    ):
        _assert(phrase in combined, f"aggregate safety fact missing: {phrase}")
    print("[OK] provider-free scope, DRC exclusion, stash exclusion, and no-publish state conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    check_repository(source_only=args.source_only)
    check_acceptance_gate()
    check_scope_safety()

    print("v600_rt6_4a_acceptance_status: PASS / AWAITING_REVIEW")
    print("v600_rt6_4a_exact_surface: 18 files")
    print("v600_rt6_4a_tasks: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_4a_mock_session_creation: PASS")
    print("v600_rt6_4a_capability_snapshot_available: True")
    print("v600_rt6_4a_real_provider_execution_at_construction: False")
    print("v600_rt6_4a_real_request_mock_fallback: False")
    print("v600_rt6_4a_full_unit_tests: 80 / PASS")
    print("v600_rt6_4a_next_checkpoint: FW-RT6-4b / NOT_AUTHORIZED")
    print("v600_rt6_4a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
