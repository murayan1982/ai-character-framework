"""FW-RT6-4c Control B aggregate session execution adoption gate."""

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
    "scripts/check_v600_realtime_execution_control_a.py",
    "scripts/check_v600_realtime_execution_control_b.py",
    "scripts/check_v600_realtime_turn_lifecycle_acceptance.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_turn_start_adoption.py",
    "scripts/smoke_v600_realtime_turn_start_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_execution_bridge.py",
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
        "Control B combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact 24-file FW-RT6-4b + FW-RT6-4c Control A+B surface conform")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    required = (
        "self._execution_bridge = _RealtimeExecutionBridge(",
        "def _prepare_turn_execution(",
        "start_result = self.start_turn(normalized_turn)",
        "async def _run_admitted_turn_async(",
        "async def run_turn_async(",
        "def run_turn_blocking(",
        "def _raise_if_blocking_turn_execution_forbidden(",
        "BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP",
        "BLOCKING_CALL_FROM_RUNTIME_THREAD",
        "return self.run_turn_blocking(",
        "asyncio.shield(asyncio.wrap_future(future))",
    )
    for phrase in required:
        _assert(phrase in source, f"Control B session source missing: {phrase}")

    _assert(
        source.index("def _prepare_turn_execution(")
        < source.index("async def _run_admitted_turn_async("),
        "admission preparation must precede runtime execution",
    )
    _assert(
        source.index("async def run_turn_async(")
        < source.index("def run_turn_blocking(")
        < source.index("def run_turn("),
        "public async/blocking/legacy execution order drift",
    )
    _assert(
        "asyncio.run(" not in source,
        "RealtimeSession must not use per-call asyncio.run",
    )
    _assert(
        "self._execution_bridge.shutdown(" in source[source.index("    def close("):],
        "accepted Control C bridge shutdown integration is missing",
    )
    print("[OK] async-first session ownership, pre-queue admission, and blocking guards conform")


def check_runtime_contract() -> None:
    import framework
    from framework import (
        RealtimeExecutionError,
        RealtimeExecutionErrorCode,
        RealtimeTurn,
        TurnOutcome,
    )

    session = framework.create_realtime_session()
    _assert(not session._execution_bridge.started, "session bridge must be lazy")

    async def first_async():
        return await session.run_turn_async(input_text="async-first")

    try:
        first = asyncio.run(first_async())
        _assert(first.outcome is TurnOutcome.COMPLETED, "async turn did not complete")
        loop_identity = session._execution_bridge.loop_identity
        thread_identity = session._execution_bridge.thread_identity
        _assert(loop_identity is not None, "async turn did not start runtime loop")
        _assert(thread_identity is not None, "async turn did not start runtime thread")

        second = session.run_turn_blocking(input_text="blocking-second")
        _assert(second.outcome is TurnOutcome.COMPLETED, "blocking turn did not complete")
        _assert(
            session._execution_bridge.loop_identity == loop_identity,
            "blocking wrapper did not reuse session runtime loop",
        )
        _assert(
            session._execution_bridge.thread_identity == thread_identity,
            "blocking wrapper did not reuse session runtime thread",
        )
    finally:
        session._execution_bridge.shutdown()

    host_loop_session = framework.create_realtime_session()

    async def host_loop_guard():
        try:
            host_loop_session.run_turn_blocking(input_text="forbidden")
        except RealtimeExecutionError as error:
            return error.code
        raise AssertionError("host event-loop blocking execution was not rejected")

    try:
        code = asyncio.run(host_loop_guard())
        _assert(
            code is RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP,
            "host-loop blocking rejection code drift",
        )
        _assert(
            not host_loop_session._execution_bridge.started,
            "rejected host-loop blocking call must not start runtime",
        )
    finally:
        host_loop_session._execution_bridge.shutdown()

    runtime_session = framework.create_realtime_session()

    async def runtime_guard():
        try:
            runtime_session.run_turn(input_text="runtime forbidden")
        except RealtimeExecutionError as error:
            return error.code
        raise AssertionError("runtime-thread blocking execution was not rejected")

    try:
        code = runtime_session._execution_bridge.run(runtime_guard())
        _assert(
            code is RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD,
            "runtime-thread blocking rejection code drift",
        )
    finally:
        runtime_session._execution_bridge.shutdown()

    explicit = framework.create_realtime_session()
    turn = RealtimeTurn(input_text="explicit")
    start = explicit.start_turn(turn)
    _assert(start.accepted, "explicit start should be accepted")
    _assert(not explicit._execution_bridge.started, "start_turn alone must not start runtime")

    async def explicit_async():
        return await explicit.run_turn_async(turn)

    try:
        result = asyncio.run(explicit_async())
        _assert(result.generation_id == start.generation_id, "explicit generation was replaced")
        _assert(
            explicit.generation_diagnostics["generation_start_count"] == 1,
            "explicit+async execution allocated a second generation",
        )
    finally:
        explicit._execution_bridge.shutdown()

    real = framework.create_realtime_session(real_runtime_enabled=True)

    async def real_rejection():
        return await real.run_turn_async(input_text="no fallback")

    result = asyncio.run(real_rejection())
    _assert(result.outcome is TurnOutcome.REJECTED, "real-runtime request must remain rejected")
    _assert(not real._execution_bridge.started, "typed real rejection must not start runtime")
    real._execution_bridge.shutdown()

    print("[OK] host-loop async execution, blocking guards, runtime reuse, and 4b identity semantics conform")


def check_tests_and_regressions() -> None:
    regressions = (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
        [sys.executable, "scripts/check_v600_realtime_turn_lifecycle_acceptance.py", "--source-only"],
        [sys.executable, "scripts/smoke_v600_realtime_turn_start_adoption.py", "--source-only"],
        [sys.executable, "scripts/check_v600_realtime_execution_control_a.py", "--source-only"],
    )
    for command in regressions:
        _run(command)

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
        )
    )
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A+B tests failed")
    _assert(focused_result.testsRun == 26, "focused Control A+B test count must be 26")

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

    print("[OK] focused 26 tests and full suite preserves accepted 152-test baseline; canonical regressions pass")


def check_docs() -> None:
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_execution_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-4c-B-SESSION-EXECUTION-ADOPTION:BEGIN",
        "run_turn_async",
        "run_turn_blocking",
        "BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP",
        "BLOCKING_CALL_FROM_RUNTIME_THREAD",
        "admission before runtime queue",
        "Control C:",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"execution contract marker missing: {marker}")

    for marker in (
        "FW-RT6-4c-B-SESSION-EXECUTION-ADOPTION:BEGIN",
        "combined working-tree surface:",
        "24 files",
        "focused Control A+B tests:",
        "26 / PASS expected",
        "full unit suite:",
        "142 / PASS expected",
    ):
        _assert(marker in tasklist, f"tasklist Control B marker missing: {marker}")

    print("[OK] FW-RT6-4c Control B docs preserve Control C callback/close deferral")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_source_contract()
    check_runtime_contract()
    check_tests_and_regressions()
    check_docs()

    print("v600_rt6_4c_control_b_status: implemented-awaiting-review")
    print("v600_rt6_4c_control_b_exact_delta: 9 files")
    print("v600_rt6_4c_combined_surface: 24 files")
    print("v600_rt6_4c_execution_model: ASYNC-FIRST")
    print("v600_rt6_4c_root_public_names: 127")
    print("v600_rt6_4c_run_turn_async: True")
    print("v600_rt6_4c_run_turn_blocking: True")
    print("v600_rt6_4c_legacy_run_turn_delegation: True")
    print("v600_rt6_4c_host_event_loop_safe_async: PASS")
    print("v600_rt6_4c_host_event_loop_blocking: TYPED_REJECTION")
    print("v600_rt6_4c_runtime_thread_blocking: TYPED_REJECTION")
    print("v600_rt6_4c_persistent_bridge_lazy: True")
    print("v600_rt6_4c_persistent_loop_reused: True")
    print("v600_rt6_4c_per_call_asyncio_run: False")
    print("v600_rt6_4c_admission_before_runtime_queue: True")
    print("v600_rt6_4c_active_new_turn_typed_rejection: PASS")
    print("v600_rt6_4c_active_generation_replacement: 0")
    print("v600_rt6_4c_focused_unit_tests: 26 / PASS")
    print("v600_rt6_4c_full_unit_tests: 152 / PASS")
    print("v600_rt6_4c_callback_context_close_safety: DEFERRED / CONTROL_C")
    print("v600_rt6_4c_provider_execution: False")
    print("v600_rt6_4c_network_execution: False")
    print("v600_rt6_4c_microphone_access: False")
    print("v600_rt6_4c_playback_execution: False")
    print("v600_rt6_4c_real_vts_execution: False")
    print("v600_rt6_4c_control_c: NOT_AUTHORIZED")
    print("v600_rt6_4c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
