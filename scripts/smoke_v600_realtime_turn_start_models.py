"""FW-RT6-4b Control A public turn-start model acceptance smoke."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "dc80d1ade4db539a38d30c74edf73e8ba824531a"
EXPECTED_PATHS = {
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_realtime_turn_start_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_turn_start_models.py",
    "scripts/smoke_v600_version_metadata.py",
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


def _check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "baseline origin/main drift",
    )
    actual_paths = _changed_paths()
    _assert(
        actual_paths == EXPECTED_PATHS,
        "Control A exact surface drift; "
        f"expected={sorted(EXPECTED_PATHS)!r}; actual={sorted(actual_paths)!r}",
    )
    print("[OK] baseline and exact eleven-file closure + Control A surface conform")


def _check_public_models() -> None:
    import framework
    from framework import (
        GenerationId,
        RealtimePhase,
        RealtimeTurnResult,
        RealtimeTurnStartResult,
        SessionId,
        TurnId,
        TurnOutcome,
    )

    _assert(len(framework.__all__) == 125, "root-public count must be 125")
    _assert(
        tuple(framework.__all__[121:124])
        == (
            "RealtimeSessionConfig",
            "RealtimeSessionConstructionStatus",
            "RealtimeSessionConstructionResult",
        ),
        "accepted construction suffix drift",
    )
    _assert(
        tuple(framework.__all__[124:]) == ("RealtimeTurnStartResult",),
        "turn-start model must be the one-name additive suffix",
    )

    session_id = SessionId.new()
    turn_id = TurnId.new()
    generation_id = GenerationId.new()

    accepted = RealtimeTurnStartResult(
        accepted=True,
        session_id=session_id,
        turn_id=turn_id,
        generation_id=generation_id,
        phase=RealtimePhase.LISTENING,
    )
    _assert(accepted.generation_id == generation_id, "accepted generation mismatch")

    terminal = RealtimeTurnResult.rejected(
        turn_id=turn_id,
        session_id=session_id,
    )
    rejected = RealtimeTurnStartResult(
        accepted=False,
        session_id=session_id,
        turn_id=turn_id,
        generation_id=None,
        phase=RealtimePhase.LISTENING,
        terminal_result=terminal,
    )
    _assert(rejected.terminal_result is terminal, "rejected terminal mismatch")
    _assert(terminal.outcome is TurnOutcome.REJECTED, "terminal outcome mismatch")

    source = (PROJECT_ROOT / "framework/realtime.py").read_text(encoding="utf-8")
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
        not [name for name in forbidden if name in source],
        "turn-start public models imported provider/runtime implementation",
    )
    print("[OK] additive result identities and turn-start public model conform")


def _check_runtime_adoption_deferred() -> None:
    session_source = (
        PROJECT_ROOT / "framework/realtime_session.py"
    ).read_text(encoding="utf-8")
    _assert(
        "def start_turn(" not in session_source,
        "Control B start_turn adoption must remain deferred",
    )
    _assert(
        "_ActiveTurnContext" not in session_source,
        "Control B active-turn context must remain deferred",
    )
    print("[OK] start_turn runtime adoption and active context remain deferred")


def _check_tests_and_regressions() -> None:
    focused = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_turn_start_models"
    )
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A tests failed")
    _assert(focused_result.testsRun == 10, "focused test count must be 10")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun == 90, "full unit suite must contain 90 tests")

    for script in (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_app_sdk.py",
    ):
        _run([sys.executable, script])

    print("[OK] focused 10 tests, full 90 tests, and canonical public regressions pass")


def _check_docs() -> None:
    construction = (
        PROJECT_ROOT / "docs/v600_realtime_session_construction_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_turn_start_contract.md"
    ).read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-4a-D-CLOSURE-SYNC:BEGIN",
        "dc80d1ade4db539a38d30c74edf73e8ba824531a",
        "COMPLETED / VERIFIED / COMMITTED / PUSHED / ACCEPTED / CLOSED",
    ):
        _assert(marker in construction, f"missing 4a closure marker: {marker}")
        _assert(marker in tasklist, f"missing tasklist closure marker: {marker}")

    _assert(
        "FW-RT6-4b-A-TURN-START-MODELS:BEGIN" in tasklist,
        "tasklist Control A marker missing",
    )
    _assert(
        "RealtimeTurnStartResult" in contract,
        "turn-start contract public model missing",
    )
    print("[OK] FW-RT6-4a closure and FW-RT6-4b Control A docs conform")


def main() -> None:
    _check_git_surface()
    _check_public_models()
    _check_runtime_adoption_deferred()
    _check_tests_and_regressions()
    _check_docs()

    print("v600_rt6_4a_closure_status: COMPLETED / VERIFIED / COMMITTED / PUSHED / ACCEPTED / CLOSED")
    print("v600_rt6_4a_closure_commit: dc80d1ade4db539a38d30c74edf73e8ba824531a")
    print("v600_rt6_4b_control_a_status: implemented-awaiting-review")
    print("v600_rt6_4b_control_a_exact_surface: 11 files")
    print("v600_rt6_4b_root_public_names: 125")
    print("v600_rt6_4b_turn_start_public_models: 1")
    print("v600_rt6_4b_turn_result_identity_fields: session_id / generation_id")
    print("v600_rt6_4b_focused_unit_tests: 10 / PASS")
    print("v600_rt6_4b_full_unit_tests: 90 / PASS")
    print("v600_rt6_4b_start_turn_runtime_adoption: False / DEFERRED")
    print("v600_rt6_4b_active_turn_context: False / DEFERRED")
    print("v600_rt6_4b_provider_execution: False")
    print("v600_rt6_4b_network_execution: False")
    print("v600_rt6_4b_microphone_access: False")
    print("v600_rt6_4b_playback_execution: False")
    print("v600_rt6_4b_real_vts_execution: False")
    print("v600_rt6_4b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_4b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
