"""FW-RT6-10a Control A recovery/reset planning contract gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "48b6554d79c78af95f825639e2a68e7a2f7493b3"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/recovery_control.py",
    "scripts/smoke_v600_recovery_control_a.py",
    "tests/test_recovery_control_a.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "RecoveryResetScope",
    "RecoveryControlDisposition",
    "RecoveryResetOutcome",
    "RecoveryResetErrorCode",
    "RecoveryControlPlan",
    "RecoveryResetResult",
    "build_recovery_control_plan",
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
        "unexpected FW-RT6-10a Control A baseline",
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
    print("[OK] baseline and exact five-file FW-RT6-10a Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.recovery_control' not in sys.modules; "
        "assert not hasattr(framework, 'RecoveryControlPlan'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import remains lazy and recovery-control names stay explicit-only")


def check_model_contract() -> None:
    _run("-m", "unittest", "tests.test_recovery_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.recovery_control as control
    from framework.identity import GenerationId
    from framework.lifecycle import RecoveryAction

    _require(
        tuple(control.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "recovery-control explicit-package exports changed",
    )

    turn = control.build_recovery_control_plan(RecoveryAction.RESET_TURN)
    session = control.build_recovery_control_plan(RecoveryAction.RESET_SESSION)
    reconnect = control.build_recovery_control_plan(RecoveryAction.RECONNECT)
    close = control.build_recovery_control_plan(RecoveryAction.CLOSE_SESSION)
    permanent = control.build_recovery_control_plan(
        RecoveryAction.PERMANENT_FAILURE
    )
    _require(turn.reset_scope.value == "turn_only", "turn reset scope drift")
    _require(session.reset_scope.value == "session", "session reset scope drift")
    _require(turn.generation_advance_required, "turn reset generation drift")
    _require(session.generation_advance_required, "session reset generation drift")
    _require(reconnect.reconnect_required, "reconnect requirement lost")
    _require(close.close_required, "close requirement lost")
    _require(
        permanent.close_required and permanent.permanently_failed,
        "permanent-failure facts drifted",
    )
    _require(not turn.decision_is_execution, "plan was relabeled execution")
    _require(turn.side_effect_free, "Control A plan claimed a side effect")

    applied = control.RecoveryResetResult.applied(
        turn,
        previous_generation_id=GenerationId.new(),
        current_generation_id=GenerationId.new(),
    )
    _require(applied.generation_advanced, "applied reset lost generation fact")
    failed = control.RecoveryResetResult.failed(
        session,
        error_code=control.RecoveryResetErrorCode.PROVIDER_RESET_FAILED,
    )
    _require(
        failed.outcome is control.RecoveryResetOutcome.FAILED,
        "typed reset failure drift",
    )
    _require(not failed.generation_advanced, "failed reset claimed generation")

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
        "recovery_control" not in runtime_source,
        "runtime plan adoption occurred before Control B",
    )
    _require(
        "def reset(" not in runtime_source,
        "RealtimeSession reset execution occurred before Control B",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] explicit reset scopes and recovery dispositions conform")
    print("[OK] typed reset result and generation-advance contract conform")
    print("[OK] root-public/version/runtime compatibility remains unchanged")


def check_docs_and_task_boundary() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            text.count("FW-RT6-10a-A-RECOVERY-CONTROL:BEGIN") == 1,
            f"missing or duplicate Control A begin marker: {relative}",
        )
        _require(
            text.count("FW-RT6-10a-A-RECOVERY-CONTROL:END") == 1,
            f"missing or duplicate Control A end marker: {relative}",
        )
        for phrase in (
            "stable explicit package: framework.recovery_control",
            "turn-only reset scope: turn_only / PASS",
            "session reset scope: session / PASS",
            "reset planning requires generation advance: True / PASS",
            "provider context loss: DOCUMENTED / PASS",
            "reset failure result: RecoveryResetResult / TYPED / PASS",
            "decision != execution: True / PASS",
            "runtime adoption: DEFERRED TO CONTROL B",
            "FW-RT6-10a aggregate tasks: 0 / 7 CLOSED",
            "Control B implementation: NOT_AUTHORIZED",
            "FW-RT6-10b implementation: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-10a", 1)[1].split("## FW-RT6-10b", 1)[0]
    _require(section.count("- [ ]") == 7, "Control A closed an aggregate task")
    _require(section.count("- [x]") == 0, "Control A changed aggregate closure")
    print("[OK] provider-context loss and later-scope boundaries are documented")
    print("[OK] FW-RT6-10a aggregate tasks remain 0 / 7 closed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_model_contract()
    check_docs_and_task_boundary()
    print("v600_rt6_10a_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10a_control_a_exact_surface: 5 files")
    print("v600_rt6_10a_explicit_package: framework.recovery_control / PASS")
    print("v600_rt6_10a_turn_reset_scope: turn_only / PASS")
    print("v600_rt6_10a_session_reset_scope: session / PASS")
    print("v600_rt6_10a_generation_advance_required: True / PASS")
    print("v600_rt6_10a_provider_context_loss: DOCUMENTED / PASS")
    print("v600_rt6_10a_reconnect_close_permanent: TYPED / PASS")
    print("v600_rt6_10a_reset_failure: TYPED / PASS")
    print("v600_rt6_10a_decision_is_execution: False / PASS")
    print("v600_rt6_10a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_10a_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_10a_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_10a_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_10a_task_count: 0 / 7 CLOSED")
    print("v600_rt6_10a_control_b: NOT_AUTHORIZED")
    print("v600_rt6_10b: NOT_AUTHORIZED")
    print("v600_rt6_10a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10a Control A recovery/reset contract gate passed")


if __name__ == "__main__":
    main()
