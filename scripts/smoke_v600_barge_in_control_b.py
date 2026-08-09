"""FW-RT6-9c Control B ordered barge-in execution gate."""

from __future__ import annotations

import argparse
from dataclasses import fields
import inspect
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "4f1fdc0de949f236703c0e6d23a8d43abf8636e5"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/output_control.py",
    "framework/realtime_session.py",
    "scripts/smoke_v600_barge_in_control_b.py",
    "tests/test_barge_in_control_a.py",
    "tests/test_barge_in_control_b.py",
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
        "unexpected FW-RT6-9c Control B baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-9c Control B surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.barge_in_control' not in sys.modules; "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import remains lazy and barge-in plan names stay explicit-only")


def check_runtime_contract() -> None:
    _run("-m", "unittest", "tests.test_barge_in_control_b")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.barge_in_control import build_barge_in_control_plan
    from framework.output_control import (
        BargeInDecision,
        BargeInPolicy,
        InterruptReason,
        InterruptResult,
    )

    _require(BargeInPolicy().flush_output is False, "default flush fact is not boolean false")
    _require(
        BargeInPolicy.soft_interrupt().flush_output is False,
        "soft interrupt unexpectedly requests queue flush",
    )
    _require(
        BargeInPolicy.flush_output().flush_output is True,
        "flush policy factory compatibility changed",
    )
    _require(
        fields(BargeInPolicy)[2].default is False,
        "flush field default remains shadowed by the factory",
    )

    parameters = tuple(
        inspect.signature(framework.RealtimeSession.execute_barge_in).parameters
    )
    _require(parameters == ("self", "plan"), "execute_barge_in signature changed")

    class _CaptureSession(framework.RealtimeSession):
        def __init__(self) -> None:
            super().__init__()
            self.request = None
            self.advance_reason = None

        def _ordered_interrupt(self, request, *, advance_reason):
            self.request = request
            self.advance_reason = advance_reason
            return InterruptResult.no_active_turn(request=request)

    session = _CaptureSession()
    plan = build_barge_in_control_plan(
        BargeInDecision.accepted_for_policy(
            BargeInPolicy.soft_interrupt(),
            turn_id="turn-control-b-gate",
        ),
        capabilities=session.capabilities,
    )
    result = session.execute_barge_in(plan)
    _require(
        session.request is plan.coordinator_request,
        "session reinterpreted the exact coordinator request",
    )
    _require(session.advance_reason == "interrupt", "generation advance reason drift")
    _require(result.reason is InterruptReason.USER_BARGE_IN, "barge-in reason drift")

    nonexecuting = build_barge_in_control_plan(
        BargeInDecision.accepted_for_policy(BargeInPolicy.flush_output()),
        capabilities=session.capabilities,
    )
    before = tuple(session.event_history)
    unsupported = session.execute_barge_in(nonexecuting)
    _require(not nonexecuting.execute_interrupt, "unsupported flush became executable")
    _require(unsupported.outcome.value == "unsupported", "missing typed unsupported result")
    _require(tuple(session.event_history) == before, "non-executing plan emitted an event")

    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API version changed",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version changed",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] exact plan request delegates to the accepted ordered interrupt owner")
    print("[OK] non-executing plan, downgrade, duplicate, and event ordering conform")
    print("[OK] flush field/factory compatibility and public versions remain stable")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-9c-B-BARGE-IN-EXECUTION" in text,
            f"missing Control B marker: {relative}",
        )
        for phrase in (
            "exact Control B surface: 7 files",
            "decision != execution: True",
            "microphone detection in core: False",
            "Control B status: IMPLEMENTED / AWAITING_REVIEW",
            "FW-RT6-9c aggregate tasks: 0 / 5 CLOSED",
        ):
            _require(phrase in text, f"missing Control B phrase in {relative}: {phrase}")
    print("[OK] execution delegation and later-scope boundaries are documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_runtime_contract()
    check_docs()
    print("v600_rt6_9c_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9c_control_b_exact_surface: 7 files")
    print("v600_rt6_9c_execute_barge_in: ADOPTED / PASS")
    print("v600_rt6_9c_exact_coordinator_request_delegation: PASS")
    print("v600_rt6_9c_second_interrupt_owner: False / PASS")
    print("v600_rt6_9c_decision_is_execution: False / PASS")
    print("v600_rt6_9c_nonexecuting_plan_effects: False / PASS")
    print("v600_rt6_9c_unsupported_hard_cancel: soft_interrupt / PASS")
    print("v600_rt6_9c_microphone_detection_required: False / PASS")
    print("v600_rt6_9c_duplicate_owner_result_replay: PASS")
    print("v600_rt6_9c_barge_in_event_ordering: PASS")
    print("v600_rt6_9c_policy_flush_collision: FIXED / COMPATIBLE")
    print("v600_rt6_9c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9c_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9c_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9c_task_count: 0 / 5 CLOSED")
    print("v600_rt6_9c_control_c: NOT_AUTHORIZED")
    print("v600_rt6_9d: NOT_AUTHORIZED")
    print("v600_rt6_9c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9c Control B barge-in runtime adoption gate passed")


if __name__ == "__main__":
    main()
