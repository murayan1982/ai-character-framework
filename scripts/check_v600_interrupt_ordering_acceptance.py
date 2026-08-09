"""FW-RT6-9b Control C aggregate interrupt-ordering acceptance gate.

The gate uses only deterministic mock sessions and in-memory stages. It imports
no provider SDK and performs no network, audio, microphone, VTube Studio, or
real motion operation.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "941887a36e530be77aaa2406251913166b976734"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_interrupt_ordering_acceptance.py",
}
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
EXPECTED_EXPLICIT_EXPORTS = (
    "DEFAULT_INTERRUPT_ORDERING_POLICY",
    "InterruptAdmissionOutcome",
    "InterruptOrderingDecision",
    "InterruptOrderingKey",
    "InterruptOrderingPolicy",
    "InterruptOrderingRule",
)
EXPECTED_RULES = (
    "resolved_turn_identity",
    "replay_owner_terminal_result",
    "first_terminal_reservation_wins",
    "first_admission_wins",
    "owner_flush_before_terminal",
    "typed_reject_new_turn",
)
EXPECTED_ADMISSION_OUTCOMES = (
    "owner",
    "duplicate_replay",
    "existing_terminal",
    "already_closed",
    "new_turn_rejected",
)
EXPECTED_RACE_TESTS = (
    "test_concurrent_and_later_duplicate_replay_exact_owner_result",
    "test_interrupt_reservation_suppresses_later_normal_terminal",
    "test_preexisting_normal_terminal_wins_without_interrupt_effects",
    "test_interrupt_admitted_before_close_finishes_first",
    "test_close_admitted_first_returns_existing_closed_result",
    "test_owner_flush_precedes_terminal_and_standalone_reuses_it",
    "test_new_turn_during_interrupt_is_immediate_typed_reject",
    "test_cancel_and_interrupt_share_one_resolved_turn_owner",
    "test_reentrant_interrupt_callback_replays_prepared_owner_result",
    "test_reentrant_owner_flush_callback_reuses_prepared_result",
    "test_public_factory_versions_and_root_surface_remain_unchanged",
)


def _require(value: bool, message: str) -> None:
    if not value:
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
    print("[OK] baseline and exact three-file FW-RT6-9b Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_b = _load(
        "_fw_rt6_9b_control_b_for_aggregate",
        "scripts/smoke_v600_interrupt_ordering_control_b.py",
    )
    control_b.check_runtime_contract()
    control_b.check_source_contract()
    control_b.check_docs()
    print("[OK] accepted Control A+B interrupt-ordering regressions conform")


def check_ordering_policy_and_race_inventory() -> None:
    import framework
    import framework.interrupt_ordering as ordering
    from framework.interrupt_ordering import (
        DEFAULT_INTERRUPT_ORDERING_POLICY,
        InterruptAdmissionOutcome,
        InterruptOrderingRule,
    )

    _require(tuple(ordering.__all__) == EXPECTED_EXPLICIT_EXPORTS, "exports drift")
    _require(
        tuple(item.value for item in InterruptOrderingRule) == EXPECTED_RULES,
        "ordering rule vocabulary drift",
    )
    _require(
        tuple(item.value for item in InterruptAdmissionOutcome)
        == EXPECTED_ADMISSION_OUTCOMES,
        "admission outcome vocabulary drift",
    )
    _require(
        DEFAULT_INTERRUPT_ORDERING_POLICY.idempotency_key_fields
        == ("session_id", "resolved_turn_id"),
        "accepted idempotency key drift",
    )
    _require(
        not DEFAULT_INTERRUPT_ORDERING_POLICY.request_id_required,
        "a second public interrupt request ID was introduced",
    )
    test_source = (
        PROJECT_ROOT / "tests/test_interrupt_ordering_control_b.py"
    ).read_text(encoding="utf-8")
    for test_name in EXPECTED_RACE_TESTS:
        _require(
            f"def {test_name}(" in test_source,
            f"deterministic race test missing: {test_name}",
        )
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "create_realtime_session signature drift",
    )
    print("[OK] explicit policy, all six rules, and eleven race tests conform")


def check_owner_duplicate_runtime() -> None:
    import framework
    from framework.output_control import (
        InterruptRequest,
        InterruptScope,
    )

    support = _load(
        "_fw_rt6_9b_control_b_test_support",
        "tests/test_interrupt_ordering_control_b.py",
    )
    stage = support._OrderedTextStage()
    session = framework.create_realtime_session(text_generation_stage=stage)
    started, stage_thread = support._active_stage(session, stage)
    request = InterruptRequest(
        scope=InterruptScope.LLM_STREAM,
        turn_id=started.turn_id,
        timeout_seconds=0.5,
    )
    owner_thread, owner = support._thread_call(lambda: session.interrupt(request))
    _require(stage.cancel_entered.wait(timeout=3.0), "owner cancel did not start")
    duplicate_thread, duplicate = support._thread_call(
        lambda: session.cancel_current_turn()
    )
    time.sleep(0.02)
    _require(duplicate_thread.is_alive(), "duplicate did not wait for the owner")
    stage.cancel_release.set()
    for thread in (owner_thread, duplicate_thread, stage_thread):
        thread.join(timeout=3.0)
        _require(not thread.is_alive(), "ordered interrupt thread did not finish")

    _require(len(owner) == 1 and len(duplicate) == 1, "interrupt result missing")
    _require(owner[0] is duplicate[0], "duplicate did not replay exact owner result")
    _require(session.interrupt(request) is owner[0], "later duplicate identity drift")
    _require(stage.cancel_count == 1, "duplicate repeated subsystem cancellation")
    event_types = [event.type for event in session.event_history]
    _require(
        event_types.count(framework.RealtimeEventType.INTERRUPT_REQUESTED) == 1,
        "duplicate repeated interrupt events",
    )
    _require(
        event_types.count(framework.RealtimeEventType.TURN_INTERRUPTED) == 1,
        "duplicate emitted multiple turn terminals",
    )
    session.close()
    print("[OK] sole owner, exact duplicate replay, and single effects conform")


def check_reentrant_corrective_runtime() -> None:
    import framework
    from framework.output_control import InterruptRequest, OutputFlushRequest

    support = _load(
        "_fw_rt6_9b_reentrant_test_support",
        "tests/test_interrupt_ordering_control_b.py",
    )
    interrupt_session = support._CompletionRaceSession()
    interrupt_session.interrupt_release.set()
    started = interrupt_session.start_turn(input_text="aggregate reentrant interrupt")
    callback_results: list[object] = []

    def interrupt_callback(event) -> None:
        if (
            event.type is framework.RealtimeEventType.INTERRUPT_REQUESTED
            and not callback_results
        ):
            callback_results.append(interrupt_session.cancel_current_turn())

    interrupt_session.on_event(interrupt_callback)
    owner_thread, owner = support._thread_call(
        lambda: interrupt_session.interrupt(
            InterruptRequest(turn_id=started.turn_id)
        )
    )
    owner_thread.join(timeout=3.0)
    _require(not owner_thread.is_alive(), "reentrant interrupt self-deadlocked")
    _require(
        len(owner) == 1
        and len(callback_results) == 1
        and callback_results[0] is owner[0],
        "reentrant interrupt did not replay exact prepared owner result",
    )
    interrupt_events = [event.type for event in interrupt_session.event_history]
    _require(
        interrupt_events.count(framework.RealtimeEventType.INTERRUPT_REQUESTED)
        == 1,
        "reentrant callback repeated the interrupt event",
    )
    interrupt_session.close()

    flush_session = support._FlushCountingSession()
    flush_started = flush_session.start_turn(input_text="aggregate reentrant flush")
    flush_callbacks: list[object] = []

    def flush_callback(event) -> None:
        if (
            event.type is framework.RealtimeEventType.OUTPUT_FLUSH_REQUESTED
            and not flush_callbacks
        ):
            flush_callbacks.append(
                flush_session.flush_output(
                    OutputFlushRequest(turn_id=flush_started.turn_id)
                )
            )

    flush_session.on_event(flush_callback)
    flush_session.interrupt(
        InterruptRequest(
            turn_id=flush_started.turn_id,
            flush_output=True,
        )
    )
    work = flush_session._interrupt_requests[
        (flush_started.session_id, flush_started.turn_id)
    ]
    _require(flush_session.flush_count == 1, "reentrant flush repeated its effect")
    _require(
        len(flush_callbacks) == 1 and flush_callbacks[0] is work.flush_result,
        "reentrant flush did not reuse the prepared result",
    )
    flush_events = [event.type for event in flush_session.event_history]
    _require(
        flush_events.count(framework.RealtimeEventType.OUTPUT_FLUSH_REQUESTED)
        == 1,
        "reentrant flush repeated its request event",
    )
    _require(
        flush_events.count(framework.RealtimeEventType.OUTPUT_FLUSH_COMPLETED)
        == 1,
        "reentrant flush repeated its completion event",
    )
    flush_session.close()
    print("[OK] reentrant interrupt and flush corrective behavior conforms")


def check_public_compatibility() -> None:
    import framework

    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(
        not hasattr(framework, "InterruptOrderingDecision"),
        "explicit ordering package leaked into the root facade",
    )
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API version drift",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version drift",
    )
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] public facade, versions, and provider isolation conform")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-9b — Duplicate interrupt and race ordering")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 7 and section.count("- [ ]") == 0,
        "FW-RT6-9b must be 7 / 7 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-9b-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
    for marker in (
        "FW-RT6-9b tasks: 7 / 7 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "same-owner interrupt callback self-deadlock: False / PASS",
        "same-owner reentrant flush effect count: 1 / PASS",
        "FW-RT6-9b final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-9c implementation: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    _require(
        "Control C changes no runtime source" in facade,
        "runtime boundary missing from public facade",
    )
    _require(
        "accepted-candidate" in facade,
        "aggregate acceptance-candidate boundary missing",
    )
    print("[OK] seven FW-RT6-9b tasks close as aggregate acceptance-candidates")


def check_runtime_and_deferred_scope() -> None:
    runtime_prefixes = (
        "framework/",
        "core/",
        "llm/",
        "providers/",
        "stt/",
        "tests/",
        "tts/",
        "vts/",
    )
    runtime = {
        path
        for path in _changed_paths()
        if path.startswith(runtime_prefixes)
    }
    _require(not runtime, f"Control C changed runtime/tests: {sorted(runtime)!r}")
    print("[OK] Control C introduces no runtime source, existing-test, or FW-RT6-9c change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_b()
    check_ordering_policy_and_race_inventory()
    check_owner_duplicate_runtime()
    check_reentrant_corrective_runtime()
    check_public_compatibility()
    check_docs_and_task_closure()
    if not args.source_only:
        check_runtime_and_deferred_scope()
    print("v600_rt6_9b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9b_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9b_control_c_exact_surface: 3 files")
    print("v600_rt6_9b_runtime_changed_by_control_c: False")
    print("v600_rt6_9b_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_9b_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_9c_status: NOT_AUTHORIZED")
    print("v600_rt6_9b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9b Control C aggregate acceptance gate passed")


if __name__ == "__main__":
    main()
