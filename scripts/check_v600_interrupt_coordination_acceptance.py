"""FW-RT6-9a Control C aggregate interrupt-coordination acceptance gate.

The gate uses only deterministic mock sessions and injected in-memory stages.
It imports no provider SDK and performs no network, audio, microphone, VTube
Studio, or real motion operation.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "a013d04092d04ad94ac9be915da8b93f0e063c01"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_interrupt_coordination_acceptance.py",
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
EXPECTED_SUBSYSTEMS = (
    "text_generation",
    "tts_generation",
    "tts_queue",
    "audio_artifact",
    "motion",
)
EXPECTED_SUBSYSTEM_OUTCOMES = (
    "completed",
    "requested",
    "not_active",
    "already_terminal",
    "unsupported",
    "timed_out",
    "already_closed",
    "failed",
)
EXPECTED_AGGREGATE_OUTCOMES = (
    "completed",
    "partial",
    "requested",
    "no_active_turn",
    "already_terminal",
    "unsupported",
    "timed_out",
    "already_closed",
    "failed",
)
EXPECTED_EXPLICIT_EXPORTS = (
    "InterruptAggregateOutcome",
    "InterruptAggregateResult",
    "InterruptSubsystem",
    "InterruptSubsystemOutcome",
    "InterruptSubsystemResult",
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


def _result_for(result, subsystem):
    aggregate = result.coordination_result
    _require(aggregate is not None, "coordination result is missing")
    return next(
        item
        for item in aggregate.subsystem_results
        if item.subsystem is subsystem
    )


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
    print("[OK] baseline and exact three-file FW-RT6-9a Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_b = _load(
        "_fw_rt6_9a_control_b_for_aggregate",
        "scripts/smoke_v600_interrupt_coordinator_control_b.py",
    )
    control_b.check_runtime_contract()
    control_b.check_source_contract()
    control_b.check_docs()
    print("[OK] accepted Control A+B interrupt-coordination regressions conform")


def check_aggregate_runtime_contract() -> None:
    import framework
    from framework.interrupt_coordination import (
        InterruptAggregateOutcome,
        InterruptSubsystem,
        InterruptSubsystemOutcome,
    )
    from framework.output_control import (
        InterruptOutcome,
        InterruptRequest,
        InterruptScope,
    )
    from framework.realtime_stage import RealtimeStageKind

    support = _load(
        "_fw_rt6_9a_control_b_test_support",
        "tests/test_interrupt_coordinator_control_b.py",
    )
    text_stage = support._BlockingStage(RealtimeStageKind.TEXT_GENERATION)
    voice_stage = support._BlockingStage(
        RealtimeStageKind.VOICE_OUTPUT,
        queue_supported=True,
        artifact_supported=True,
        pending_count=2,
        artifact_count=1,
    )
    session = framework.create_realtime_session(
        text_generation_stage=text_stage,
        voice_output_stage=voice_stage,
    )
    started, context = support._active_context(session, text="aggregate interrupt")
    text_thread, text_holder = support._start_stage(
        session,
        "text_generation",
        context,
        text_stage.started,
    )
    voice_thread, voice_holder = support._start_stage(
        session,
        "voice_output",
        context,
        voice_stage.started,
    )

    result = session.interrupt(
        InterruptRequest.user_barge_in(
            turn_id=started.turn_id,
            timeout_seconds=0.5,
        )
    )
    text_thread.join(timeout=3.0)
    voice_thread.join(timeout=3.0)

    _require(not text_thread.is_alive(), "text cancellation did not complete")
    _require(not voice_thread.is_alive(), "TTS cancellation did not complete")
    _require(text_holder == [None], "text late delivery was not suppressed")
    _require(voice_holder == [None], "TTS late delivery was not suppressed")
    _require(result.outcome is InterruptOutcome.ACCEPTED, "outer outcome drift")
    aggregate = result.coordination_result
    _require(aggregate is not None, "typed aggregate is missing")
    _require(
        aggregate.outcome is InterruptAggregateOutcome.PARTIAL,
        "mixed aggregate did not remain PARTIAL",
    )
    _require(
        tuple(item.subsystem for item in aggregate.subsystem_results)
        == tuple(InterruptSubsystem),
        "stable subsystem order drift",
    )
    _require(aggregate.completed_count == 4, "completed subsystem count drift")
    _require(aggregate.timed_out_count == 0, "unexpected aggregate timeout")
    _require(aggregate.timeout_seconds == 0.5, "request timeout projection drift")
    for subsystem in (
        InterruptSubsystem.TEXT_GENERATION,
        InterruptSubsystem.TTS_GENERATION,
        InterruptSubsystem.TTS_QUEUE,
        InterruptSubsystem.AUDIO_ARTIFACT,
    ):
        _require(
            _result_for(result, subsystem).outcome
            is InterruptSubsystemOutcome.COMPLETED,
            f"completed subsystem drift: {subsystem.value}",
        )
    _require(
        _result_for(result, InterruptSubsystem.MOTION).outcome
        is InterruptSubsystemOutcome.NOT_ACTIVE,
        "inactive motion was overclaimed",
    )
    _require(
        (text_stage.cancel_count, voice_stage.cancel_count) == (1, 1),
        "generation cancel reach drift",
    )
    _require(
        (voice_stage.clear_count, voice_stage.invalidate_count) == (1, 1),
        "queue/artifact reach drift",
    )
    _require(
        aggregate.public_metadata["whole_request_duplicate_ordering_deferred"],
        "FW-RT6-9b deferral drift",
    )
    _require(
        aggregate.public_metadata["barge_in_execution_deferred"],
        "FW-RT6-9c deferral drift",
    )
    _require(
        session.terminal_results[-1].outcome.value == "interrupted",
        "accepted aggregate did not commit the interrupted terminal",
    )
    _require(
        [event.type for event in session.event_history[-4:]]
        == [
            framework.RealtimeEventType.INTERRUPT_REQUESTED,
            framework.RealtimeEventType.INTERRUPT_ACCEPTED,
            framework.RealtimeEventType.INTERRUPT_COMPLETED,
            framework.RealtimeEventType.TURN_INTERRUPTED,
        ],
        "canonical interrupt terminal event order drift",
    )
    session.close()
    _require(
        (text_stage.close_count, voice_stage.close_count) == (1, 1),
        "stage close ownership drift",
    )
    print("[OK] aggregate reach, ordering, partial truth, and terminal facts conform")

    idle_stage = support._BlockingStage(RealtimeStageKind.TEXT_GENERATION)
    idle_session = framework.create_realtime_session(
        text_generation_stage=idle_stage
    )
    no_active = idle_session.interrupt(
        InterruptRequest(scope=InterruptScope.LLM_STREAM)
    )
    _require(
        no_active.outcome is InterruptOutcome.NO_ACTIVE_TURN,
        "no-active outer outcome drift",
    )
    _require(
        no_active.coordination_result.outcome
        is InterruptAggregateOutcome.NO_ACTIVE_TURN,
        "no-active aggregate outcome drift",
    )
    unknown = idle_session.interrupt(
        InterruptRequest(
            scope=InterruptScope.LLM_STREAM,
            turn_id=framework.TurnId.new(),
        )
    )
    _require(
        unknown.outcome is InterruptOutcome.NOT_IMPLEMENTED,
        "explicit unknown-turn compatibility drift",
    )
    _require(
        unknown.coordination_result.outcome
        is InterruptAggregateOutcome.NO_ACTIVE_TURN,
        "unknown target aggregate truth drift",
    )
    terminal_turn = idle_session.run_turn(input_text="terminal interrupt target")
    terminal = idle_session.interrupt(
        InterruptRequest(
            scope=InterruptScope.LLM_STREAM,
            turn_id=terminal_turn.turn_id,
        )
    )
    _require(
        terminal.outcome is InterruptOutcome.NO_ACTIVE_TURN,
        "terminal outer compatibility drift",
    )
    _require(
        terminal.coordination_result.outcome
        is InterruptAggregateOutcome.ALREADY_TERMINAL,
        "terminal aggregate outcome drift",
    )
    idle_session.close()
    closed = idle_session.interrupt(
        InterruptRequest(scope=InterruptScope.LLM_STREAM)
    )
    _require(
        closed.outcome is InterruptOutcome.ALREADY_CLOSED,
        "closed outer outcome drift",
    )
    _require(
        closed.coordination_result.outcome
        is InterruptAggregateOutcome.ALREADY_CLOSED,
        "closed aggregate outcome drift",
    )
    print("[OK] inactive, unknown, terminal, and closed projections conform")

    timeout_stage = support._BlockingStage(
        RealtimeStageKind.TEXT_GENERATION,
        release_on_cancel=False,
    )
    timeout_session = framework.create_realtime_session(
        text_generation_stage=timeout_stage
    )
    timeout_started, timeout_context = support._active_context(
        timeout_session,
        text="bounded timeout",
    )
    timeout_thread, timeout_holder = support._start_stage(
        timeout_session,
        "text_generation",
        timeout_context,
        timeout_stage.started,
    )
    timed_out = timeout_session.interrupt(
        InterruptRequest(
            scope=InterruptScope.LLM_STREAM,
            turn_id=timeout_started.turn_id,
            timeout_seconds=0.03,
        )
    )
    timeout_stage.release.set()
    timeout_thread.join(timeout=3.0)
    timeout_result = _result_for(
        timed_out,
        InterruptSubsystem.TEXT_GENERATION,
    )
    _require(timed_out.outcome is InterruptOutcome.FAILED, "timeout outer drift")
    _require(
        timed_out.coordination_result.outcome
        is InterruptAggregateOutcome.TIMED_OUT,
        "timeout aggregate drift",
    )
    _require(
        timeout_result.outcome is InterruptSubsystemOutcome.TIMED_OUT,
        "timeout subsystem drift",
    )
    _require(
        timeout_result.future_delivery_suppressed and timeout_holder == [None],
        "timeout late-delivery barrier drift",
    )
    timeout_session.close()
    print("[OK] bounded timeout and late-delivery suppression conform")


def check_public_compatibility() -> None:
    import framework
    import framework.interrupt_coordination as coordination
    from framework.interrupt_coordination import (
        InterruptAggregateOutcome,
        InterruptSubsystem,
        InterruptSubsystemOutcome,
    )

    _require(tuple(coordination.__all__) == EXPECTED_EXPLICIT_EXPORTS, "exports drift")
    _require(
        tuple(item.value for item in InterruptSubsystem) == EXPECTED_SUBSYSTEMS,
        "interrupt subsystem vocabulary drift",
    )
    _require(
        tuple(item.value for item in InterruptSubsystemOutcome)
        == EXPECTED_SUBSYSTEM_OUTCOMES,
        "subsystem outcome vocabulary drift",
    )
    _require(
        tuple(item.value for item in InterruptAggregateOutcome)
        == EXPECTED_AGGREGATE_OUTCOMES,
        "aggregate outcome vocabulary drift",
    )
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "create_realtime_session signature drift",
    )
    _require(
        not hasattr(framework, "InterruptAggregateResult"),
        "explicit coordination package leaked into root facade",
    )
    _require(len(framework.__all__) == 127, "framework root-public count drift")
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
    print("[OK] explicit package, public facade, versions, and isolation conform")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-9a — Interrupt coordinator")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 9 and section.count("- [ ]") == 0,
        "FW-RT6-9a must be 9 / 9 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-9a-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
    for marker in (
        "FW-RT6-9a tasks: 9 / 9 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "whole-request duplicate/race ordering changed: False",
        "barge-in decision/execution changed: False",
        "FW-RT6-9a final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-9b duplicate/race ordering: NOT_AUTHORIZED",
        "FW-RT6-9c barge-in execution: NOT_AUTHORIZED",
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
    print("[OK] nine FW-RT6-9a tasks close as aggregate acceptance-candidates")


def check_runtime_and_deferred_scope() -> None:
    runtime_prefixes = (
        "framework/",
        "core/",
        "llm/",
        "providers/",
        "stt/",
        "tts/",
        "vts/",
    )
    runtime = {
        path
        for path in _changed_paths()
        if path.startswith(runtime_prefixes)
    }
    _require(not runtime, f"Control C changed runtime sources: {sorted(runtime)!r}")
    print("[OK] Control C introduces no runtime source or FW-RT6-9b/9c change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_b()
    check_aggregate_runtime_contract()
    check_public_compatibility()
    check_docs_and_task_closure()
    if not args.source_only:
        check_runtime_and_deferred_scope()
    print("v600_rt6_9a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9a_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9a_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9a_control_c_exact_surface: 3 files")
    print("v600_rt6_9a_runtime_changed_by_control_c: False")
    print("v600_rt6_9a_task_count: 9 / 9 ACCEPTED-CANDIDATE")
    print("v600_rt6_9a_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_9b_status: NOT_AUTHORIZED")
    print("v600_rt6_9c_status: NOT_AUTHORIZED")
    print("v600_rt6_9a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9a Control C aggregate acceptance gate passed")


if __name__ == "__main__":
    main()
