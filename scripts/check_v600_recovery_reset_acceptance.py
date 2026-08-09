"""FW-RT6-10a Control C aggregate recovery/reset acceptance gate.

The gate uses only deterministic in-memory sessions and completion envelopes.
It imports no provider SDK and performs no provider, network, audio,
microphone, playback, or real VTube Studio operation.
"""

from __future__ import annotations

import argparse
import inspect
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "bcfb77922d219da56697430e42e21e95c3b6cd62"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_recovery_reset_acceptance.py",
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
EXPECTED_FACTORY_PARAMETERS = (
    "project_root",
    "public_metadata",
    "real_runtime_enabled",
    "voice_input_stage",
    "text_generation_stage",
    "voice_output_stage",
    "motion_stage",
    "config",
)
EXPECTED_DIAGNOSTIC_KEYS = {
    "generation_start_count",
    "generation_advance_count",
    "accepted_completion_count",
    "stale_completion_count",
    "active_generation_count",
    "registry_size",
}
TURN_CONTEXT_LOSS = (
    "active_turn_provider_context",
    "in_flight_stage_context",
)
SESSION_CONTEXT_LOSS = (
    "active_turn_provider_context",
    "provider_conversation_context",
    "provider_session_context",
    "in_flight_stage_context",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], *, capture: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=capture,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (result.stdout or "")
        + (result.stderr or ""),
    )
    return result.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact three-file FW-RT6-10a Control C surface conform")


def check_accepted_control_a_b() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-10a-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10a-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-10a-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10a-B-ACCEPTANCE-SYNC:END",
    ):
        _require(tasklist.count(marker) == 1, f"accepted sync marker drift: {marker}")
    for phrase in (
        "Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED",
        "Control A acceptance sync: 2fe31e3c6a18f62696cd12f4f153c026d6f113a6",
        "Control B implementation: d91430aff9aba804b37f3849fc7134e1eda19c6f",
    ):
        _require(phrase in tasklist, f"accepted Control A/B fact missing: {phrase}")

    control_a_source = (
        PROJECT_ROOT / "tests/test_recovery_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_source = (
        PROJECT_ROOT / "tests/test_recovery_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_source.count("    def test_") == 13, "Control A test count drift")
    _require(control_b_source.count("    def test_") == 14, "Control B test count drift")
    for name, source in (
        ("test_reset_plans_document_exact_provider_context_loss", control_a_source),
        ("test_reset_failure_is_typed_safe_and_does_not_claim_generation_advance", control_a_source),
        ("test_reset_retires_old_completion_and_accepts_replacement", control_b_source),
        ("test_terminal_reset_reserves_replacement_for_next_turn", control_b_source),
        ("test_completion_and_reset_are_linearized_by_session_operation_lock", control_b_source),
    ):
        _require(f"def {name}(" in source, f"accepted recovery/reset test missing: {name}")

    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_recovery_control_a",
            "tests.test_recovery_control_b",
        ],
        capture=False,
    )
    print("[OK] accepted Control A+B recovery/reset regressions conform")


def check_planning_contract() -> None:
    from framework.lifecycle import RecoveryAction
    from framework.recovery_control import (
        RecoveryControlDisposition,
        RecoveryResetErrorCode,
        RecoveryResetOutcome,
        RecoveryResetResult,
        RecoveryResetScope,
        build_recovery_control_plan,
    )

    none_plan = build_recovery_control_plan(RecoveryAction.NONE)
    reuse_plan = build_recovery_control_plan(RecoveryAction.REUSE_SESSION)
    for plan in (none_plan, reuse_plan):
        _require(
            plan.disposition is RecoveryControlDisposition.REUSE_SESSION,
            "reusable disposition drift",
        )
        _require(not plan.execute_reset and plan.reset_scope is None, "reuse scope drift")
        result = RecoveryResetResult.for_non_reset_plan(plan)
        _require(result.outcome is RecoveryResetOutcome.NOT_REQUIRED, "reuse result drift")

    turn_plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)
    session_plan = build_recovery_control_plan(RecoveryAction.RESET_SESSION)
    _require(turn_plan.reset_scope is RecoveryResetScope.TURN_ONLY, "turn scope drift")
    _require(session_plan.reset_scope is RecoveryResetScope.SESSION, "session scope drift")
    _require(turn_plan.provider_context_loss == TURN_CONTEXT_LOSS, "turn loss drift")
    _require(
        session_plan.provider_context_loss == SESSION_CONTEXT_LOSS,
        "session loss drift",
    )
    _require(
        turn_plan.generation_advance_required
        and session_plan.generation_advance_required,
        "reset generation requirement drift",
    )

    expected = {
        RecoveryAction.RECONNECT: RecoveryResetOutcome.RECONNECT_REQUIRED,
        RecoveryAction.CLOSE_SESSION: RecoveryResetOutcome.CLOSE_REQUIRED,
        RecoveryAction.PERMANENT_FAILURE: RecoveryResetOutcome.PERMANENTLY_FAILED,
    }
    for action, outcome in expected.items():
        plan = build_recovery_control_plan(action)
        result = RecoveryResetResult.for_non_reset_plan(plan)
        _require(result.outcome is outcome, f"typed disposition drift: {action.value}")
        _require(not result.generation_advanced, "non-reset disposition advanced generation")
    permanent = build_recovery_control_plan(RecoveryAction.PERMANENT_FAILURE)
    _require(
        permanent.close_required and permanent.permanently_failed,
        "permanent failure lost close requirement",
    )

    failed = RecoveryResetResult.failed(
        session_plan,
        error_code=RecoveryResetErrorCode.RESET_FAILED,
    )
    _require(failed.outcome is RecoveryResetOutcome.FAILED, "typed failure drift")
    _require(not failed.generation_advanced, "failed reset claimed generation advance")
    print("[OK] reusable/reset/reconnect/close/permanent planning is typed")
    print("[OK] reset scopes, provider-context loss, and typed failure conform")


def check_reset_execution_contract() -> None:
    import framework
    from framework.lifecycle import RecoveryAction
    from framework.realtime import RealtimeTurn, RealtimeTurnResult
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
    _require(previous is not None, "admitted turn lost generation")
    gate = session._generation_gate
    before_diagnostics = dict(session.generation_diagnostics)
    before_events = tuple(session.event_history)
    plan = build_recovery_control_plan(RecoveryAction.RESET_TURN)

    applied = session.reset(plan)
    _require(applied.plan is plan, "reset rebuilt the exact accepted plan")
    _require(applied.outcome is RecoveryResetOutcome.APPLIED, "turn reset not applied")
    _require(applied.previous_generation_id == previous, "old generation drift")
    _require(
        applied.current_generation_id != previous,
        "reset did not establish a distinct generation",
    )
    _require(session._generation_gate is gate, "generation owner was replaced")
    _require(tuple(session.event_history) == before_events, "reset event was invented")
    after_diagnostics = dict(session.generation_diagnostics)
    _require(
        set(after_diagnostics) == EXPECTED_DIAGNOSTIC_KEYS,
        "generation diagnostics keys changed",
    )
    _require(
        after_diagnostics["generation_start_count"]
        == before_diagnostics["generation_start_count"] + 1,
        "reset replacement generation count drift",
    )

    delivered: list[str] = []
    stale = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn.turn_id,
            generation_id=previous,
            stage="recovery_reset_acceptance_old",
            value="old",
        ),
        deliver=delivered.append,
    )
    _require(not stale.accepted, "reset-retired completion was accepted")
    _require(stale.retired_by is GenerationAdvanceReason.RESET, "reset reason drift")
    _require(not delivered, "reset-retired value crossed delivery boundary")

    current = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn.turn_id,
            generation_id=applied.current_generation_id,
            stage="recovery_reset_acceptance_current",
            value="current",
        ),
        deliver=delivered.append,
    )
    _require(current.accepted and delivered == ["current"], "replacement rejected")

    terminal_session = framework.create_realtime_session()
    terminal = terminal_session.run_turn(input_text="terminal")
    terminal_reset = terminal_session.reset(
        build_recovery_control_plan(RecoveryAction.RESET_SESSION)
    )
    _require(
        terminal_reset.previous_generation_id == terminal.generation_id,
        "terminal reset lost previous generation",
    )
    next_turn = terminal_session.start_turn(input_text="next")
    _require(
        next_turn.generation_id == terminal_reset.current_generation_id,
        "next turn did not consume exact replacement generation",
    )

    interrupted = RealtimeTurnResult.interrupted(
        turn_id=turn.turn_id,
        session_id=session.info.session_id,
        generation_id=applied.current_generation_id,
    )
    _require(
        interrupted.recovery_action is RecoveryAction.RESET_TURN,
        "interrupt recovery action is not typed",
    )
    _require(
        build_recovery_control_plan(interrupted.recovery_action).reset_scope.value
        == "turn_only",
        "interrupt recovery did not retain turn scope",
    )

    empty = framework.create_realtime_session()
    missing = empty.reset(build_recovery_control_plan(RecoveryAction.RESET_TURN))
    _require(
        missing.error_code is RecoveryResetErrorCode.GENERATION_MISMATCH,
        "missing-generation failure is not typed",
    )
    closed = framework.create_realtime_session()
    closed.start_turn(input_text="close")
    closed.close()
    closed_result = closed.reset(
        build_recovery_control_plan(RecoveryAction.RESET_SESSION)
    )
    _require(
        closed_result.error_code is RecoveryResetErrorCode.SESSION_CLOSED,
        "closed-session reset failure is not typed",
    )
    _require(
        not missing.generation_advanced and not closed_result.generation_advanced,
        "typed reset failure claimed generation advance",
    )
    print("[OK] reset advances exactly one generation through the existing owner")
    print("[OK] reset-retired completion is rejected before delivery")
    print("[OK] interrupt recovery, terminal handoff, and reset failures are typed")


def check_public_compatibility_and_provider_isolation() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.recovery_control' not in sys.modules; "
        "assert not hasattr(framework, 'RecoveryControlPlan'); "
        "assert hasattr(framework.RealtimeSession, 'reset'); "
        "assert len(framework.__all__) == 127; "
        "assert 'pyvts' not in sys.modules; "
        "assert 'websockets' not in sys.modules"
    )
    _run([sys.executable, "-c", code])

    import framework
    import framework.recovery_control as recovery_control

    _require(
        tuple(recovery_control.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "explicit recovery package exports changed",
    )
    _require(
        tuple(inspect.signature(framework.RealtimeSession.reset).parameters)
        == ("self", "plan"),
        "RealtimeSession.reset signature drift",
    )
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "realtime factory signature drift",
    )
    _require(len(tuple(framework.RealtimeEventType)) == 48, "event vocabulary changed")
    _require("RESET" not in framework.RealtimeEventType.__members__, "reset event added")
    _require(len(framework.__all__) == 127, "root-public names changed")
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API version drift",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version drift",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] root-public/version/event/factory contracts remain unchanged")
    print("[OK] recovery models remain explicit-package-only and provider-free")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-10a — Recovery/reset semantics")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 7 and section.count("- [ ]") == 0,
        "FW-RT6-10a must be 7 / 7 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            text.count("FW-RT6-10a-C-AGGREGATE-ACCEPTANCE:BEGIN") == 1,
            "Control C aggregate begin marker missing or duplicated",
        )
        _require(
            text.count("FW-RT6-10a-C-AGGREGATE-ACCEPTANCE:END") == 1,
            "Control C aggregate end marker missing or duplicated",
        )
    for marker in (
        "Control C exact surface: 3 files",
        "focused Control A+B recovery/reset tests: 27 / PASS",
        "accepted FW-RT6-9d aggregate regression: 27 / PASS",
        "full Framework unit suite: 520 / PASS",
        "turn-only reset scope: turn_only / PASS",
        "session reset scope: session / PASS",
        "reset provider-context loss: DOCUMENTED / PASS",
        "reset generation advance: EXACTLY 1 / PASS",
        "old completion after reset delivered: False / PASS",
        "reset failure: TYPED / PASS",
        "runtime source changed by Control C: False",
        "existing tests changed by Control C: False",
        "FW-RT6-10a tasks: 7 / 7 ACCEPTED-CANDIDATE",
        "FW-RT6-10a final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-10b implementation: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    for phrase in (
        "A reset advances generation by establishing exactly one distinct",
        "Reset does not reinterpret reconnect, close, or permanent failure",
        "Final closure remains a separate",
    ):
        _require(phrase in facade, f"public facade boundary missing: {phrase}")
    print("[OK] seven FW-RT6-10a tasks close as aggregate acceptance-candidates")


def check_runtime_and_deferred_scope() -> None:
    forbidden_prefixes = (
        "framework/",
        "core/",
        "llm/",
        "plugins/",
        "stt/",
        "tests/",
        "tts/",
    )
    changed_runtime = {
        path for path in _changed_paths() if path.startswith(forbidden_prefixes)
    }
    _require(
        not changed_runtime,
        f"Control C changed runtime/existing tests: {sorted(changed_runtime)!r}",
    )
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    _require(
        "FW-RT6-10b implementation: NOT_AUTHORIZED" in tasklist,
        "FW-RT6-10b authorization boundary drift",
    )
    print("[OK] Control C introduces no runtime, existing-test, or FW-RT6-10b change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_b()
    check_planning_contract()
    check_reset_execution_contract()
    check_public_compatibility_and_provider_isolation()
    check_docs_and_task_closure()
    if not args.source_only:
        check_runtime_and_deferred_scope()

    print("v600_rt6_10a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10a_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10a_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10a_control_c_exact_surface: 3 files")
    print("v600_rt6_10a_runtime_changed_by_control_c: False")
    print("v600_rt6_10a_existing_tests_changed_by_control_c: False")
    print("v600_rt6_10a_recovery_owner: RecoveryAction / REUSED")
    print("v600_rt6_10a_generation_owner: RealtimeGenerationGate / REUSED")
    print("v600_rt6_10a_turn_reset_scope: turn_only / PASS")
    print("v600_rt6_10a_session_reset_scope: session / PASS")
    print("v600_rt6_10a_replacement_generation_count: 1 / PASS")
    print("v600_rt6_10a_old_completion_after_reset: False / PASS")
    print("v600_rt6_10a_reset_failure: TYPED / PASS")
    print("v600_rt6_10a_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_10a_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_10b: NOT_AUTHORIZED")
    print("v600_rt6_10a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10a Control C aggregate recovery/reset gate passed")


if __name__ == "__main__":
    main()
