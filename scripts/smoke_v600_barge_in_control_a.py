"""FW-RT6-9c Control A decision-to-control-plan contract gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "42dcf194909504a1a09ea6612d81db1b56a008f9"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/barge_in_control.py",
    "scripts/smoke_v600_barge_in_control_a.py",
    "tests/test_barge_in_control_a.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "BargeInControlPlan",
    "build_barge_in_control_plan",
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
        "unexpected FW-RT6-9c Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-9c Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.barge_in_control' not in sys.modules; "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import remains lazy and barge-in names stay explicit-only")


def check_model_contract() -> None:
    _run("-m", "unittest", "tests.test_barge_in_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.barge_in_control as control
    from framework.identity import SessionId
    from framework.output_control import BargeInDecision, BargeInPolicy
    from framework.realtime_capabilities import RealtimeCapabilitySnapshot

    _require(
        tuple(control.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "barge-in control explicit-package exports changed",
    )
    decision = BargeInDecision.accepted_for_policy(BargeInPolicy.hard_cancel())
    plan = control.build_barge_in_control_plan(
        decision,
        capabilities=RealtimeCapabilitySnapshot(session_id=SessionId.new()),
    )
    _require(plan.requested_mode.value == "hard_cancel", "requested mode drift")
    _require(plan.effective_mode.value == "soft_interrupt", "downgrade drift")
    _require(plan.capability_downgraded, "missing truthful downgrade")
    _require(not plan.provider_hard_cancel_planned, "hard cancel was overclaimed")
    _require(not plan.microphone_detection_required, "core claimed microphone")
    _require(not plan.decision_is_execution, "decision was relabeled execution")
    _require(plan.side_effect_free, "Control A model claimed a side effect")
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API version changed",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version changed",
    )
    runtime_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    _require(
        "barge_in_control" not in runtime_source,
        "runtime plan adoption occurred before Control B",
    )
    _require(
        "def execute_barge_in(" not in runtime_source,
        "barge-in execution occurred before Control B",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] pure planning and truthful capability downgrade conform")
    print("[OK] root-public/version/runtime compatibility remains unchanged")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-9c-A-BARGE-IN-CONTROL" in text,
            f"missing Control A marker: {relative}",
        )
        for phrase in (
            "stable explicit package: framework.barge_in_control",
            "barge-in policy triggers microphone: False",
            "decision != execution: True",
            "unsupported hard cancel effective mode: soft_interrupt",
            "runtime adoption: DEFERRED TO CONTROL B",
            "FW-RT6-9c aggregate tasks: 0 / 5 CLOSED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")
    print("[OK] decision, plan, downgrade, and later-scope boundaries are documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_model_contract()
    check_docs()
    print("v600_rt6_9c_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9c_control_a_exact_surface: 5 files")
    print("v600_rt6_9c_explicit_package: framework.barge_in_control / PASS")
    print("v600_rt6_9c_decision_is_execution: False / PASS")
    print("v600_rt6_9c_control_plan_side_effect_free: True / PASS")
    print("v600_rt6_9c_microphone_detection_required: False / PASS")
    print("v600_rt6_9c_unsupported_hard_cancel: soft_interrupt / PASS")
    print("v600_rt6_9c_unsupported_flush_execution: False / PASS")
    print("v600_rt6_9c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9c_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9c_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9c_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_9c_task_count: 0 / 5 CLOSED")
    print("v600_rt6_9c_control_b: NOT_AUTHORIZED")
    print("v600_rt6_9d: NOT_AUTHORIZED")
    print("v600_rt6_9c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9c Control A barge-in control contract gate passed")


if __name__ == "__main__":
    main()
