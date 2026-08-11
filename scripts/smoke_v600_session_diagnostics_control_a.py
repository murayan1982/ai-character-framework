"""FW-RT6-10c Control A immutable public diagnostics contract gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "3fe21fd1aec9f38019e1bfadb946f3246edc7799"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/session_diagnostics.py",
    "scripts/smoke_v600_session_diagnostics_control_a.py",
    "tests/test_session_diagnostics_control_a.py",
}
EXPECTED_EXPORTS = (
    "SessionTerminalSnapshot",
    "SessionDiagnosticsSnapshot",
    "build_session_terminal_snapshot",
    "build_session_diagnostics_snapshot",
)


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
        "unexpected FW-RT6-10c Control A baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the Control A baseline",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(actual)}",
    )
    print("[OK] baseline and exact five-file FW-RT6-10c Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_diagnostics' not in sys.modules; "
        "assert not hasattr(framework, 'SessionDiagnosticsSnapshot'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import stays lazy and diagnostics names remain explicit-only")


def check_model_contract() -> None:
    _run("-m", "unittest", "tests.test_session_diagnostics_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.lifecycle import RealtimePhase, RecoveryAction, TurnOutcome
    from framework.realtime import RealtimeErrorCode, RealtimeState, RealtimeTurnResult
    import framework.session_diagnostics as control

    _require(tuple(control.__all__) == EXPECTED_EXPORTS, "explicit exports drifted")
    session_id = SessionId.new()
    turn_id = TurnId.new()
    generation_id = GenerationId.new()
    rich = RealtimeTurnResult.failed(
        session_id=session_id,
        turn_id=turn_id,
        generation_id=generation_id,
        public_error_code=RealtimeErrorCode.PROVIDER_ERROR,
        safe_message="do-not-retain-message",
        retryable=True,
        recovery_action=RecoveryAction.RECONNECT,
        public_metadata={"provider_payload": "do-not-retain-payload"},
    )
    terminal = control.build_session_terminal_snapshot(rich)
    _require(terminal is not None, "terminal projection disappeared")
    _require(terminal.outcome is TurnOutcome.FAILED, "terminal outcome drifted")
    _require(
        terminal.public_error_code is RealtimeErrorCode.PROVIDER_ERROR,
        "terminal error code drifted",
    )
    _require(
        "do-not-retain" not in repr(terminal)
        and "provider_payload" not in repr(terminal.as_dict()),
        "private-rich terminal value escaped projection",
    )
    snapshot = control.build_session_diagnostics_snapshot(
        session_id=session_id,
        state=RealtimeState.THINKING,
        phase=RealtimePhase.THINKING,
        is_closed=False,
        active_turn_id=turn_id,
        active_generation_id=generation_id,
        queue_depth=2,
        active_generation_count=1,
        last_terminal_result=rich,
        stale_completion_count=3,
        duplicate_terminal_count=4,
        overflow_count=5,
    )
    _require(snapshot.last_terminal_result is terminal or snapshot.last_terminal_result == terminal,
             "terminal projection changed")
    _require(snapshot.last_safe_error_code is RealtimeErrorCode.PROVIDER_ERROR,
             "last safe error was not derived")
    _require(snapshot.queue_depth == 2, "queue depth drifted")
    _require(snapshot.active_generation_count == 1, "active count drifted")
    _require(
        (snapshot.stale_completion_count,
         snapshot.duplicate_terminal_count,
         snapshot.overflow_count) == (3, 4, 5),
        "diagnostic counts drifted",
    )
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(framework.RealtimeSessionInfo().api_version == "5.2.0",
             "realtime API version changed")
    _require(framework.MotionSessionInfo().api_version == "5.5.0",
             "motion API version changed")
    print("[OK] immutable session and redacted terminal diagnostics models conform")
    print("[OK] ID pairing, closed context, count, and safe-error invariants conform")
    print("[OK] root-public and API-version contracts remain unchanged")


def check_privacy_and_runtime_boundary() -> None:
    source = (PROJECT_ROOT / "framework/session_diagnostics.py").read_text(
        encoding="utf-8"
    )
    for forbidden_import in (
        "openai",
        "websocket",
        "pyvts",
        "pyaudio",
        "sounddevice",
        "microphone",
    ):
        _require(forbidden_import not in source.lower(),
                 f"provider/runtime import escaped: {forbidden_import}")
    runtime = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    _require("diagnostics_snapshot" not in runtime,
             "Control B runtime property escaped into Control A")
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] diagnostics remain provider-free and runtime adoption stays deferred")


def check_docs_and_task_boundary() -> None:
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("FW-RT6-10c-A-PUBLIC-DIAGNOSTICS:BEGIN" in text,
                 f"Control A contract missing from {relative}")
        _require("FW-RT6-10c aggregate tasks: 0 / 9 CLOSED" in text,
                 f"aggregate boundary missing from {relative}")
        _require("Control B" in text and "NOT_AUTHORIZED" in text,
                 f"later-control boundary missing from {relative}")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-10c — Public diagnostics", 1)[1].split(
        "## FW-RT6-10d", 1
    )[0]
    _require(section.count("- [ ]") == 9, "FW-RT6-10c task count drifted")
    _require(section.count("- [x]") == 0, "Control A closed aggregate tasks")
    print("[OK] documentation and 0 / 9 aggregate task boundary conform")


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
    check_model_contract()
    check_privacy_and_runtime_boundary()
    check_docs_and_task_boundary()
    print("v600_rt6_10c_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10c_control_a_exact_surface: 5 files")
    print("v600_rt6_10c_explicit_package: framework.session_diagnostics / PASS")
    print("v600_rt6_10c_terminal_projection: PUBLIC_SAFE / PASS")
    print("v600_rt6_10c_active_context_pairing: ENFORCED / PASS")
    print("v600_rt6_10c_active_generation_count: 0_OR_1 / PASS")
    print("v600_rt6_10c_private_payload_retained: False / PASS")
    print("v600_rt6_10c_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_10c_task_count: 0 / 9 CLOSED")
    print("v600_rt6_10c_control_b: NOT_AUTHORIZED")
    print("v600_rt6_10c_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10c Control A public diagnostics contract gate passed")


if __name__ == "__main__":
    main()
