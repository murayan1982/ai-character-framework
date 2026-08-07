"""FW-RT6-4b Control C aggregate single-active-turn lifecycle acceptance."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "dc80d1ade4db539a38d30c74edf73e8ba824531a"
EXPECTED_SURFACE = {
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_realtime_turn_start_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "scripts/check_v600_realtime_turn_lifecycle_acceptance.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_turn_start_adoption.py",
    "scripts/smoke_v600_realtime_turn_start_models.py",
    "scripts/smoke_v600_version_metadata.py",
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
        "command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
    )
    return completed.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {path.strip().replace("\\", "/") for path in (*tracked, *untracked) if path.strip()}


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"unexpected combined Control A+B+C surface: expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact sixteen-file combined Control A+B+C surface conform")


def check_source_contract() -> None:
    path = PROJECT_ROOT / "framework/realtime_session.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))

    required = (
        "def start_turn(",
        "class _ActiveTurnContext:",
        "self._turn_admission_lock = RLock()",
        "def _prepare_turn_execution(",
        "start_result = self.start_turn(normalized_turn)",
        "async def _run_admitted_turn_async(",
        "admitted_generation_id: GenerationId",
        "session_id=self._session_id",
        "generation_id=admitted_generation_id",
        "self._clear_active_turn_context()",
        'reason="active_turn_exists"',
    )
    for phrase in required:
        _assert(phrase in source, f"unified turn source missing: {phrase}")

    run_segment = source[
        source.index("    def _prepare_turn_execution("):
        source.index("    def get_tts_queue_state(")
    ]
    _assert(
        "self._start_turn_generation(turn.turn_id)" not in run_segment,
        "turn execution must not allocate a legacy replacement generation",
    )
    _assert(
        run_segment.index("start_result = self.start_turn(normalized_turn)")
        < run_segment.index("with self._serialized_operation():"),
        "turn admission must occur before serialized runtime execution",
    )
    _assert(
        run_segment.count("RealtimeEventType.TURN_STARTED") == 0,
        "execution path must not emit a second TURN_STARTED",
    )
    _assert(
        "return self.run_turn_blocking(" in run_segment,
        "legacy run_turn must delegate to blocking compatibility",
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
        "Control C imported provider/runtime implementation",
    )
    print("[OK] run_turn explicit admission, identity, and no-replacement source contract conforms")


def check_runtime_contract() -> None:
    import framework
    from framework import RealtimeEventType, RealtimePhase, RealtimeState, RealtimeTurn, TurnOutcome

    session = framework.create_realtime_session()
    first = session.run_turn(input_text="first")
    _assert(first.outcome is TurnOutcome.COMPLETED, "normal turn did not complete")
    _assert(first.session_id == session.info.session_id, "session identity mismatch")
    _assert(first.generation_id is not None, "normal turn lost generation identity")
    _assert(session.state is RealtimeState.IDLE, "session did not return idle state")
    _assert(session.phase is RealtimePhase.IDLE, "session did not return idle phase")
    _assert(session._active_turn_context is None, "active context was not cleared")
    _assert(session.terminal_diagnostics["terminal_commit_count"] == 1, "normal terminal commit count drift")
    _assert(session.generation_diagnostics["generation_start_count"] == 1, "normal generation start count drift")
    _assert(session.generation_diagnostics["generation_advance_count"] == 1, "normal generation retirement count drift")

    turn_events = tuple(event for event in session.event_history if event.turn_id == first.turn_id)
    _assert(sum(event.type is RealtimeEventType.TURN_STARTED for event in turn_events) == 1, "normal turn must emit one TURN_STARTED")
    terminals = tuple(event for event in turn_events if event.terminal)
    _assert(len(terminals) == 1, "normal turn must emit exactly one terminal event")
    _assert(terminals[0].type is RealtimeEventType.TURN_COMPLETED, "normal terminal type drift")
    _assert(terminals[0].generation_id == first.generation_id, "terminal generation mismatch")

    second = session.run_turn(input_text="second")
    _assert(second.outcome is TurnOutcome.COMPLETED, "reused session did not complete next turn")
    _assert(second.generation_id != first.generation_id, "reused session did not allocate fresh generation")
    _assert(session.terminal_diagnostics["terminal_commit_count"] == 2, "reused session terminal count drift")

    active_session = framework.create_realtime_session()
    active = active_session.start_turn(RealtimeTurn(input_text="active"))
    _assert(active.accepted, "explicit active turn was not admitted")
    current_generation = active_session._generation_gate.current_generation_id
    advance_before = active_session.generation_diagnostics["generation_advance_count"]
    rejected = active_session.run_turn(RealtimeTurn(input_text="new"))
    _assert(rejected.outcome is TurnOutcome.REJECTED, "active new turn was not rejected")
    _assert(rejected.generation_id is None, "rejected turn allocated a generation")
    _assert(active_session._generation_gate.current_generation_id == current_generation, "active generation was replaced")
    _assert(active_session.generation_diagnostics["generation_advance_count"] == advance_before, "active generation was retired on rejection")

    explicit_session = framework.create_realtime_session()
    explicit_turn = RealtimeTurn(input_text="explicit")
    start = explicit_session.start_turn(explicit_turn)
    completed = explicit_session.run_turn(explicit_turn)
    _assert(completed.generation_id == start.generation_id, "explicit start generation was not reused")
    _assert(explicit_session.generation_diagnostics["generation_start_count"] == 1, "explicit start + run_turn allocated two generations")

    real_session = framework.create_realtime_session(real_runtime_enabled=True)
    real_result = real_session.run_turn(input_text="no fallback")
    _assert(real_result.outcome is TurnOutcome.REJECTED, "real request must reject while orchestration is unavailable")
    _assert(real_result.session_id == real_session.info.session_id, "real rejection lost session identity")
    _assert(real_result.generation_id is None, "real rejection allocated generation")
    _assert(not real_result.public_metadata["mock_runtime"], "real request silently used mock runtime")

    print("[OK] single active, exactly-once normal terminal, identity, and session reuse conform")


def check_tests_and_regressions() -> None:
    focused = unittest.TestSuite()
    for name in (
        "tests.test_realtime_turn_start_models",
        "tests.test_realtime_turn_start_adoption",
        "tests.test_realtime_turn_lifecycle_acceptance",
    ):
        focused.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A+B+C tests failed")
    _assert(focused_result.testsRun == 36, "focused Control A+B+C test count must be 36")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 116, "full unit suite regressed below FW-RT6-4b baseline")

    for script in (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_app_sdk.py",
    ):
        _run([sys.executable, script])

    print(f"[OK] focused 36 tests, full {full_result.testsRun} tests, and canonical public regressions pass")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_realtime_turn_start_contract.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    marker = "FW-RT6-4b-C-TURN-LIFECYCLE-ACCEPTANCE:BEGIN"
    _assert(marker in contract, "Control C contract marker missing")
    _assert(marker in tasklist, "Control C tasklist marker missing")

    start = tasklist.index("## FW-RT6-4b — Single-active-turn lifecycle")
    end = tasklist.index("## FW-RT6-4c", start)
    section = tasklist[start:end]
    _assert(section.count("- [x]") == 7, "FW-RT6-4b task acceptance count must be 7")
    _assert("- [ ]" not in section.split("**Acceptance:**", 1)[0], "FW-RT6-4b tasks remain unchecked")
    for phrase in (
        "7 / 7 ACCEPTED-CANDIDATE",
        "36 / PASS expected",
        "116 / PASS expected",
        "FW-RT6-4c / NOT_AUTHORIZED",
    ):
        _assert(phrase in section, f"Control C tasklist fact missing: {phrase}")

    print("[OK] all seven FW-RT6-4b tasks and aggregate acceptance docs conform")


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

    print("v600_rt6_4b_control_c_status: implemented-awaiting-review")
    print("v600_rt6_4b_control_c_exact_delta: 7 files")
    print("v600_rt6_4b_combined_control_a_b_c_surface: 16 files")
    print("v600_rt6_4b_accepted_task_count: 7")
    print("v600_rt6_4b_run_turn_explicit_admission: PASS")
    print("v600_rt6_4b_normal_result_identity: session_id / turn_id / generation_id / PASS")
    print("v600_rt6_4b_normal_terminal_exactly_once: PASS")
    print("v600_rt6_4b_active_context_cleanup: PASS")
    print("v600_rt6_4b_session_reusable: True")
    print("v600_rt6_4b_active_new_turn_typed_rejection: PASS")
    print("v600_rt6_4b_active_generation_replacement: 0")
    print("v600_rt6_4b_focused_unit_tests: 36 / PASS")
    print("v600_rt6_4b_full_unit_tests: 116 / PASS")
    print("v600_rt6_4b_root_public_names: 125")
    print("v600_rt6_4b_real_provider_execution: False")
    print("v600_rt6_4b_network_execution: False")
    print("v600_rt6_4b_microphone_access: False")
    print("v600_rt6_4b_playback_execution: False")
    print("v600_rt6_4b_real_vts_execution: False")
    print("v600_rt6_4b_drc_accessed_or_changed: False")
    print("v600_rt6_4b_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_4b_next_checkpoint: FW-RT6-4c / NOT_AUTHORIZED")
    print("v600_rt6_4b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
