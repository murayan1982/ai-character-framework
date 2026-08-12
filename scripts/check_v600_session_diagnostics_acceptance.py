"""FW-RT6-10c Control C aggregate public diagnostics acceptance gate.

The gate uses deterministic in-memory sessions only.  It performs no provider,
network, audio, microphone, playback, or real VTube Studio operation.
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import inspect
import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "0427a5446cad52706d10396f2a91ba207eef2911"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_session_diagnostics_acceptance.py",
    "tests/test_session_diagnostics_control_b.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "SessionTerminalSnapshot",
    "SessionDiagnosticsSnapshot",
    "build_session_terminal_snapshot",
    "build_session_diagnostics_snapshot",
)
EXPECTED_SESSION_FIELDS = (
    "session_id",
    "state",
    "phase",
    "is_closed",
    "active_turn_id",
    "active_generation_id",
    "queue_depth",
    "active_generation_count",
    "last_terminal_result",
    "last_safe_error_code",
    "stale_completion_count",
    "duplicate_terminal_count",
    "overflow_count",
)
EXPECTED_TERMINAL_FIELDS = (
    "session_id",
    "turn_id",
    "generation_id",
    "outcome",
    "public_error_code",
    "retryable",
    "recovery_action",
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
EXPECTED_TASKS = (
    "session snapshotを追加する。",
    "current phaseを追加する。",
    "active turn/generationを追加する。",
    "queue depthを追加する。",
    "active generation countを追加する。",
    "last terminal resultを追加する。",
    "last safe error codeを追加する。",
    "stale/duplicate/overflow countを追加する。",
    "private payload/text/audio/pathを含めない。",
)
EXPECTED_CONTROL_A_TESTS = (
    "test_explicit_exports_are_exact_and_root_surface_is_unchanged",
    "test_terminal_projection_discards_private_rich_result_values",
    "test_active_snapshot_requires_one_paired_context",
    "test_last_terminal_and_safe_error_are_projected_and_consistent",
    "test_snapshot_is_frozen_slotted_and_as_dict_is_primitive_only",
)
EXPECTED_CONTROL_B_TESTS = (
    "test_property_is_read_only_and_root_import_remains_lazy",
    "test_active_snapshot_uses_generation_gate_identity",
    "test_terminal_event_callback_observes_no_retired_active_generation",
    "test_stale_count_reuses_generation_gate_diagnostics",
    "test_duplicate_count_reuses_terminal_registry_diagnostics",
    "test_overflow_count_reuses_event_hub_diagnostics",
    "test_inverted_existing_lock_contention_does_not_deadlock",
    "test_versions_and_provider_isolation_remain_after_aggregate_acceptance",
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
    print("[OK] baseline and exact four-file corrective FW-RT6-10c Control C surface conform")


def check_accepted_controls_and_lazy_root() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_diagnostics' not in sys.modules; "
        "assert hasattr(framework.RealtimeSession, 'diagnostics_snapshot'); "
        "assert not hasattr(framework, 'SessionDiagnosticsSnapshot'); "
        "assert len(framework.__all__) == 127"
    )
    _run([sys.executable, "-c", code])

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-10c-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10c-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-10c-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10c-B-ACCEPTANCE-SYNC:END",
    ):
        _require(tasklist.count(marker) == 1, f"accepted sync marker drift: {marker}")
    for phrase in (
        "Control A implementation: 53023cca67f0865f6454a311517889fdf26f91ab",
        "Control A acceptance sync: 3566ed618161b1212fb1a193cb4e27f663303863",
        "Control B implementation: ba1c193f1d90e632d727b4f2697302f5f99d167d",
        "Control B acceptance sync: 0427a5446cad52706d10396f2a91ba207eef2911",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted Control A/B fact missing: {phrase}")

    control_a_source = (
        PROJECT_ROOT / "tests/test_session_diagnostics_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_source = (
        PROJECT_ROOT / "tests/test_session_diagnostics_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_source.count("    def test_") == 12, "Control A test count drift")
    _require(control_b_source.count("    def test_") == 13, "Control B test count drift")
    for name in EXPECTED_CONTROL_A_TESTS:
        _require(f"def {name}(" in control_a_source, f"Control A test missing: {name}")
    for name in EXPECTED_CONTROL_B_TESTS:
        _require(f"def {name}(" in control_b_source, f"Control B test missing: {name}")

    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_session_diagnostics_control_a",
            "tests.test_session_diagnostics_control_b",
        ],
        capture=False,
    )
    print("[OK] root import stays lazy and diagnostics names remain explicit-only")
    print("[OK] accepted Control A+B public diagnostics regressions conform")


def check_model_and_runtime_observation() -> None:
    import framework
    import framework.session_diagnostics as diagnostics
    from framework.lifecycle import RealtimePhase, TurnOutcome
    from framework.output_control import TTSQueueState
    from framework.realtime import (
        RealtimeErrorCode,
        RealtimeEventType,
        RealtimeState,
        RealtimeTurn,
    )
    from framework.realtime_generation_gate import RealtimeStageCompletionEnvelope
    from framework.session_diagnostics import (
        SessionDiagnosticsSnapshot,
        SessionTerminalSnapshot,
        build_session_diagnostics_snapshot,
    )

    _require(
        tuple(diagnostics.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "explicit diagnostics exports drift",
    )
    _require(
        tuple(field.name for field in fields(SessionDiagnosticsSnapshot))
        == EXPECTED_SESSION_FIELDS,
        "session snapshot fields drift",
    )
    _require(
        tuple(field.name for field in fields(SessionTerminalSnapshot))
        == EXPECTED_TERMINAL_FIELDS,
        "terminal snapshot fields drift",
    )
    descriptor = inspect.getattr_static(framework.RealtimeSession, "diagnostics_snapshot")
    _require(isinstance(descriptor, property), "diagnostics_snapshot stopped being a property")
    _require(descriptor.fset is None, "diagnostics_snapshot became writable")

    session = framework.create_realtime_session()
    idle = session.diagnostics_snapshot
    another_idle = session.diagnostics_snapshot
    _require(idle is not another_idle and idle == another_idle, "snapshot is not fresh")
    _require(idle.state is RealtimeState.IDLE, "idle state drift")
    _require(idle.phase is RealtimePhase.IDLE, "idle phase drift")
    _require(idle.active_generation_count == 0, "idle generation count drift")
    _require(idle.last_terminal_result is None, "idle terminal appeared")
    _require(idle.last_safe_error_code is RealtimeErrorCode.NONE, "idle safe error drift")
    try:
        idle.queue_depth = 1  # type: ignore[misc]
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("snapshot became mutable")

    observed: list[SessionDiagnosticsSnapshot] = []

    def callback(event) -> None:
        if event.type is RealtimeEventType.SESSION_CLOSED:
            observed.append(session.diagnostics_snapshot)

    session.on_event(callback)
    started = session.start_turn(input_text="private-aggregate-input")
    active = session.diagnostics_snapshot
    _require(started.accepted, "turn admission failed")
    _require(active.active_turn_id == started.turn_id, "active turn drift")
    _require(active.active_generation_id == started.generation_id, "active generation drift")
    _require(active.active_generation_count == 1, "active count drift")
    session.close()
    closed = session.diagnostics_snapshot
    _require(len(observed) == 1, "final callback diagnostics count drift")
    _require(observed[0].active_turn_id is None, "callback retained retired turn")
    _require(closed.state is RealtimeState.CLOSED and closed.is_closed, "closed state drift")
    _require(closed.active_generation_count == 0, "closed generation remained active")
    _require(closed.last_terminal_result is not None, "closed terminal disappeared")
    _require(closed.last_terminal_result.outcome is TurnOutcome.CLOSED, "close outcome drift")
    _require(
        closed.last_safe_error_code is RealtimeErrorCode.SESSION_CLOSED,
        "closed safe error drift",
    )
    _require(
        "private-aggregate-input" not in json.dumps(closed.as_dict(), sort_keys=True),
        "private input escaped diagnostics projection",
    )

    legacy = framework.create_realtime_session()
    legacy_turn_id = "legacy-host-turn"
    legacy.start_turn(
        RealtimeTurn(
            session_id=legacy.info.session_id,
            turn_id=legacy_turn_id,
            input_text="private-legacy-input",
        )
    )
    _require(
        legacy.diagnostics_snapshot.active_turn_id == legacy_turn_id,
        "legacy active turn compatibility drift",
    )
    legacy.close()
    _require(
        legacy.diagnostics_snapshot.last_terminal_result.turn_id == legacy_turn_id,
        "legacy terminal compatibility drift",
    )
    legacy_model = build_session_diagnostics_snapshot(
        session_id="legacy-host-session",
        state=RealtimeState.IDLE,
        phase=RealtimePhase.IDLE,
        is_closed=False,
    )
    _require(legacy_model.session_id == "legacy-host-session", "legacy session ID drift")

    queue = framework.create_realtime_session()
    queue.get_tts_queue_state = lambda: TTSQueueState(  # type: ignore[method-assign]
        queued_count=6,
        current_item_id="private-queue-item",
        safe_message="private-queue-message",
        public_metadata={"provider_payload": "private-queue-payload"},
    )
    queue_snapshot = queue.diagnostics_snapshot
    queue_json = json.dumps(queue_snapshot.as_dict(), sort_keys=True)
    _require(queue_snapshot.queue_depth == 6, "queue depth drift")
    _require("private-queue" not in queue_json, "queue private value escaped")

    stale_session = framework.create_realtime_session()
    stale_started = stale_session.start_turn(input_text="private-stale-input")
    stale_session.cancel_current_turn()
    delivered: list[str] = []
    stale = stale_session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=stale_started.turn_id,
            generation_id=stale_started.generation_id,
            stage="diagnostics-aggregate-stale",
            value="private-stale-value",
        ),
        deliver=delivered.append,
    )
    _require(not stale.accepted and not delivered, "stale completion crossed delivery")
    _require(
        stale_session.diagnostics_snapshot.stale_completion_count == 1,
        "stale count owner drift",
    )

    duplicate_session = framework.create_realtime_session()
    duplicate_session.start_turn(input_text="private-duplicate-input")
    duplicate_session.close()
    record = duplicate_session._terminal_registry.records[-1]
    duplicate = duplicate_session._terminal_registry.commit(
        record.turn_id,
        record.outcome,
        recovery_action=record.recovery_action,
        reason=record.reason,
        result=record.result,
    )
    _require(not duplicate.accepted, "duplicate terminal was accepted")
    _require(
        duplicate_session.diagnostics_snapshot.duplicate_terminal_count == 1,
        "duplicate count owner drift",
    )

    overflow_session = framework.create_realtime_session()
    for _ in range(70):
        overflow_session.emit_created()
    _require(
        overflow_session.diagnostics_snapshot.overflow_count
        == overflow_session.event_diagnostics["history_overflow_count"]
        > 0,
        "overflow count owner drift",
    )

    getter_source = inspect.getsource(descriptor.fget)
    _require(
        "_generation_gate.current_turn_id" in getter_source,
        "generation gate stopped owning active identity",
    )
    _require(
        "_active_turn_identity" not in getter_source,
        "temporary compatibility context became diagnostics owner",
    )
    read_source = inspect.getsource(
        framework.RealtimeSession._diagnostics_snapshot_read_section
    )
    _require("blocking=False" in read_source, "non-blocking lock retry disappeared")
    _require("time.sleep(0)" in read_source, "lock retry stopped yielding")
    print("[OK] immutable model and idle/active/terminal/closed observations conform")
    print("[OK] generation, queue, terminal, stale, duplicate, and overflow owners conform")
    print("[OK] legacy compatibility, reentrant reads, lock progress, and privacy conform")


def check_public_boundaries_and_task_closure() -> None:
    import framework

    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-10c-C-PUBLIC-DIAGNOSTICS-ACCEPTANCE:BEGIN",
        "FW-RT6-10c-C-PUBLIC-DIAGNOSTICS-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public contract marker drift: {marker}")
    for marker in (
        "FW-RT6-10c-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-10c-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")
    for phrase in (
        "exact corrective Control C surface: 4 files",
        "explicit diagnostics exports: 4 / UNCHANGED",
        "public property: RealtimeSession.diagnostics_snapshot / READ_ONLY",
        "new diagnostics lock/thread/registry/execution owner: False / PASS",
        "private-rich runtime value retained: False / PASS",
        "runtime source changed by Control C: False",
        "existing Control B test semantic sync: 1 file / TASK BOUNDARY ONLY",
        "FW-RT6-10c tasks: 9 / 9 ACCEPTED-CANDIDATE",
        "FW-RT6-10c final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-10d: NOT_AUTHORIZED",
        "Control C commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in facade or phrase in tasklist, f"aggregate phrase missing: {phrase}")

    section = tasklist.split("## FW-RT6-10c — Public diagnostics", 1)[1].split(
        "## FW-RT6-10d", 1
    )[0]
    _require(section.count("- [x]") == 9, "FW-RT6-10c accepted-candidate count drift")
    _require(section.count("- [ ]") == 0, "FW-RT6-10c task remains open")
    for task in EXPECTED_TASKS:
        _require(task in section, f"FW-RT6-10c task missing: {task}")

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
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "realtime factory signature drift",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice", "openai"):
        _require(module_name not in sys.modules, f"provider/runtime module escaped: {module_name}")
    print("[OK] root-public, factory, version, and provider-isolation boundaries conform")
    print("[OK] Control C introduces no runtime or FW-RT6-10d change")
    print("[OK] one existing Control B test receives task-boundary-only semantic sync")
    print("[OK] nine FW-RT6-10c tasks close as aggregate acceptance-candidates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_controls_and_lazy_root()
    check_model_and_runtime_observation()
    check_public_boundaries_and_task_closure()

    print("v600_rt6_10c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10c_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10c_control_c_exact_surface: 4 files / CORRECTIVE")
    print("v600_rt6_10c_runtime_changed_by_control_c: False")
    print("v600_rt6_10c_existing_test_semantic_sync: 1 file / TASK_BOUNDARY_ONLY")
    print("v600_rt6_10c_explicit_exports: 4 / PASS")
    print("v600_rt6_10c_runtime_property: diagnostics_snapshot / READ_ONLY")
    print("v600_rt6_10c_active_identity_owner: RealtimeGenerationGate / REUSED")
    print("v600_rt6_10c_terminal_owner: RealtimeTerminalRegistry / REUSED")
    print("v600_rt6_10c_overflow_owner: RealtimeEventHub / REUSED")
    print("v600_rt6_10c_new_lock_thread_registry: False / PASS")
    print("v600_rt6_10c_legacy_host_ids: PRESERVED / PASS")
    print("v600_rt6_10c_private_payload_retained: False / PASS")
    print("v600_rt6_10c_task_count: 9 / 9 ACCEPTED-CANDIDATE")
    print("v600_rt6_10c_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_10d: NOT_AUTHORIZED")
    print("v600_rt6_10c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10c Control C aggregate public diagnostics gate passed")


if __name__ == "__main__":
    main()
