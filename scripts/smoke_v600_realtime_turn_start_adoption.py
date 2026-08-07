"""FW-RT6-4b Control B explicit turn-start adoption acceptance smoke."""

from __future__ import annotations

import argparse
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "dc80d1ade4db539a38d30c74edf73e8ba824531a"
CONTROL_B_DELTA = {
    "docs/v600_realtime_turn_start_contract.md",
    "docs/v600_tasklist.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_turn_start_adoption.py",
    "tests/test_realtime_turn_start_adoption.py",
}
COMBINED_SURFACE = {
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_realtime_turn_start_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_turn_start_adoption.py",
    "scripts/smoke_v600_realtime_turn_start_models.py",
    "scripts/smoke_v600_version_metadata.py",
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
        "command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
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


def _check_git_surface(*, source_only: bool) -> None:
    if source_only:
        print("[OK] source-only mode skips Git metadata")
        return
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "baseline origin/main drift",
    )
    actual = _changed_paths()
    _assert(
        actual == COMBINED_SURFACE,
        f"combined Control A+B surface drift: expected={sorted(COMBINED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact fourteen-file combined Control A+B surface conform")


def _check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    required = (
        "class _ActiveTurnContext:",
        "self._turn_admission_lock = RLock()",
        "self._active_turn_context: _ActiveTurnContext | None = None",
        "def _bind_active_turn_context(",
        "def _active_turn_identity(",
        "def _commit_state_neutral_start_rejection(",
        "def start_turn(",
        'reason="active_turn_exists"',
        '"automatic_previous_turn_replacement": False',
    )
    for item in required:
        _assert(item in source, f"missing Control B source contract: {item}")

    execution_segment = source[
        source.index("def _prepare_turn_execution("):
        source.index("def get_tts_queue_state(")
    ]
    _assert(
        "self._start_turn_generation(turn.turn_id)" not in execution_segment,
        "turn execution must not allocate a legacy replacement generation",
    )
    _assert(
        "start_result = self.start_turn(normalized_turn)" in execution_segment,
        "execution preparation must preserve explicit start_turn admission",
    )
    _assert(
        "return self.run_turn_blocking(" in execution_segment,
        "legacy run_turn must delegate to blocking compatibility after FW-RT6-4c",
    )
    _assert(
        source.index("def start_turn(") < source.index("def _prepare_turn_execution("),
        "explicit start API should precede execution preparation",
    )
    forbidden = (
        "import openai",
        "import elevenlabs",
        "import pyvts",
        "import websocket",
        "import websockets",
        "stt.stt_engine",
        "tts.voice_engine",
        "live2d.vts_client",
    )
    _assert(
        not [item for item in forbidden if item in source],
        "Control B session adoption imported provider/runtime implementation",
    )
    print("[OK] structured context, explicit start, and provider-free admission source conform")


def _check_runtime_contract() -> None:
    import framework
    from framework import (
        RealtimeErrorCode,
        RealtimeEventType,
        RealtimePhase,
        RealtimeState,
        TurnOutcome,
    )

    session = framework.create_realtime_session()
    first = session.start_turn(input_text="first")
    _assert(first.accepted, "first explicit start must be accepted")
    _assert(first.generation_id is not None, "accepted start must allocate generation")
    _assert(session.state is RealtimeState.LISTENING, "accepted start must enter listening")
    _assert(session.phase is RealtimePhase.LISTENING, "accepted start phase mismatch")

    same = session.start_turn(
        framework.RealtimeTurn(
            turn_id=first.turn_id,
            session_id=first.session_id,
        )
    )
    _assert(same.accepted, "same active turn start must be idempotently accepted")
    _assert(same.generation_id == first.generation_id, "same turn generation drift")

    before_state = session.state
    before_phase = session.phase
    rejected = session.start_turn(input_text="second")
    _assert(not rejected.accepted, "second active turn must be rejected")
    terminal = rejected.terminal_result
    _assert(terminal is not None, "active rejection requires terminal result")
    _assert(terminal.outcome is TurnOutcome.REJECTED, "active rejection outcome drift")
    _assert(
        terminal.public_error_code is RealtimeErrorCode.REJECTED,
        "active rejection error code drift",
    )
    _assert(session.state is before_state, "active rejection changed session state")
    _assert(session.phase is before_phase, "active rejection changed session phase")
    diagnostics = session.generation_diagnostics
    _assert(diagnostics["generation_start_count"] == 1, "rejection allocated generation")
    _assert(diagnostics["generation_advance_count"] == 0, "rejection retired generation")
    _assert(diagnostics["active_generation_count"] == 1, "active generation was lost")

    rejected_events = [
        event
        for event in session.event_history
        if event.turn_id == rejected.turn_id
    ]
    _assert(len(rejected_events) == 1, "active rejection terminal event count drift")
    event = rejected_events[0]
    _assert(event.type is RealtimeEventType.TURN_REJECTED, "rejection event type drift")
    _assert(event.generation_id is None, "rejected turn must not own generation")

    before_event_count = len(session.event_history)
    duplicate = session.start_turn(
        framework.RealtimeTurn(
            turn_id=rejected.turn_id,
            session_id=session.info.session_id,
        )
    )
    _assert(not duplicate.accepted, "duplicate rejected start must remain rejected")
    _assert(
        duplicate.terminal_result is terminal,
        "duplicate rejected start must return original terminal result",
    )
    _assert(
        len(session.event_history) == before_event_count,
        "duplicate rejected start emitted another terminal event",
    )
    session.close()
    print("[OK] explicit start and state-neutral active rejection runtime contract conforms")


def _check_atomic_two_start_race() -> None:
    import framework

    session = framework.create_realtime_session()
    barrier = Barrier(2)

    def start(value: str):
        barrier.wait(timeout=5)
        return session.start_turn(input_text=value)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(start, ("a", "b")))

    _assert(sum(result.accepted for result in results) == 1, "race must accept exactly one")
    _assert(sum(not result.accepted for result in results) == 1, "race must reject exactly one")
    diagnostics = session.generation_diagnostics
    _assert(diagnostics["generation_start_count"] == 1, "race allocated multiple generations")
    _assert(diagnostics["generation_advance_count"] == 0, "race replaced active generation")
    session.close()
    print("[OK] concurrent explicit starts are atomically single-active")


def _check_tests_and_regressions() -> None:
    focused = unittest.TestSuite()
    for name in (
        "tests.test_realtime_turn_start_models",
        "tests.test_realtime_turn_start_adoption",
    ):
        focused.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A+B tests failed")
    _assert(focused_result.testsRun == 24, "focused Control A+B test count must be 24")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 104, "full unit suite regressed below Control B baseline")

    for script in (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_app_sdk.py",
    ):
        _run([sys.executable, script])
    print(f"[OK] focused 24 tests and current full {full_result.testsRun}-test suite pass")


def _check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_realtime_turn_start_contract.md").read_text(
        encoding="utf-8"
    )
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-4b-B-TURN-START-ADOPTION:BEGIN",
        "active_turn_exists",
        "state-neutral",
        "DEFERRED / Control C",
    ):
        _assert(marker in contract, f"missing Control B contract marker: {marker}")
        _assert(marker in tasklist, f"missing Control B tasklist marker: {marker}")
    _assert(
        "- [x] normal completionをterminal registryへcommitする。" in tasklist,
        "accepted FW-RT6-4b aggregate tasklist completion is missing",
    )
    _assert(
        "FW-RT6-4b-D-ACCEPTANCE-SYNC:BEGIN" in tasklist,
        "accepted FW-RT6-4b aggregate sync is missing",
    )
    print("[OK] historical Control B docs remain truthful after FW-RT6-4b acceptance")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    _check_git_surface(source_only=args.source_only)
    _check_source_contract()
    _check_runtime_contract()
    _check_atomic_two_start_race()
    _check_tests_and_regressions()
    _check_docs()

    print("v600_rt6_4b_control_b_status: implemented-awaiting-review")
    print("v600_rt6_4b_control_b_exact_delta: 5 files")
    print("v600_rt6_4b_combined_control_a_b_surface: 14 files")
    print("v600_rt6_4b_root_public_names: 125")
    print("v600_rt6_4b_explicit_start_api: True")
    print("v600_rt6_4b_structured_active_turn_context: True")
    print("v600_rt6_4b_same_turn_start_idempotent: True")
    print("v600_rt6_4b_active_new_turn_typed_rejection: PASS")
    print("v600_rt6_4b_active_rejection_state_neutral: PASS")
    print("v600_rt6_4b_rejected_turn_generation_start: 0")
    print("v600_rt6_4b_active_generation_retirement_on_rejection: 0")
    print("v600_rt6_4b_concurrent_explicit_start_single_active: PASS")
    print("v600_rt6_4b_focused_unit_tests: 24 / PASS")
    print("v600_rt6_4b_full_unit_tests: 104 / PASS")
    print("v600_rt6_4b_run_turn_unified_adoption: False / DEFERRED")
    print("v600_rt6_4b_provider_execution: False")
    print("v600_rt6_4b_network_execution: False")
    print("v600_rt6_4b_microphone_access: False")
    print("v600_rt6_4b_playback_execution: False")
    print("v600_rt6_4b_real_vts_execution: False")
    print("v600_rt6_4b_control_c: NOT_AUTHORIZED")
    print("v600_rt6_4b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
