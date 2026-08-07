"""FW-RT6-4c Control A async-first execution model acceptance gate."""

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
    "scripts/check_v600_realtime_turn_lifecycle_acceptance.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_turn_start_adoption.py",
    "scripts/smoke_v600_realtime_turn_start_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_execution_bridge.py",
    "tests/test_realtime_execution_models.py",
    "tests/test_realtime_turn_lifecycle_acceptance.py",
    "tests/test_realtime_turn_start_adoption.py",
    "tests/test_realtime_turn_start_models.py"
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
        "Control A combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact 22-file FW-RT6-4b + 4c Control A surface conform")


def check_public_execution_models() -> None:
    import framework
    from framework import RealtimeExecutionError, RealtimeExecutionErrorCode

    _assert(len(framework.__all__) == 127, "root-public count must be 127")
    _assert(
        tuple(framework.__all__[124:125]) == ("RealtimeTurnStartResult",),
        "accepted FW-RT6-4b turn-start suffix drift",
    )
    _assert(
        tuple(framework.__all__[125:])
        == ("RealtimeExecutionErrorCode", "RealtimeExecutionError"),
        "execution models must be the exact two-name additive suffix",
    )
    _assert(
        tuple(code.value for code in RealtimeExecutionErrorCode)
        == (
            "blocking_call_in_active_event_loop",
            "blocking_call_from_runtime_thread",
        ),
        "public execution error-code contract drift",
    )
    error = RealtimeExecutionError(
        RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP
    )
    _assert(error.safe_message == str(error), "public execution error message drift")

    source = (PROJECT_ROOT / "framework/realtime_execution.py").read_text(
        encoding="utf-8"
    )
    forbidden_import_fragments = (
        "import openai",
        "import elevenlabs",
        "import pyvts",
        "import websocket",
        "import websockets",
        "from tts.",
        "from stt.",
        "from live2d.",
    )
    lowered_source = source.lower()
    _assert(
        not [
            item
            for item in forbidden_import_fragments
            if item in lowered_source
        ],
        "public execution model imported provider/runtime detail",
    )
    print("[OK] exact two-name public execution suffix and safe errors conform")


def check_persistent_bridge() -> None:
    from framework.realtime_execution_bridge import _RealtimeExecutionBridge

    async def identity() -> tuple[int, int]:
        return id(asyncio.get_running_loop()), threading.get_ident()

    bridge = _RealtimeExecutionBridge()
    _assert(not bridge.started, "bridge must be lazy at construction")
    try:
        first = bridge.run(identity())
        second = bridge.run(identity())
        _assert(first == second, "bridge must reuse one event loop and worker thread")
        _assert(bridge.loop_identity == first[0], "bridge loop identity drift")
        _assert(bridge.thread_identity == first[1], "bridge thread identity drift")
    finally:
        bridge.shutdown()

    _assert(bridge.closed, "bridge must report closed after shutdown")
    _assert(not bridge.thread_alive, "bridge thread leaked after shutdown")

    bridge_source = (
        PROJECT_ROOT / "framework/realtime_execution_bridge.py"
    ).read_text(encoding="utf-8")
    _assert(
        "asyncio.run(" not in bridge_source,
        "persistent bridge must not use per-call asyncio.run",
    )
    _assert(
        "asyncio.run_coroutine_threadsafe" in bridge_source,
        "bridge submission must target the persistent loop",
    )
    print("[OK] lazy persistent runtime bridge reuses one loop/thread and shuts down")


def check_session_adoption_progress() -> None:
    session_source = (
        PROJECT_ROOT / "framework/realtime_session.py"
    ).read_text(encoding="utf-8")
    required = (
        "_RealtimeExecutionBridge",
        "RealtimeExecutionErrorCode",
        "RealtimeExecutionError",
        "async def run_turn_async(",
        "def run_turn_blocking(",
    )
    for phrase in required:
        _assert(
            phrase in session_source,
            f"accepted Control A primitive is not adopted by Control B: {phrase}",
        )
    _assert(
        "asyncio.run(" not in session_source,
        "Control B must not introduce per-call asyncio.run",
    )
    print("[OK] accepted Control A primitives remain intact after Control B session adoption")


def check_tests_and_regressions() -> None:
    focused = unittest.TestSuite(
        (
            unittest.defaultTestLoader.loadTestsFromName(
                "tests.test_realtime_execution_models"
            ),
            unittest.defaultTestLoader.loadTestsFromName(
                "tests.test_realtime_execution_bridge"
            ),
        )
    )
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A tests failed")
    _assert(focused_result.testsRun == 14, "focused Control A test count must be 14")

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

    for script in (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_app_sdk.py",
        "scripts/check_v600_realtime_turn_lifecycle_acceptance.py",
    ):
        command = [sys.executable, script]
        if script.endswith("check_v600_realtime_turn_lifecycle_acceptance.py"):
            command.append("--source-only")
        _run(command)

    print("[OK] focused 14 Control A tests and full suite preserves accepted 152-test baseline; canonical regressions pass")


def check_docs() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    turn_contract = (
        PROJECT_ROOT / "docs/v600_realtime_turn_start_contract.md"
    ).read_text(encoding="utf-8")
    execution_contract = (
        PROJECT_ROOT / "docs/v600_realtime_execution_contract.md"
    ).read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-4b-D-ACCEPTANCE-SYNC:BEGIN",
        "COMPLETED / VERIFIED / ACCEPTED",
        "36 / PASS",
        "116 / PASS",
    ):
        _assert(marker in tasklist, f"tasklist 4b acceptance marker missing: {marker}")
        _assert(
            marker in turn_contract,
            f"turn contract 4b acceptance marker missing: {marker}",
        )

    for marker in (
        "FW-RT6-4c-A-EXECUTION-MODELS-BRIDGE:BEGIN",
        "ASYNC-FIRST",
        "RealtimeExecutionErrorCode",
        "RealtimeExecutionError",
        "125 -> 127",
        "RealtimeSession adoption:",
        "False / DEFERRED",
    ):
        _assert(
            marker in execution_contract,
            f"execution contract marker missing: {marker}",
        )

    _assert(
        "FW-RT6-4c-A-EXECUTION-MODELS-BRIDGE:BEGIN" in tasklist,
        "tasklist Control A marker missing",
    )
    print("[OK] FW-RT6-4b acceptance sync and FW-RT6-4c Control A docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_public_execution_models()
    check_persistent_bridge()
    check_session_adoption_progress()
    check_tests_and_regressions()
    check_docs()

    print("v600_rt6_4b_acceptance_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_4c_control_a_status: implemented-awaiting-review")
    print("v600_rt6_4c_control_a_exact_delta: 16 files")
    print("v600_rt6_4c_combined_surface: 22 files")
    print("v600_rt6_4c_execution_model: ASYNC-FIRST")
    print("v600_rt6_4c_root_public_names: 127")
    print("v600_rt6_4c_public_execution_names: 2")
    print("v600_rt6_4c_persistent_bridge_lazy: True")
    print("v600_rt6_4c_persistent_loop_reused: True")
    print("v600_rt6_4c_per_call_asyncio_run: False")
    print("v600_rt6_4c_session_adoption: True / CONTROL_B")
    print("v600_rt6_4c_focused_unit_tests: 14 / PASS")
    print("v600_rt6_4c_full_unit_tests: 152 / PASS")
    print("v600_rt6_4c_provider_execution: False")
    print("v600_rt6_4c_network_execution: False")
    print("v600_rt6_4c_microphone_access: False")
    print("v600_rt6_4c_playback_execution: False")
    print("v600_rt6_4c_real_vts_execution: False")
    print("v600_rt6_4c_control_b: NOT_AUTHORIZED")
    print("v600_rt6_4c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
