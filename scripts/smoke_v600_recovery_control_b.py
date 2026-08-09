"""FW-RT6-10a Control B session-owned reset execution gate."""

from __future__ import annotations

import argparse
from inspect import signature
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "2fe31e3c6a18f62696cd12f4f153c026d6f113a6"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime_generation_gate.py",
    "framework/realtime_session.py",
    "scripts/check_v600_end_to_end_stale_acceptance.py",
    "scripts/smoke_v600_recovery_control_a.py",
    "scripts/smoke_v600_recovery_control_b.py",
    "tests/test_end_to_end_stale_control_b.py",
    "tests/test_recovery_control_a.py",
    "tests/test_recovery_control_b.py",
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
        "unexpected FW-RT6-10a Control B baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the Control B baseline",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(actual)}",
    )
    print("[OK] baseline and exact ten-file FW-RT6-10a Control B surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_and_source_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.recovery_control' not in sys.modules; "
        "assert hasattr(framework.RealtimeSession, 'reset'); "
        "assert not hasattr(framework, 'RecoveryControlPlan'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)

    runtime_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    gate_source = (
        PROJECT_ROOT / "framework/realtime_generation_gate.py"
    ).read_text(encoding="utf-8")
    _require("def reset(" in runtime_source, "RealtimeSession.reset is missing")
    _require(
        "self._generation_gate.reset_generation()" in runtime_source,
        "reset does not delegate to the existing generation owner",
    )
    _require(
        "def reset_generation(" in gate_source,
        "generation reset boundary is missing",
    )
    _require(
        runtime_source.count("RealtimeGenerationGate()") == 1,
        "a second session generation owner was introduced",
    )
    print("[OK] root import stays lazy and the sole generation owner is reused")


def check_runtime_contract() -> None:
    _run(
        "-m",
        "unittest",
        "tests.test_recovery_control_a",
        "tests.test_recovery_control_b",
    )

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.lifecycle import RecoveryAction
    from framework.realtime import RealtimeEventType, RealtimeTurn
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
    )
    from framework.recovery_control import (
        RecoveryResetErrorCode,
        RecoveryResetOutcome,
        build_recovery_control_plan,
    )

    session = framework.create_realtime_session()
    turn = RealtimeTurn(session_id=session.info.session_id, input_text="reset")
    started = session.start_turn(turn)
    previous = started.generation_id
    _require(previous is not None, "admitted turn lost its generation")
    gate = session._generation_gate
    event_count = len(session.event_history)
    plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)
    result = session.reset(plan)
    _require(result.plan is plan, "reset rebuilt the accepted plan")
    _require(
        result.outcome is RecoveryResetOutcome.APPLIED,
        "active turn reset was not applied",
    )
    _require(result.previous_generation_id == previous, "old generation drift")
    _require(
        result.current_generation_id != previous,
        "replacement generation is not distinct",
    )
    _require(session._generation_gate is gate, "freshness owner was replaced")
    _require(len(session.event_history) == event_count, "reset emitted a new event")

    delivered: list[str] = []
    stale = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn.turn_id,
            generation_id=previous,
            stage="recovery_control_b_old",
            value="old",
        ),
        deliver=delivered.append,
    )
    _require(not stale.accepted, "old completion survived reset")
    _require(
        stale.retired_by is GenerationAdvanceReason.RESET,
        "old generation lost reset retirement reason",
    )
    _require(not delivered, "stale reset completion reached delivery")

    terminal_session = framework.create_realtime_session()
    terminal = terminal_session.run_turn(input_text="terminal")
    terminal_reset = terminal_session.reset(
        build_recovery_control_plan(RecoveryAction.RESET_SESSION)
    )
    _require(
        terminal_reset.previous_generation_id == terminal.generation_id,
        "terminal reset lost its previous generation",
    )
    next_turn = terminal_session.start_turn(input_text="next")
    _require(
        next_turn.generation_id == terminal_reset.current_generation_id,
        "next turn did not consume the exact reset replacement",
    )

    empty = framework.create_realtime_session()
    failed = empty.reset(build_recovery_control_plan(RecoveryAction.RESET_TURN))
    _require(
        failed.error_code is RecoveryResetErrorCode.GENERATION_MISMATCH,
        "missing-generation failure is not typed",
    )
    _require(not failed.generation_advanced, "failed reset claimed advancement")

    reuse = empty.reset(build_recovery_control_plan(RecoveryAction.REUSE_SESSION))
    _require(
        reuse.outcome is RecoveryResetOutcome.NOT_REQUIRED,
        "reuse_session was reinterpreted as reset",
    )
    _require(not reuse.generation_advanced, "reuse_session changed generation")

    _require("RESET" not in RealtimeEventType.__members__, "event vocabulary changed")
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
        "reset" not in signature(framework.create_realtime_session).parameters,
        "realtime factory signature changed",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] typed reset, exact replacement, and stale suppression conform")
    print("[OK] terminal reset handoff and non-reset dispositions conform")
    print("[OK] public versions, events, factory, and provider isolation conform")


def check_docs_and_task_boundary() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            text.count("FW-RT6-10a-B-RECOVERY-EXECUTION:BEGIN") == 1,
            f"missing or duplicate Control B begin marker: {relative}",
        )
        _require(
            text.count("FW-RT6-10a-B-RECOVERY-EXECUTION:END") == 1,
            f"missing or duplicate Control B end marker: {relative}",
        )
        for phrase in (
            "focused Control B recovery/reset tests: 14 / PASS",
            "focused Control A+B recovery/reset tests: 27 / PASS",
            "accepted FW-RT6-9d aggregate regression: 27 / PASS",
            "full Framework unit suite: 520 / PASS",
            "explicit execution boundary: RealtimeSession.reset(plan) / ADOPTED",
            "existing freshness owner reused: RealtimeGenerationGate / PASS",
            "second recovery/freshness owner introduced: False / PASS",
            "terminal reset replacement consumed by next turn: EXACT / PASS",
            "old completion after reset delivered: False / PASS",
            "completion/reset race linearization: PASS",
            "provider reset execution: False / PASS",
            "FW-RT6-10a aggregate tasks: 0 / 7 CLOSED",
            "Control B acceptance sync: NOT_AUTHORIZED",
            "Control C aggregate acceptance: NOT_AUTHORIZED",
            "FW-RT6-10b implementation: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing Control B phrase in {relative}: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-10a", 1)[1].split("## FW-RT6-10b", 1)[0]
    _require(section.count("- [ ]") == 7, "Control B closed an aggregate task")
    _require(section.count("- [x]") == 0, "Control B changed aggregate closure")
    _require(
        "Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED"
        in tasklist,
        "accepted Control A sync is missing",
    )
    print("[OK] reset scope, loss, race, and later-scope boundaries are documented")
    print("[OK] FW-RT6-10a aggregate tasks remain 0 / 7 closed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_and_source_contract()
    check_runtime_contract()
    check_docs_and_task_boundary()
    print("v600_rt6_10a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10a_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10a_control_b_exact_surface: 10 files")
    print("v600_rt6_10a_reset_execution: RealtimeSession.reset(plan) / PASS")
    print("v600_rt6_10a_generation_owner: RealtimeGenerationGate / REUSED")
    print("v600_rt6_10a_replacement_generation_count: 1 / PASS")
    print("v600_rt6_10a_old_completion_after_reset: False / PASS")
    print("v600_rt6_10a_terminal_replacement_handoff: EXACT / PASS")
    print("v600_rt6_10a_completion_reset_race: LINEARIZED / PASS")
    print("v600_rt6_10a_non_reset_side_effects: False / PASS")
    print("v600_rt6_10a_reset_failure: TYPED / PASS")
    print("v600_rt6_10a_provider_execution: False / PASS")
    print("v600_rt6_10a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_10a_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_10a_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_10a_task_count: 0 / 7 CLOSED")
    print("v600_rt6_10a_control_b_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_10a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10b: NOT_AUTHORIZED")
    print("v600_rt6_10a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10a Control B recovery/reset execution gate passed")


if __name__ == "__main__":
    main()
