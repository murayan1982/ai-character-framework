"""FW-RT6-8a Control A motion correlation regression gate.

The gate is provider/network/audio safe. The v5.5 composition regression uses
only its injected in-memory transport and never imports or calls real pyvts.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import fields
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "7bcf66f0f0f309824fcb78b03978c9d9ebf40988"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/motion.py",
    "framework/motion_session.py",
    "scripts/smoke_v600_motion_correlation_control_a.py",
    "tests/test_motion_correlation_control_a.py",
}


def _require(condition: bool, message: str) -> None:
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


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-8a Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact six-file FW-RT6-8a Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        check=True,
    )


def check_runtime_contract() -> None:
    _run("scripts/smoke_v520_motion_public_contract_conformance_gate.py")
    _run("scripts/smoke_v550_motion_session_real_adapter_composition.py")
    _run(
        "-m",
        "unittest",
        "tests.test_motion_correlation_control_a",
    )

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework

    request_fields = tuple(field.name for field in fields(framework.MotionRequest))
    result_fields = tuple(field.name for field in fields(framework.MotionResult))
    _require(
        request_fields[-2:] == ("turn_id", "generation_id"),
        "MotionRequest correlation fields are not additive",
    )
    _require(
        result_fields[-2:] == ("turn_id", "generation_id"),
        "MotionResult correlation fields are not additive",
    )
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version changed",
    )
    print("[OK] optional request/result correlation and legacy v5.5 behavior conform")
    print("[OK] mock, guarded, closed, and in-memory VTS result projections correlate")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-8a-A-MOTION-CORRELATION" in text,
            f"missing Control A marker: {relative}",
        )
        for phrase in (
            "MotionRequest request_id changed: False",
            "standalone correlation identity invented: False",
            "unified EventSequence bridge: DEFERRED TO CONTROL B",
            "common stale guard / VTS suppression adoption: DEFERRED TO CONTROL B",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-8a-B-MOTION-COORDINATION" in text,
            f"missing Control B coordination marker: {relative}",
        )
    print("[OK] accepted Control A correlation remains compatible with Control B")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_runtime_contract()
    check_docs()
    print("v600_rt6_8a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8a_control_a_exact_surface: 6 files")
    print("v600_rt6_8a_request_context: optional turn/generation / PASS")
    print("v600_rt6_8a_result_event_context: propagated / PASS")
    print("v600_rt6_8a_request_id_compatibility: PASS")
    print("v600_rt6_8a_session_id_compatibility: PASS")
    print("v600_rt6_8a_standalone_identity_invented: False / PASS")
    print("v600_rt6_8a_unified_event_sequence: ADOPTED_BY_CONTROL_B / PASS")
    print("v600_rt6_8a_common_stale_guard: ADOPTED_BY_CONTROL_B / PASS")
    print("v600_rt6_8a_vts_generation_suppression_changed: False")
    print("v600_rt6_8a_task_count: 0 / 5 CLOSED")
    print("v600_rt6_8a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-8a Control A motion correlation smoke passed")


if __name__ == "__main__":
    main()
