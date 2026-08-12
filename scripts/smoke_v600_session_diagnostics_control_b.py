"""FW-RT6-10c Control B coherent realtime diagnostics runtime gate."""

from __future__ import annotations

import argparse
import inspect
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "3566ed618161b1212fb1a193cb4e27f663303863"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime_session.py",
    "framework/session_diagnostics.py",
    "scripts/smoke_v600_session_diagnostics_control_b.py",
    "tests/test_session_diagnostics_control_a.py",
    "tests/test_session_diagnostics_control_b.py",
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
        "unexpected FW-RT6-10c Control B baseline",
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
    print("[OK] baseline and exact seven-file FW-RT6-10c Control B surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_diagnostics' not in sys.modules; "
        "assert hasattr(framework.RealtimeSession, 'diagnostics_snapshot'); "
        "assert not hasattr(framework, 'SessionDiagnosticsSnapshot'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import stays lazy while the session property is public")


def check_runtime_contract() -> None:
    _run(
        "-m",
        "unittest",
        "tests.test_session_diagnostics_control_a",
        "tests.test_session_diagnostics_control_b",
    )

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.output_control import TTSQueueState
    from framework.realtime import RealtimeErrorCode, RealtimeState, RealtimeTurn
    from framework.session_diagnostics import SessionDiagnosticsSnapshot

    idle_session = framework.create_realtime_session()
    idle = idle_session.diagnostics_snapshot
    _require(isinstance(idle, SessionDiagnosticsSnapshot), "snapshot type drifted")
    _require(idle.state is RealtimeState.IDLE, "idle state drifted")
    _require(idle.active_generation_count == 0, "idle generation count drifted")
    _require(idle.last_terminal_result is None, "idle terminal appeared")
    _require(
        idle.last_safe_error_code is RealtimeErrorCode.NONE,
        "idle safe error drifted",
    )

    started = idle_session.start_turn(input_text="private-gate-input")
    active = idle_session.diagnostics_snapshot
    _require(started.accepted, "turn admission failed")
    _require(active.active_turn_id == started.turn_id, "active turn drifted")
    _require(
        active.active_generation_id == started.generation_id,
        "active generation drifted",
    )
    _require(active.active_generation_count == 1, "active count drifted")
    idle_session.close()
    closed = idle_session.diagnostics_snapshot
    _require(closed.is_closed, "closed snapshot remained open")
    _require(closed.state is RealtimeState.CLOSED, "closed state drifted")
    _require(closed.active_turn_id is None, "closed turn remained active")
    _require(closed.active_generation_count == 0, "closed generation remained active")
    _require(closed.last_terminal_result is not None, "closed terminal disappeared")
    _require(
        closed.last_safe_error_code is RealtimeErrorCode.SESSION_CLOSED,
        "closed safe error drifted",
    )
    _require(
        "private-gate-input" not in json.dumps(closed.as_dict(), sort_keys=True),
        "private input escaped diagnostics projection",
    )

    legacy_session = framework.create_realtime_session()
    legacy_id = "legacy-host-turn"
    legacy_session.start_turn(
        RealtimeTurn(
            session_id=legacy_session.info.session_id,
            turn_id=legacy_id,
            input_text="private-legacy-input",
        )
    )
    _require(
        legacy_session.diagnostics_snapshot.active_turn_id == legacy_id,
        "legacy active turn compatibility regressed",
    )
    legacy_session.close()
    legacy_terminal = legacy_session.diagnostics_snapshot.last_terminal_result
    _require(
        legacy_terminal is not None and legacy_terminal.turn_id == legacy_id,
        "legacy terminal compatibility regressed",
    )

    queue_session = framework.create_realtime_session()
    queue_session.get_tts_queue_state = lambda: TTSQueueState(  # type: ignore[method-assign]
        queued_count=4,
        current_item_id="private-queue-item",
        safe_message="private-queue-message",
        public_metadata={"provider_payload": "private-queue-payload"},
    )
    queue_snapshot = queue_session.diagnostics_snapshot
    queue_rendered = json.dumps(queue_snapshot.as_dict(), sort_keys=True)
    _require(queue_snapshot.queue_depth == 4, "queue depth drifted")
    _require("private-queue" not in queue_rendered, "queue private value escaped")

    getter = framework.RealtimeSession.diagnostics_snapshot.fget
    _require(getter is not None, "diagnostics property getter disappeared")
    getter_source = inspect.getsource(getter)
    _require(
        "_generation_gate.current_turn_id" in getter_source,
        "generation gate stopped owning active turn diagnostics",
    )
    _require(
        "_active_turn_identity" not in getter_source,
        "temporary compatibility context became diagnostics owner",
    )
    read_source = inspect.getsource(
        framework.RealtimeSession._diagnostics_snapshot_read_section
    )
    _require("blocking=False" in read_source, "deadlock-safe lock retry disappeared")
    _require("time.sleep(0)" in read_source, "lock retry stopped yielding")

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

    print("[OK] idle, active, terminal, closed, queue, and legacy snapshots conform")
    print("[OK] generation, terminal, and event owners remain authoritative")
    print("[OK] reentrant and inverted-lock diagnostics reads remain deadlock-safe")
    print("[OK] diagnostics retain no private-rich runtime value")
    print("[OK] root-public and API-version contracts remain unchanged")


def check_docs_and_task_boundary() -> None:
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-10c-B-PUBLIC-DIAGNOSTICS:BEGIN" in text,
            f"Control B contract missing from {relative}",
        )
        _require(
            "FW-RT6-10c aggregate tasks: 0 / 9 CLOSED" in text,
            f"aggregate boundary missing from {relative}",
        )
        _require(
            "Control C" in text and "NOT_AUTHORIZED" in text,
            f"Control C boundary missing from {relative}",
        )
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-10c — Public diagnostics", 1)[1].split(
        "## FW-RT6-10d", 1
    )[0]
    _require(section.count("- [ ]") == 9, "FW-RT6-10c task count drifted")
    _require(section.count("- [x]") == 0, "Control B closed aggregate tasks")
    control_a_test = (
        PROJECT_ROOT / "tests/test_session_diagnostics_control_a.py"
    ).read_text(encoding="utf-8")
    _require(
        "def test_control_a_remains_provider_free_after_runtime_adoption" in control_a_test,
        "Control A runtime-adoption test semantic sync disappeared",
    )
    _require(
        'hasattr(framework.RealtimeSession, "diagnostics_snapshot")' not in control_a_test,
        "obsolete Control A property-absence assertion remains",
    )
    print("[OK] documentation, Control A test sync, and 0 / 9 task boundary conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="skip baseline and worktree-surface checks",
    )
    args = parser.parse_args()
    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_runtime_contract()
    check_docs_and_task_boundary()
    print("v600_rt6_10c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10c_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10c_control_b_exact_surface: 7 files / CORRECTIVE")
    print("v600_rt6_10c_runtime_property: diagnostics_snapshot / READ_ONLY")
    print("v600_rt6_10c_active_identity_owner: RealtimeGenerationGate / REUSED")
    print("v600_rt6_10c_terminal_owner: RealtimeTerminalRegistry / REUSED")
    print("v600_rt6_10c_overflow_owner: RealtimeEventHub / REUSED")
    print("v600_rt6_10c_new_lock_thread_registry: False")
    print("v600_rt6_10c_legacy_host_ids: PRESERVED / PASS")
    print("v600_rt6_10c_private_payload_retained: False / PASS")
    print("v600_rt6_10c_task_count: 0 / 9 CLOSED")
    print("v600_rt6_10c_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10c Control B coherent public diagnostics gate passed")


if __name__ == "__main__":
    main()
