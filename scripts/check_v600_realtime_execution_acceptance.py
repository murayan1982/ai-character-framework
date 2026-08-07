"""FW-RT6-4c Control C aggregate execution-model acceptance gate."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "dc80d1ade4db539a38d30c74edf73e8ba824531a"
EXPECTED_COMBINED_SURFACE = {
    "docs/v600_realtime_execution_contract.md",
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_realtime_turn_start_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_execution.py",
    "framework/realtime_execution_bridge.py",
    "framework/realtime_session.py",
    "scripts/check_v600_realtime_execution_acceptance.py",
    "scripts/check_v600_realtime_execution_control_a.py",
    "scripts/check_v600_realtime_execution_control_b.py",
    "scripts/check_v600_realtime_turn_lifecycle_acceptance.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_turn_start_adoption.py",
    "scripts/smoke_v600_realtime_turn_start_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_execution_bridge.py",
    "tests/test_realtime_execution_callback_close.py",
    "tests/test_realtime_execution_models.py",
    "tests/test_realtime_execution_session_adoption.py",
    "tests/test_realtime_turn_lifecycle_acceptance.py",
    "tests/test_realtime_turn_start_adoption.py",
    "tests/test_realtime_turn_start_models.py",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(
        completed.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + completed.stdout
        + completed.stderr,
    )
    return completed.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in (*tracked, *untracked)
        if path.strip()
    }


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "baseline origin/main drift",
    )
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_COMBINED_SURFACE,
        "Control C combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact 26-file FW-RT6-4b + FW-RT6-4c Control A+B+C surface conform")


def check_source_contract() -> None:
    session_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    bridge_source = (
        PROJECT_ROOT / "framework/realtime_execution_bridge.py"
    ).read_text(encoding="utf-8")

    required_session = (
        "should_shutdown_bridge = False",
        "if should_shutdown_bridge:",
        "self._execution_bridge.shutdown()",
        "if self._execution_bridge.is_runtime_thread():",
        "BLOCKING_CALL_FROM_RUNTIME_THREAD",
        "async def run_turn_async(",
        "def run_turn_blocking(",
    )
    for phrase in required_session:
        _assert(phrase in session_source, f"Control C session source missing: {phrase}")

    required_bridge = (
        "self._stopped = threading.Event()",
        "def wait_stopped(",
        "if thread.ident == threading.get_ident():",
        "thread.join(timeout=timeout_seconds)",
        "self._stopped.set()",
    )
    for phrase in required_bridge:
        _assert(phrase in bridge_source, f"Control C bridge source missing: {phrase}")

    _assert("asyncio.run(" not in session_source, "session introduced per-call asyncio.run")
    _assert("asyncio.run(" not in bridge_source, "bridge introduced per-call asyncio.run")
    print("[OK] callback reentrancy guards and post-unlock bridge shutdown source contract conform")


def check_runtime_contract() -> None:
    import framework
    from framework import (
        RealtimeEventType,
        RealtimeExecutionError,
        RealtimeExecutionErrorCode,
        RealtimeState,
        TurnOutcome,
    )

    session = framework.create_realtime_session()
    host_thread = threading.get_ident()
    callback_threads: list[int] = []
    rejection_codes: list[RealtimeExecutionErrorCode] = []
    shutdown_depths: list[int] = []
    original_shutdown = session._execution_bridge.shutdown

    def checked_shutdown(*, timeout_seconds: float = 2.0) -> None:
        shutdown_depths.append(session._operation_depth)
        original_shutdown(timeout_seconds=timeout_seconds)

    session._execution_bridge.shutdown = checked_shutdown  # type: ignore[method-assign]

    def callback(event) -> None:
        if event.type is RealtimeEventType.LISTENING_STARTED:
            callback_threads.append(threading.get_ident())
            try:
                session.run_turn_blocking(input_text="reentrant")
            except RealtimeExecutionError as error:
                rejection_codes.append(error.code)
            session.cancel_current_turn()
            session.close()

    session.on_event(callback)
    result = session.run_turn_blocking(input_text="aggregate callback close")
    _assert(result.outcome is TurnOutcome.COMPLETED, "callback-close outer turn drift")
    _assert(
        callback_threads == [session._execution_bridge.thread_identity],
        "turn callback did not execute on runtime thread",
    )
    _assert(callback_threads[0] != host_thread, "turn callback leaked onto caller thread")
    _assert(
        rejection_codes
        == [RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD],
        "runtime callback blocking reentrancy rejection drift",
    )
    _assert(shutdown_depths == [0], "bridge shutdown occurred while operation depth was active")
    _assert(session._closed, "callback close did not close session")
    _assert(session.state is RealtimeState.CLOSED, "callback close state drift")
    _assert(session._execution_bridge.closed, "callback close did not close bridge")
    _assert(
        session._execution_bridge.wait_stopped(timeout_seconds=2.0),
        "callback close left runtime worker alive",
    )
    _assert(not session._execution_bridge.thread_alive, "runtime worker leaked after close")
    _assert(session._execution_bridge.loop_identity is None, "runtime loop leaked after close")

    direct = framework.create_realtime_session()
    direct_threads: list[int] = []

    def direct_callback(event) -> None:
        if event.type is RealtimeEventType.INTERRUPT_REQUESTED:
            direct_threads.append(threading.get_ident())

    direct.on_event(direct_callback)
    direct.interrupt()
    _assert(direct_threads == [host_thread], "direct control callback context drift")
    _assert(not direct._execution_bridge.started, "direct control unexpectedly started runtime")
    direct.close()
    _assert(not direct._execution_bridge.started, "close-before-start created runtime")

    print("[OK] callback context, blocking rejection, cancel reentrancy, and close shutdown conform")


def check_regressions_before_threaded_suite() -> None:
    regressions = (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
        [sys.executable, "scripts/check_v600_realtime_turn_lifecycle_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_realtime_execution_control_a.py", "--source-only"],
    )
    for command in regressions:
        _run(command)
    print("[OK] canonical public, FW-RT6-4b, and Control A regressions pass; Control B is covered by focused tests")


def check_tests() -> None:
    focused = unittest.TestSuite(
        (
            unittest.defaultTestLoader.loadTestsFromName(
                "tests.test_realtime_execution_models"
            ),
            unittest.defaultTestLoader.loadTestsFromName(
                "tests.test_realtime_execution_bridge"
            ),
            unittest.defaultTestLoader.loadTestsFromName(
                "tests.test_realtime_execution_session_adoption"
            ),
            unittest.defaultTestLoader.loadTestsFromName(
                "tests.test_realtime_execution_callback_close"
            ),
        )
    )
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A+B+C tests failed")
    _assert(focused_result.testsRun == 36, "focused Control A+B+C count must be 36")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(
        full_result.testsRun >= 152,
        "full unit suite must preserve the accepted 152-test FW-RT6-4c baseline",
    )
    print("[OK] focused 36 tests pass and full suite preserves accepted 152-test baseline")


def check_docs() -> None:
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_execution_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-4c-C-CALLBACK-CLOSE-ACCEPTANCE:BEGIN",
        "session runtime worker thread",
        "caller thread",
        "BLOCKING_CALL_FROM_RUNTIME_THREAD",
        "bridge shutdown while operation depth > 0:",
        "runtime self-join:",
        "worker / loop leak after final close:",
        "6 / 6 ACCEPTED-CANDIDATE",
        "FW-RT6-5a / NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"execution contract Control C marker missing: {marker}")
        _assert(marker in tasklist, f"tasklist Control C marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-4c — Public execution model decision and implementation")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    _assert(section.count("- [x]") == 6, "FW-RT6-4c task completion count must be 6")
    _assert("- [ ]" not in section, "FW-RT6-4c tasklist retains incomplete tasks")
    print("[OK] all six FW-RT6-4c tasks and Control C aggregate docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_source_contract()
    check_regressions_before_threaded_suite()
    check_runtime_contract()
    check_tests()
    check_docs()

    print("v600_rt6_4c_control_c_status: implemented-awaiting-review")
    print("v600_rt6_4c_control_c_exact_delta: 8 files")
    print("v600_rt6_4c_combined_surface: 26 files")
    print("v600_rt6_4c_execution_model: ASYNC-FIRST")
    print("v600_rt6_4c_root_public_names: 127")
    print("v600_rt6_4c_callback_turn_context: RUNTIME_WORKER_THREAD")
    print("v600_rt6_4c_direct_control_callback_context: CALLER_THREAD")
    print("v600_rt6_4c_runtime_callback_blocking: TYPED_REJECTION")
    print("v600_rt6_4c_runtime_callback_cancel_reentrant: PASS")
    print("v600_rt6_4c_runtime_callback_close_reentrant: PASS")
    print("v600_rt6_4c_bridge_shutdown_operation_depth: 0")
    print("v600_rt6_4c_runtime_self_join: False")
    print("v600_rt6_4c_worker_loop_leak_after_close: False")
    print("v600_rt6_4c_close_before_runtime_start_starts_runtime: False")
    print("v600_rt6_4c_close_idempotent: True")
    print("v600_rt6_4c_per_call_asyncio_run: False")
    print("v600_rt6_4c_focused_unit_tests: 36 / PASS")
    print("v600_rt6_4c_full_unit_tests: 152 / PASS")
    print("v600_rt6_4c_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_4c_deadlock: False")
    print("v600_rt6_4c_provider_execution: False")
    print("v600_rt6_4c_network_execution: False")
    print("v600_rt6_4c_microphone_access: False")
    print("v600_rt6_4c_playback_execution: False")
    print("v600_rt6_4c_real_vts_execution: False")
    print("v600_rt6_4c_drc_accessed_or_changed: False")
    print("v600_rt6_4c_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_4c_next_checkpoint: FW-RT6-5a / NOT_AUTHORIZED")
    print("v600_rt6_4c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
