"""FW-RT6-9c Control C aggregate barge-in acceptance gate.

The gate uses only deterministic in-memory sessions and mock stages.  It
performs no provider, network, audio, microphone, or real VTS operation.
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import importlib.util
import inspect
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "080070b740c7178623f578b134945df3c0dd513f"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_barge_in_acceptance.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "BargeInControlPlan",
    "build_barge_in_control_plan",
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
EXPECTED_INTERRUPT_REQUEST_FIELDS = (
    "scope",
    "reason",
    "turn_id",
    "flush_output",
    "cancel_tts_queue",
    "cancel_llm_stream",
    "stop_motion",
    "public_metadata",
    "timeout_seconds",
)
EXPECTED_INTERRUPT_RESULT_FIELDS = (
    "outcome",
    "scope",
    "reason",
    "turn_id",
    "safe_message",
    "retryable",
    "provider_cancel_supported",
    "queue_flush_supported",
    "public_metadata",
    "motion_result",
)
EXPECTED_CONTROL_A_TESTS = (
    "test_rejected_decision_builds_a_non_executing_plan",
    "test_soft_interrupt_plan_is_capability_independent",
    "test_unsupported_flush_downgrades_without_claiming_execution",
    "test_unsupported_hard_cancel_truthfully_downgrades_to_soft",
    "test_control_models_do_not_import_provider_modules",
)
EXPECTED_CONTROL_B_TESTS = (
    "test_decision_remains_separate_from_interrupt_execution",
    "test_exact_plan_request_is_delegated_without_reinterpretation",
    "test_soft_plan_reaches_existing_ordered_interrupt_owner",
    "test_hard_cancel_downgrade_executes_only_supported_soft_request",
    "test_unsupported_flush_plan_has_no_interrupt_or_flush_effect",
    "test_plan_capabilities_must_match_executing_session",
    "test_duplicate_execution_replays_exact_owner_result_once",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + result.stdout
        + result.stderr,
    )
    return result.stdout


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


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    _require(spec is not None and spec.loader is not None, f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    print("[OK] baseline and exact three-file FW-RT6-9c Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_a = _load(
        "_fw_rt6_9c_control_a_for_aggregate",
        "scripts/smoke_v600_barge_in_control_a.py",
    )
    control_a.check_import_contract()
    _run([sys.executable, "-m", "unittest", "tests.test_barge_in_control_a"])
    control_a.check_docs()

    control_b = _load(
        "_fw_rt6_9c_control_b_for_aggregate",
        "scripts/smoke_v600_barge_in_control_b.py",
    )
    control_b.check_import_contract()
    control_b.check_runtime_contract()
    control_b.check_docs()
    print("[OK] accepted Control A+B barge-in regressions conform")


def check_decision_and_plan_separation() -> None:
    import framework
    import framework.barge_in_control as control
    from framework.barge_in_control import build_barge_in_control_plan
    from framework.output_control import BargeInPolicy

    _require(tuple(control.__all__) == EXPECTED_EXPLICIT_EXPORTS, "exports drift")
    control_a_source = (
        PROJECT_ROOT / "tests/test_barge_in_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_source = (
        PROJECT_ROOT / "tests/test_barge_in_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_source.count("    def test_") == 12, "Control A test count drift")
    _require(control_b_source.count("    def test_") == 12, "Control B test count drift")
    for test_name in EXPECTED_CONTROL_A_TESTS:
        _require(
            f"def {test_name}(" in control_a_source,
            f"Control A regression missing: {test_name}",
        )
    for test_name in EXPECTED_CONTROL_B_TESTS:
        _require(
            f"def {test_name}(" in control_b_source,
            f"Control B regression missing: {test_name}",
        )

    session = framework.create_realtime_session()
    started = session.start_turn(input_text="aggregate decision separation")
    _require(started.accepted, "aggregate decision turn was not admitted")
    session.set_barge_in_policy(BargeInPolicy.soft_interrupt())
    decision = session.decide_barge_in(turn_id=started.turn_id)
    decision_events = tuple(session.event_history)
    decision_event_types = tuple(event.type for event in decision_events)
    _require(decision.accepted, "soft barge-in decision was rejected")
    _require(session.terminal_results == (), "decision reserved a terminal")
    _require(
        framework.RealtimeEventType.BARGE_IN_ACCEPTED in decision_event_types,
        "accepted decision event missing",
    )
    for event_type in (
        framework.RealtimeEventType.INTERRUPT_REQUESTED,
        framework.RealtimeEventType.OUTPUT_FLUSH_REQUESTED,
        framework.RealtimeEventType.TURN_INTERRUPTED,
    ):
        _require(event_type not in decision_event_types, "decision executed an effect")

    plan = build_barge_in_control_plan(
        decision,
        capabilities=session.capabilities,
    )
    _require(not plan.decision_is_execution, "decision was relabeled as execution")
    _require(plan.side_effect_free, "control plan claimed a side effect")
    _require(plan.coordinator_request is not None, "executable plan has no request")
    _require(tuple(session.event_history) == decision_events, "plan emitted an event")
    _require(session.terminal_results == (), "plan reserved a terminal")
    session.close()
    print("[OK] decision, explicit plan projection, and execution remain separated")


def check_execution_owner_and_event_order() -> None:
    import framework
    from framework.barge_in_control import build_barge_in_control_plan
    from framework.output_control import BargeInDecision, BargeInPolicy, BargeInPolicyMode

    support = _load(
        "_fw_rt6_9c_control_b_test_support",
        "tests/test_barge_in_control_b.py",
    )

    capture = support._CaptureSession()
    hard_plan = build_barge_in_control_plan(
        BargeInDecision.accepted_for_policy(
            BargeInPolicy.hard_cancel(),
            turn_id="turn-aggregate-capture",
        ),
        capabilities=capture.capabilities,
    )
    request = hard_plan.coordinator_request
    _require(hard_plan.requested_mode is BargeInPolicyMode.HARD_CANCEL, "request drift")
    _require(hard_plan.effective_mode is BargeInPolicyMode.SOFT_INTERRUPT, "downgrade drift")
    _require(hard_plan.capability_downgraded, "downgrade fact missing")
    _require(not hard_plan.provider_hard_cancel_planned, "provider cancel overclaimed")
    _require(request is not None, "downgraded plan lost its cooperative request")
    _require(not request.cancel_llm_stream, "unsupported provider cancel was requested")
    capture.execute_barge_in(hard_plan)
    _require(capture.delegated_request is request, "exact request identity was lost")
    capture.close()

    stage = support._CancelableTextStage()
    session = framework.create_realtime_session(text_generation_stage=stage)
    started, stage_thread = support._start_active_stage(session, stage)
    session.set_barge_in_policy(BargeInPolicy.soft_interrupt())
    decision = session.decide_barge_in(turn_id=started.turn_id)
    plan = build_barge_in_control_plan(decision, capabilities=session.capabilities)
    first = session.execute_barge_in(plan)
    stage_thread.join(timeout=3.0)
    _require(not stage_thread.is_alive(), "barge-in stage did not finish")
    second = session.execute_barge_in(plan)

    _require(second is first, "duplicate did not replay exact owner result")
    _require(stage.cancel_count == 1, "duplicate repeated subsystem cancellation")
    event_types = tuple(event.type for event in session.event_history)
    ordered = (
        framework.RealtimeEventType.BARGE_IN_DETECTED,
        framework.RealtimeEventType.BARGE_IN_ACCEPTED,
        framework.RealtimeEventType.INTERRUPT_REQUESTED,
        framework.RealtimeEventType.INTERRUPT_ACCEPTED,
        framework.RealtimeEventType.INTERRUPT_COMPLETED,
        framework.RealtimeEventType.TURN_INTERRUPTED,
    )
    positions = tuple(event_types.index(event_type) for event_type in ordered)
    _require(positions == tuple(sorted(positions)), "barge-in event ordering drift")
    _require(
        event_types.count(framework.RealtimeEventType.INTERRUPT_REQUESTED) == 1,
        "duplicate repeated interrupt events",
    )
    _require(
        event_types.count(framework.RealtimeEventType.TURN_INTERRUPTED) == 1,
        "multiple turn terminal events were emitted",
    )
    session.close()
    print("[OK] exact coordinator delegation, duplicate replay, and event order conform")


def check_nonexecuting_and_capability_guards() -> None:
    import framework
    from framework.barge_in_control import build_barge_in_control_plan
    from framework.output_control import (
        BargeInDecision,
        BargeInPolicy,
        InterruptOutcome,
    )
    from framework.realtime_capabilities import RealtimeCapabilitySnapshot

    session = framework.create_realtime_session()
    started = session.start_turn(input_text="aggregate unsupported flush")
    flush_plan = build_barge_in_control_plan(
        BargeInDecision.accepted_for_policy(
            BargeInPolicy.flush_output(),
            turn_id=started.turn_id,
        ),
        capabilities=session.capabilities,
    )
    before = tuple(session.event_history)
    result = session.execute_barge_in(flush_plan)
    _require(not flush_plan.execute_interrupt, "unsupported flush became executable")
    _require(flush_plan.coordinator_request is None, "non-executing plan has a request")
    _require(result.outcome is InterruptOutcome.UNSUPPORTED, "typed unsupported missing")
    _require(tuple(session.event_history) == before, "non-executing plan emitted effects")
    _require(session.terminal_results == (), "non-executing plan terminated the turn")

    mismatch = build_barge_in_control_plan(
        BargeInDecision.accepted_for_policy(BargeInPolicy.hard_cancel()),
        capabilities=RealtimeCapabilitySnapshot(
            session_id=session.capabilities.session_id,
            hard_cancel_supported=True,
            tts_queue_flush_supported=True,
        ),
    )
    try:
        session.execute_barge_in(mismatch)
    except ValueError as error:
        _require("executing session" in str(error), "capability rejection message drift")
    else:
        raise AssertionError("capability-mismatched plan was executed")
    session.close()
    print("[OK] unsupported execution and capability mismatch guards conform")


def check_public_compatibility_and_provider_isolation() -> None:
    import framework
    from framework.output_control import BargeInPolicy, InterruptRequest, InterruptResult

    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(
        "BargeInControlPlan" not in framework.__all__,
        "explicit plan package leaked into the root facade",
    )
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "create_realtime_session signature drift",
    )
    _require(
        tuple(inspect.signature(framework.RealtimeSession.execute_barge_in).parameters)
        == ("self", "plan"),
        "execute_barge_in signature drift",
    )
    _require(
        tuple(item.name for item in fields(InterruptRequest))
        == EXPECTED_INTERRUPT_REQUEST_FIELDS,
        "InterruptRequest fields drift",
    )
    _require(
        tuple(item.name for item in fields(InterruptResult))
        == EXPECTED_INTERRUPT_RESULT_FIELDS,
        "InterruptResult fields drift",
    )
    _require(fields(BargeInPolicy)[2].default is False, "flush default drift")
    _require(BargeInPolicy().flush_output is False, "flush instance fact drift")
    _require(BargeInPolicy.flush_output().flush_output is True, "flush factory drift")
    _require(len(tuple(framework.RealtimeEventType)) == 48, "event vocabulary drift")
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
    for relative in (
        "framework/barge_in_control.py",
        "framework/realtime_session.py",
    ):
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for token in ("import pyaudio", "import sounddevice", "pyaudio.", "sounddevice."):
            _require(token not in source, f"microphone runtime escaped into {relative}")
    print("[OK] public contracts, versions, and provider/microphone isolation conform")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-9c — Barge-in decision and execution separation")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 5 and section.count("- [ ]") == 0,
        "FW-RT6-9c must be 5 / 5 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-9c-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
        _require(
            "FW-RT6-9c-C-AGGREGATE-ACCEPTANCE:END" in text,
            "Control C aggregate end marker missing",
        )
    for marker in (
        "FW-RT6-9c tasks: 5 / 5 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "existing tests changed by Control C: False",
        "decision automatically executes: False / PASS",
        "microphone detection in core: False / PASS",
        "unsupported hard cancel effective mode: soft_interrupt / PASS",
        "FW-RT6-9c final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-9d implementation: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    _require(
        "These remain three distinct operations" in facade,
        "decision/plan/execution separation missing from public facade",
    )
    _require(
        "Final closure remains a separate one-file acceptance sync" in facade,
        "final acceptance boundary missing from public facade",
    )
    print("[OK] five FW-RT6-9c tasks close as aggregate acceptance-candidates")


def check_runtime_and_deferred_scope() -> None:
    forbidden_prefixes = (
        "framework/",
        "core/",
        "llm/",
        "providers/",
        "stt/",
        "tests/",
        "tts/",
        "vts/",
    )
    changed_runtime = {
        path for path in _changed_paths() if path.startswith(forbidden_prefixes)
    }
    _require(
        not changed_runtime,
        f"Control C changed runtime/tests: {sorted(changed_runtime)!r}",
    )
    print("[OK] Control C introduces no runtime, existing-test, or FW-RT6-9d change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_b()
    check_decision_and_plan_separation()
    check_execution_owner_and_event_order()
    check_nonexecuting_and_capability_guards()
    check_public_compatibility_and_provider_isolation()
    check_docs_and_task_closure()
    if not args.source_only:
        check_runtime_and_deferred_scope()
    print("v600_rt6_9c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9c_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9c_control_c_exact_surface: 3 files")
    print("v600_rt6_9c_runtime_changed_by_control_c: False")
    print("v600_rt6_9c_existing_tests_changed_by_control_c: False")
    print("v600_rt6_9c_decision_is_execution: False / PASS")
    print("v600_rt6_9c_microphone_detection_in_core: False / PASS")
    print("v600_rt6_9c_capability_downgrade_truthful: True / PASS")
    print("v600_rt6_9c_task_count: 5 / 5 ACCEPTED-CANDIDATE")
    print("v600_rt6_9c_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_9d_status: NOT_AUTHORIZED")
    print("v600_rt6_9c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9c Control C aggregate acceptance gate passed")


if __name__ == "__main__":
    main()
