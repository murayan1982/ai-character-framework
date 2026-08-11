"""FW-RT6-10b Control B unified close/dispose runtime gate."""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "6153661b3960fbfa1130b2caef39e48717ad8e80"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/audio/voice_output.py",
    "framework/facade.py",
    "framework/motion_session.py",
    "framework/realtime_execution_bridge.py",
    "framework/realtime_session.py",
    "framework/session_close.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_session_close_control_b.py",
    "tests/test_session_close_control_b.py",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


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
        "unexpected FW-RT6-10b Control B baseline",
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
    print("[OK] baseline and exact eleven-file FW-RT6-10b Control B surface conform")


def check_lazy_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_close' not in sys.modules; "
        "assert not hasattr(framework, 'SessionCloseResult'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import stays lazy and session-close names remain explicit-only")


def check_runtime_contract() -> None:
    _run("-m", "unittest", "tests.test_session_close_control_b")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.audio.voice_output import VoiceOutputSession
    from framework.facade import TextChatSession
    from framework.motion_session import MotionSession
    from framework.realtime_session import RealtimeSession
    from framework.session_close import SessionCloseOutcome
    from framework.voice_input_session import VoiceInputSession

    public_sessions = (
        RealtimeSession,
        TextChatSession,
        VoiceInputSession,
        VoiceOutputSession,
        MotionSession,
    )
    for session_type in public_sessions:
        _require(
            hasattr(session_type, "last_close_result"),
            f"missing last_close_result: {session_type.__name__}",
        )
        _require(
            not hasattr(session_type, "close_result"),
            f"forbidden ambiguous close_result: {session_type.__name__}",
        )
        signature = inspect.signature(session_type.close)
        _require(
            signature.return_annotation in {None, "None"},
            f"close return contract changed: {session_type.__name__}",
        )

    realtime = RealtimeSession()
    started = realtime.start_turn(input_text="control-b-gate")
    _require(started.accepted, "realtime turn was not admitted")
    realtime.close()
    _require(realtime.is_closed, "realtime close left the session open")
    _require(
        realtime.terminal_results[-1].outcome.value == "closed",
        "active realtime turn was not terminalized as closed",
    )
    _require(
        realtime.last_close_result.active_turn_terminalized,
        "active-turn close fact was not recorded",
    )
    realtime.close()
    _require(
        realtime.last_close_result.outcome is SessionCloseOutcome.ALREADY_CLOSED,
        "duplicate realtime close did not become already_closed",
    )
    _require(
        realtime.last_close_result.diagnostics["cleanup_attempted_count"] == 0,
        "duplicate realtime close repeated cleanup",
    )

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

    print("[OK] five public sessions expose read-only typed last-close results")
    print("[OK] active realtime turn closes through the existing terminal owner")
    print("[OK] final close delivery, callback release, and duplicate close conform")
    print("[OK] bounded stage/provider cleanup and confirmed bridge stop conform")


def check_docs_and_later_control_boundary() -> None:
    for relative in ("docs/app_integration_contract.md", "docs/public_facade.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            text.count("FW-RT6-10b-B-SESSION-CLOSE:BEGIN") == 1,
            f"missing or duplicate Control B begin marker: {relative}",
        )
        _require(
            text.count("FW-RT6-10b-B-SESSION-CLOSE:END") == 1,
            f"missing or duplicate Control B end marker: {relative}",
        )
        for phrase in (
            "exact Control B surface: 11 files",
            "last_close_result",
            "stage cleanup",
            "cleanup failure reopens session: False",
            "framework root-public names: 127 / UNCHANGED",
            "existing tests changed: False",
            "docs/v600_tasklist.md changed: False",
            "Control B commit / push: NOT_AUTHORIZED",
            "Control C",
        ):
            _require(phrase in text, f"missing Control B contract phrase: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-10b", 1)[1].split("## FW-RT6-10c", 1)[0]
    _require(section.count("- [ ]") == 7, "Control B closed an aggregate task")
    _require(section.count("- [x]") == 0, "Control B changed aggregate closure")
    print("[OK] Control B runtime adoption and later-control boundaries are documented")
    print("[OK] FW-RT6-10b aggregate tasks remain 0 / 7 closed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_lazy_import_contract()
    check_runtime_contract()
    check_docs_and_later_control_boundary()
    print("v600_rt6_10b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10b_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10b_control_b_exact_surface: 11 files")
    print("v600_rt6_10b_public_session_adoption: 5 / 5 PASS")
    print("v600_rt6_10b_active_turn_terminal: CLOSED / TYPED / PASS")
    print("v600_rt6_10b_stage_common_deadline: ENFORCED / PASS")
    print("v600_rt6_10b_bridge_stopped_before_complete: True / PASS")
    print("v600_rt6_10b_cleanup_failure_reopens_session: False / PASS")
    print("v600_rt6_10b_duplicate_close_cleanup_count: 0 / PASS")
    print("v600_rt6_10b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_10b_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_10b_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_10b_task_count: 0 / 7 CLOSED")
    print("v600_rt6_10b_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10b Control B unified close/dispose gate passed")


if __name__ == "__main__":
    main()
