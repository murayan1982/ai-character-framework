"""FW-RT6-10b Control A session close/dispose contract gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "ffb67d8cf089cf0b9e0d0c517614517186201a17"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/session_close.py",
    "scripts/smoke_v600_session_close_control_a.py",
    "tests/test_session_close_control_a.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "SessionCleanupTarget",
    "SessionCleanupOutcome",
    "SessionCloseOutcome",
    "SessionClosePlan",
    "SessionCleanupResult",
    "SessionCloseResult",
    "build_session_close_plan",
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
        "unexpected FW-RT6-10b Control A baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the Control A baseline",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(actual)}",
    )
    print("[OK] baseline and exact five-file FW-RT6-10b Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_close' not in sys.modules; "
        "assert not hasattr(framework, 'SessionClosePlan'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import stays lazy and session-close names remain explicit-only")


def _results_for_plan(control, plan):
    required = set(plan.required_targets)
    return tuple(
        (
            control.SessionCleanupResult.completed(target)
            if target in required
            else control.SessionCleanupResult.not_required(target)
        )
        for target in control.SessionCleanupTarget
    )


def check_model_contract() -> None:
    _run("-m", "unittest", "tests.test_session_close_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.session_close as control

    _require(
        tuple(control.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "session-close explicit-package exports changed",
    )
    plan = control.build_session_close_plan(
        active_turn_terminal_required=True,
        stage_cleanup_required=True,
        provider_client_cleanup_required=True,
        callback_hub_close_required=True,
        execution_bridge_shutdown_required=True,
    )
    _require(
        tuple(target.value for target in plan.required_targets)
        == (
            "active_turn",
            "stage",
            "provider_client",
            "callback_hub",
            "execution_bridge",
        ),
        "close target order drifted",
    )
    _require(not plan.decision_is_execution, "close plan was relabeled execution")
    _require(plan.side_effect_free, "Control A close plan claimed a side effect")

    closed = control.SessionCloseResult.from_cleanup(
        plan,
        cleanup_results=_results_for_plan(control, plan),
        active_turn_terminalized=True,
    )
    _require(
        closed.outcome is control.SessionCloseOutcome.CLOSED,
        "successful close outcome drifted",
    )
    _require(closed.session_closed, "successful close result left session open")
    _require(
        closed.diagnostics["active_turn_terminalized_count"] == 1,
        "active-turn terminal diagnostic drifted",
    )

    timeout_plan = control.build_session_close_plan(
        stage_cleanup_required=True,
        execution_bridge_shutdown_required=True,
    )
    timeout_results = list(_results_for_plan(control, timeout_plan))
    timeout_results[list(control.SessionCleanupTarget).index(
        control.SessionCleanupTarget.STAGE
    )] = control.SessionCleanupResult.timed_out_result(
        control.SessionCleanupTarget.STAGE
    )
    timed_out = control.SessionCloseResult.from_cleanup(
        timeout_plan,
        cleanup_results=timeout_results,
        active_turn_terminalized=False,
    )
    _require(
        timed_out.outcome
        is control.SessionCloseOutcome.CLOSED_WITH_CLEANUP_FAILURES,
        "cleanup timeout was mislabeled successful",
    )
    _require(timed_out.session_closed, "cleanup timeout reopened the session")
    _require(
        timed_out.diagnostics["cleanup_timeout_count"] == 1,
        "cleanup timeout diagnostic drifted",
    )

    duplicate = control.SessionCloseResult.already_closed()
    _require(
        duplicate.outcome is control.SessionCloseOutcome.ALREADY_CLOSED,
        "duplicate close outcome drifted",
    )
    _require(
        duplicate.diagnostics["cleanup_attempted_count"] == 0,
        "duplicate close repeated cleanup",
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
    for relative in (
        "framework/realtime_session.py",
        "framework/facade.py",
        "framework/voice_input_session.py",
        "framework/audio/voice_output.py",
        "framework/motion_session.py",
        "framework/realtime_execution_bridge.py",
        "framework/realtime_event_hub.py",
        "framework/realtime_stage.py",
    ):
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "from .session_close import" not in source
            and "import framework.session_close" not in source,
            f"Control B runtime adoption escaped into Control A: {relative}",
        )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")

    print("[OK] active-turn, cleanup-target, timeout, and duplicate-close models conform")
    print("[OK] cleanup failure stays truthful while the session remains closed")
    print("[OK] existing lifecycle owners and root-public/version contracts remain unchanged")


def check_docs_and_task_boundary() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            text.count("FW-RT6-10b-A-SESSION-CLOSE:BEGIN") == 1,
            f"missing or duplicate Control A begin marker: {relative}",
        )
        _require(
            text.count("FW-RT6-10b-A-SESSION-CLOSE:END") == 1,
            f"missing or duplicate Control A end marker: {relative}",
        )
        for phrase in (
            "stable explicit package: framework.session_close",
            "close execution owner: PUBLIC SESSION / REUSED",
            "active turn terminal outcome: TurnOutcome.CLOSED / REQUIRED",
            "cleanup targets and outcomes: TYPED / PASS",
            "stage cleanup timeout: REQUIRED / NOT EXECUTED IN CONTROL A",
            "callback hub close: AFTER FINAL SESSION_CLOSED DELIVERY",
            "bridge stopped confirmation: REQUIRED / NOT EXECUTED IN CONTROL A",
            "cleanup failure reopens session: False",
            "repeated close: already_closed / NO RE-CLEANUP",
            "runtime adoption: DEFERRED TO CONTROL B",
            "FW-RT6-10b aggregate tasks: 0 / 7 CLOSED",
            "Control B implementation: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-10b", 1)[1].split("## FW-RT6-10c", 1)[0]
    _require(section.count("- [ ]") == 7, "Control A closed an aggregate task")
    _require(section.count("- [x]") == 0, "Control A changed aggregate closure")
    print("[OK] runtime adoption and later-control boundaries are documented")
    print("[OK] FW-RT6-10b aggregate tasks remain 0 / 7 closed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_model_contract()
    check_docs_and_task_boundary()
    print("v600_rt6_10b_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10b_control_a_exact_surface: 5 files")
    print("v600_rt6_10b_explicit_package: framework.session_close / PASS")
    print("v600_rt6_10b_close_owner: PUBLIC SESSION / REUSED")
    print("v600_rt6_10b_active_turn_terminal: CLOSED / TYPED")
    print("v600_rt6_10b_cleanup_targets: 5 / TYPED")
    print("v600_rt6_10b_cleanup_timeout: TYPED / NOT_EXECUTED")
    print("v600_rt6_10b_duplicate_close: already_closed / NO_RE_CLEANUP")
    print("v600_rt6_10b_cleanup_failure_reopens_session: False / PASS")
    print("v600_rt6_10b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_10b_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_10b_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_10b_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_10b_task_count: 0 / 7 CLOSED")
    print("v600_rt6_10b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_10b_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10b Control A session close/dispose contract gate passed")


if __name__ == "__main__":
    main()
