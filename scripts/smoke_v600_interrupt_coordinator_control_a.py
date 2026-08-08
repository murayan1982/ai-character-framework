"""FW-RT6-9a Control A interrupt-coordination contract gate."""

from __future__ import annotations

import argparse
from dataclasses import fields
from inspect import signature
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "c72caa0f2c4eb2f5cd764f8cb85ac27aee5d4ba5"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/interrupt_coordination.py",
    "framework/output_control.py",
    "scripts/smoke_v600_interrupt_coordinator_control_a.py",
    "tests/test_interrupt_coordinator_control_a.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "InterruptAggregateOutcome",
    "InterruptAggregateResult",
    "InterruptSubsystem",
    "InterruptSubsystemOutcome",
    "InterruptSubsystemResult",
)


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
        ("-c", "core.safecrlf=false", "diff", "HEAD", "--name-only"),
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
        "unexpected FW-RT6-9a Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact six-file FW-RT6-9a Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.interrupt_coordination' not in sys.modules; "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import remains lazy and coordinator names stay explicit-only")


def check_model_contract() -> None:
    _run("-m", "unittest", "tests.test_interrupt_coordinator_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.interrupt_coordination as coordination
    from framework.output_control import InterruptRequest, InterruptResult

    _require(
        tuple(coordination.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "interrupt coordination explicit-package exports changed",
    )
    _require(
        tuple(item.name for item in fields(InterruptRequest))[-1:] == (
            "timeout_seconds",
        ),
        "InterruptRequest additive timeout changed",
    )
    _require(
        tuple(item.name for item in fields(InterruptResult))[-1:] == (
            "motion_result",
        ),
        "accepted InterruptResult dataclass fields changed",
    )
    _require(
        tuple(signature(InterruptResult).parameters)[-1:] == (
            "coordination_result",
        ),
        "InterruptResult additive coordination projection changed",
    )
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API version changed",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version changed",
    )
    _require(
        not hasattr(framework.RealtimeSession, "interrupt_coordinator"),
        "runtime coordinator adopted early",
    )
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] subsystem reach, truthful aggregation, and timeout models conform")
    print("[OK] root-public/version/runtime compatibility remains unchanged")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-9a-A-INTERRUPT-COORDINATION" in text,
            f"missing Control A marker: {relative}",
        )
        for phrase in (
            "cooperative cancel != provider hard cancel",
            "aggregate outcome derived from subsystem results: True",
            "unsupported overclaim: False",
            "runtime adoption: DEFERRED TO CONTROL B",
            "FW-RT6-9a aggregate tasks: 0 / 9 CLOSED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")
    print("[OK] aggregation truthfulness and Phase 9b/9c deferrals are documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_model_contract()
    check_docs()
    print("v600_rt6_9a_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9a_control_a_exact_surface: 6 files")
    print("v600_rt6_9a_explicit_package: framework.interrupt_coordination / PASS")
    print("v600_rt6_9a_subsystem_count: 5 / PASS")
    print("v600_rt6_9a_subsystem_outcome_count: 8 / PASS")
    print("v600_rt6_9a_aggregate_outcome_count: 9 / PASS")
    print("v600_rt6_9a_partial_result: PASS")
    print("v600_rt6_9a_unsupported_overclaim: False / PASS")
    print("v600_rt6_9a_interrupt_request_timeout_additive: True / PASS")
    print("v600_rt6_9a_interrupt_result_coordination_additive: True / PASS")
    print("v600_rt6_9a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9a_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9a_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9a_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_9a_duplicate_race_ordering: DEFERRED_TO_FW_RT6_9B")
    print("v600_rt6_9a_barge_in_execution: DEFERRED_TO_FW_RT6_9C")
    print("v600_rt6_9a_task_count: 0 / 9 CLOSED")
    print("v600_rt6_9a_control_b: NOT_AUTHORIZED")
    print("v600_rt6_9a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9a Control A interrupt-coordination gate passed")


if __name__ == "__main__":
    main()
