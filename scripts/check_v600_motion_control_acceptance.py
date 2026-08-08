"""FW-RT6-8c Control C aggregate motion-control acceptance gate.

The gate uses only deterministic mock sessions and injected in-memory motion
stages.  It imports no provider SDK and performs no network, audio, microphone,
VTube Studio, or real motion operation.
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

EXPECTED_HEAD = "b1710ba1398cbbaf982d0fa436f41ba43d707e96"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_motion_control_acceptance.py",
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
EXPECTED_CONTROL_OUTCOMES = (
    "requested",
    "completed",
    "not_active",
    "already_terminal",
    "unsupported",
    "timed_out",
    "already_closed",
    "failed",
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
    print("[OK] baseline and exact three-file FW-RT6-8c Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_b = _load(
        "_fw_rt6_8c_control_b_for_aggregate",
        "scripts/smoke_v600_motion_control_control_b.py",
    )
    control_b.check_runtime_contract()
    control_b.check_source_contract()
    control_b.check_docs()
    print("[OK] accepted Control A+B motion-control regressions conform")


def check_aggregate_runtime_contract() -> None:
    import framework
    from framework.motion_control import MotionControlOutcome, MotionControlResult
    from framework.output_control import (
        InterruptOutcome,
        InterruptRequest,
        InterruptScope,
    )

    support = _load(
        "_fw_rt6_8c_control_b_test_support",
        "tests/test_motion_control_control_b.py",
    )
    stage = support._ControllableMotionStage(stop_supported=True)
    session, started, turn_thread = support._start_blocked_turn(stage)
    result = session.interrupt(
        InterruptRequest.user_barge_in(turn_id=started.turn_id)
    )
    turn_thread.join(timeout=3.0)

    _require(not turn_thread.is_alive(), "accepted cancellation did not finish motion")
    _require(
        result.outcome is InterruptOutcome.NO_ACTIVE_TURN,
        "motion reach changed the established aggregate interrupt outcome",
    )
    _require(
        isinstance(result.motion_result, MotionControlResult),
        "aggregate result lost typed motion reach",
    )
    motion = result.motion_result
    _require(
        motion.outcome is MotionControlOutcome.COMPLETED,
        "active motion control did not complete",
    )
    _require(
        motion.turn_id == started.turn_id
        and motion.generation_id == started.generation_id,
        "motion-control correlation drift",
    )
    _require(
        motion.cancel_requested
        and motion.cancel_accepted
        and motion.cancel_completed
        and motion.future_delivery_suppressed,
        "cancel request/accept/complete/barrier facts drift",
    )
    _require(
        motion.stop_motion_requested
        and motion.stop_motion_supported
        and motion.stop_motion_applied,
        "validated provider-neutral stop facts drift",
    )
    _require(
        motion.public_metadata["whole_turn_aggregate_changed"] is False,
        "motion result overclaimed whole-turn aggregation",
    )
    _require(
        stage.cancel_count == 1 and stage.stop_count == 1,
        "single active work did not execute cancel/stop exactly once",
    )
    motion_events = [
        event.type
        for event in session.event_history
        if event.boundary == "motion"
    ]
    _require(
        motion_events
        == [
            framework.RealtimeEventType.MOTION_REQUESTED,
            framework.RealtimeEventType.MOTION_STARTED,
        ],
        "accepted cancel delivered a late motion terminal event",
    )
    session.close()
    _require(stage.close_count == 1, "motion stage close ownership drift")

    inactive = framework.create_realtime_session()
    no_active = inactive.interrupt(
        InterruptRequest(scope=InterruptScope.MOTION)
    )
    _require(
        no_active.outcome is InterruptOutcome.NO_ACTIVE_TURN,
        "no-active aggregate outcome drift",
    )
    _require(
        no_active.motion_result is not None
        and no_active.motion_result.outcome is MotionControlOutcome.NOT_ACTIVE,
        "no-active motion outcome drift",
    )

    completed_turn = inactive.run_turn(input_text="aggregate terminal")
    terminal = inactive.interrupt(
        InterruptRequest(
            scope=InterruptScope.MOTION,
            turn_id=completed_turn.turn_id,
        )
    )
    _require(
        terminal.motion_result is not None
        and terminal.motion_result.outcome
        is MotionControlOutcome.ALREADY_TERMINAL,
        "terminal motion outcome drift",
    )
    inactive.close()
    closed = inactive.interrupt(
        InterruptRequest(scope=InterruptScope.MOTION)
    )
    _require(
        closed.outcome is InterruptOutcome.ALREADY_CLOSED,
        "closed aggregate outcome drift",
    )
    _require(
        closed.motion_result is not None
        and closed.motion_result.outcome is MotionControlOutcome.ALREADY_CLOSED,
        "closed motion outcome drift",
    )
    print("[OK] aggregate motion reach, terminal facts, and late barrier conform")


def check_public_compatibility() -> None:
    import framework
    from framework.motion_control import MotionControlOutcome

    _require(
        tuple(item.value for item in MotionControlOutcome)
        == EXPECTED_CONTROL_OUTCOMES,
        "motion-control outcome vocabulary drift",
    )
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "create_realtime_session signature drift",
    )
    _require(
        not hasattr(framework.RealtimeSession, "cancel_motion"),
        "RealtimeSession gained an unreviewed cancel_motion method",
    )
    _require(
        not hasattr(framework.MotionSession, "cancel_motion"),
        "standalone MotionSession public contract drift",
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
    print("[OK] public factory, root, versions, and provider isolation conform")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-8c — Motion cancel/clear capability")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 5 and section.count("- [ ]") == 0,
        "FW-RT6-8c must be 5 / 5 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-8c-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
    for marker in (
        "FW-RT6-8c tasks: 5 / 5 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "aggregate InterruptResult outcome changed: False",
        "FW-RT6-8c final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-9a aggregate interrupt: NOT_AUTHORIZED",
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
    print("[OK] five FW-RT6-8c tasks close as aggregate acceptance-candidates")


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
    print("[OK] Control C introduces no runtime source or FW-RT6-9a change")


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
    print("v600_rt6_8c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8c_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_8c_control_c_exact_surface: 3 files")
    print("v600_rt6_8c_runtime_changed_by_control_c: False")
    print("v600_rt6_8c_aggregate_interrupt_changed: False")
    print("v600_rt6_8c_task_count: 5 / 5 ACCEPTED-CANDIDATE")
    print("v600_rt6_8c_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_9a_status: NOT_AUTHORIZED")
    print("v600_rt6_8c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-8c Control C aggregate acceptance gate passed")


if __name__ == "__main__":
    main()
