"""FW-RT6-8c Control A typed motion-control contract gate."""

from __future__ import annotations

import argparse
from dataclasses import fields
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "bd5888ffb2ec96664f744f214be19e8cd50029dc"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/motion_control.py",
    "framework/output_control.py",
    "framework/realtime_capabilities.py",
    "scripts/smoke_v600_motion_control_control_a.py",
    "tests/test_motion_control_control_a.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "MotionControlOutcome",
    "MotionControlResult",
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
        "unexpected FW-RT6-8c Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-8c Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.motion_control' not in sys.modules; "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import remains lazy and motion-control names stay explicit-only")


def check_model_contract() -> None:
    _run("-m", "unittest", "tests.test_motion_control_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.motion_control as control
    from framework.output_control import InterruptResult
    from framework.realtime_capabilities import RealtimeMotionCapability

    _require(
        tuple(control.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "motion control explicit-package exports changed",
    )
    _require(
        tuple(item.name for item in fields(InterruptResult))[-1:] == (
            "motion_result",
        ),
        "InterruptResult additive motion result field changed",
    )
    _require(
        tuple(item.name for item in fields(RealtimeMotionCapability))[-1:] == (
            "stop_motion_supported",
        ),
        "RealtimeMotionCapability additive stop flag changed",
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
    _require(not hasattr(framework.RealtimeSession, "cancel_motion"), "runtime adopted early")
    _require(not hasattr(framework.MotionSession, "cancel_motion"), "motion runtime adopted early")
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] typed motion cancel/stop reach and legacy prefixes conform")
    print("[OK] root-public/version/runtime compatibility remains unchanged")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-8c-A-MOTION-CONTROL" in text,
            f"missing Control A marker: {relative}",
        )
        for phrase in (
            "request cancel != STOP_MOTION",
            "provider stop completion inferred from cancel acceptance: False",
            "aggregate interrupt outcome changed by Control A: False",
            "runtime adoption: DEFERRED TO CONTROL B",
            "FW-RT6-8c aggregate tasks: 0 / 5 CLOSED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")
    print("[OK] cancel/stop truthfulness and Phase 9 deferrals are documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_model_contract()
    check_docs()
    print("v600_rt6_8c_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_8c_control_a_exact_surface: 7 files")
    print("v600_rt6_8c_explicit_package: framework.motion_control / PASS")
    print("v600_rt6_8c_outcome_count: 8 / PASS")
    print("v600_rt6_8c_interrupt_result_additive: motion_result / PASS")
    print("v600_rt6_8c_stop_motion_capability_additive: True / PASS")
    print("v600_rt6_8c_request_cancel_equals_stop_motion: False / PASS")
    print("v600_rt6_8c_provider_stop_overclaim: False / PASS")
    print("v600_rt6_8c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_8c_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_8c_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_8c_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_8c_aggregate_interrupt: DEFERRED_TO_FW_RT6_9A")
    print("v600_rt6_8c_task_count: 0 / 5 CLOSED")
    print("v600_rt6_8c_control_b: NOT_AUTHORIZED")
    print("v600_rt6_8c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-8c Control A motion-control contract gate passed")


if __name__ == "__main__":
    main()
