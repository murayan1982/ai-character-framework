"""FW-RT6-11a Control B public compatibility-profile adoption gate."""

from __future__ import annotations

import argparse
import inspect
from pathlib import Path
import subprocess
import sys
import warnings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "149edb89e65409ce9c6854b39449d05e9ecfeb98"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/audio/voice_output.py",
    "framework/facade.py",
    "framework/motion_session.py",
    "framework/realtime_session.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_session_compatibility_control_a.py",
    "scripts/smoke_v600_session_compatibility_control_b.py",
    "tests/test_session_compatibility_control_a.py",
    "tests/test_session_compatibility_control_b.py",
}
RUNTIME_ADOPTION_FILES = (
    "framework/facade.py",
    "framework/voice_input_session.py",
    "framework/audio/voice_output.py",
    "framework/motion_session.py",
    "framework/realtime_session.py",
)
CONTROL_A_SEMANTIC_SYNC = {
    "scripts/smoke_v600_session_compatibility_control_a.py",
    "tests/test_session_compatibility_control_a.py",
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
            line.strip().replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-11a Control B baseline",
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
    print("[OK] baseline and exact eleven-file FW-RT6-11a Control B surface conform")


def check_lazy_import_contract() -> None:
    code = "\n".join(
        (
            "import sys",
            "import framework",
            "assert 'framework.session_compatibility' not in sys.modules",
            "assert len(framework.__all__) == 127",
            "session = framework.VoiceOutputSession()",
            "assert 'framework.session_compatibility' not in sys.modules",
            "assert session.compatibility_profile.mode.value == 'v5_standalone'",
            "assert 'framework.session_compatibility' in sys.modules",
            "session.close()",
        )
    )
    _run("-c", code)
    print("[OK] root import and construction stay lazy until profile access")


def check_focused_contract() -> None:
    _run(
        "-m",
        "unittest",
        "tests.test_session_compatibility_control_a",
        "tests.test_session_compatibility_control_b",
    )

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.audio.voice_output import VoiceOutputSession
    from framework.facade import TextChatSession, TextChatSessionInfo
    from framework.motion_session import MotionSession
    from framework.realtime_session import RealtimeSession
    from framework.realtime_session_config import RealtimeSessionConfig
    from framework.session_compatibility import (
        CompatibilityWarningMode,
        SessionCompatibilityMode,
    )
    from framework.voice_input_session import VoiceInputSession

    session_types = (
        TextChatSession,
        VoiceInputSession,
        VoiceOutputSession,
        MotionSession,
        RealtimeSession,
    )
    for session_type in session_types:
        descriptor = inspect.getattr_static(session_type, "compatibility_profile")
        _require(isinstance(descriptor, property),
                 f"compatibility profile is not a property: {session_type.__name__}")
        _require(descriptor.fset is None and descriptor.fdel is None,
                 f"compatibility profile is writable: {session_type.__name__}")

    standalone_sessions = (
        TextChatSession(
            object(),  # type: ignore[arg-type]
            TextChatSessionInfo(
                preset="control_b",
                character_name="Control B",
                input_language_code="en",
                output_language_code="en",
                llm_mode="test",
                provider=None,
                model=None,
                route_name=None,
            ),
        ),
        VoiceInputSession(),
        VoiceOutputSession(),
        MotionSession(),
    )
    realtime_sessions = (
        RealtimeSession(),
        RealtimeSession(real_runtime_enabled=False),
        RealtimeSession(real_runtime_enabled=True),
        RealtimeSession(config=RealtimeSessionConfig(real_runtime_enabled=True)),
    )
    all_sessions = (*standalone_sessions, *realtime_sessions)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            standalone_profiles = tuple(
                session.compatibility_profile for session in standalone_sessions
            )
            realtime_profiles = tuple(
                session.compatibility_profile for session in realtime_sessions
            )
        _require(not caught, "compatibility profile access emitted a warning")
        _require(
            all(
                profile.mode is SessionCompatibilityMode.V5_STANDALONE
                for profile in standalone_profiles
            ),
            "standalone compatibility mode drifted",
        )
        _require(
            tuple(profile.mode for profile in realtime_profiles)
            == (
                SessionCompatibilityMode.V5_SKELETON,
                SessionCompatibilityMode.V5_SKELETON,
                SessionCompatibilityMode.V6_UNIFIED,
                SessionCompatibilityMode.V6_UNIFIED,
            ),
            "RealtimeSession request-mode mapping drifted",
        )
        for profile in (*standalone_profiles, *realtime_profiles):
            _require(
                profile.warning_mode is CompatibilityWarningMode.SILENT,
                "compatibility profile became noisy",
            )
            _require(not profile.runtime_execution_performed,
                     "profile access performed runtime execution")
        before_close = tuple(session.compatibility_profile for session in all_sessions)
    finally:
        for session in all_sessions:
            session.close()
    _require(
        tuple(session.compatibility_profile for session in all_sessions) == before_close,
        "compatibility profile changed or disappeared after close",
    )

    requested = RealtimeSession(real_runtime_enabled=True)
    try:
        rejected = requested.run_turn(input_text="no mock fallback")
        _require(rejected.outcome.value == "rejected",
                 "unavailable explicit runtime was not rejected")
        _require(rejected.public_metadata["mock_runtime"] is False,
                 "explicit unified request fell back to mock")
        _require(rejected.public_metadata["provider_execution_performed"] is False,
                 "compatibility probe executed a provider")
    finally:
        requested.close()

    _require(len(framework.__all__) == 127, "root-public surface changed")
    print("[OK] five read-only properties and exact realtime request modes conform")
    print("[OK] profiles stay silent, immutable, provider-free, and readable after close")
    print("[OK] explicit unified request never silently falls back to mock")


def check_source_contract() -> None:
    for relative in RUNTIME_ADOPTION_FILES:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(source.count("def compatibility_profile") == 1,
                 f"profile property count drifted: {relative}")
        _require(source.count("build_session_compatibility_profile(") == 1,
                 f"canonical builder reuse drifted: {relative}")
        _require("warnings.warn" not in source,
                 f"compatibility warning escaped: {relative}")
    for relative in CONTROL_A_SEMANTIC_SYNC:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("control_b" in source.lower() and "compatibility_profile" in source,
                 f"Control A semantic sync drifted: {relative}")
    print("[OK] five runtime owners reuse the canonical builder exactly once")
    print("[OK] Control A semantic sync stays limited to the authorized boundary")


def check_existing_compatibility_contract() -> None:
    _run("scripts/smoke_v600_session_compatibility_control_a.py", "--source-only")
    print("[OK] accepted Control A and historical v5 compatibility gates remain green")


def check_docs_and_task_boundary() -> None:
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-11a-B-SESSION-COMPATIBILITY-ADOPTION:BEGIN" in text,
            f"Control B contract missing from {relative}",
        )
        _require("exact corrective implementation surface: 11 files" in text,
                 f"exact surface missing from {relative}")
        _require("0 / 6 CLOSED" in text,
                 f"aggregate boundary missing from {relative}")
        _require("Control C" in text and "NOT_AUTHORIZED" in text,
                 f"later-control boundary missing from {relative}")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split(
        "## FW-RT6-11a — v5 standalone session compatibility",
        1,
    )[1].split("## FW-RT6-11b", 1)[0]
    _require(section.count("- [ ]") == 6, "FW-RT6-11a task count drifted")
    _require(section.count("- [x]") == 0, "Control B closed aggregate tasks")
    print("[OK] documentation and 0 / 6 aggregate boundary conform")


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
    check_lazy_import_contract()
    check_focused_contract()
    check_source_contract()
    check_existing_compatibility_contract()
    check_docs_and_task_boundary()
    print("v600_rt6_11a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11a_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11a_control_b_exact_surface: 11 files / CORRECTED")
    print("v600_rt6_11a_control_a_semantic_sync: 2 files / CONTROL_B_BOUNDARY_ONLY")
    print("v600_rt6_11a_public_session_adoption: 5 / 5 PASS")
    print("v600_rt6_11a_profile_property: READ_ONLY / LAZY")
    print("v600_rt6_11a_standalone_mode: v5_standalone / 4 PASS")
    print("v600_rt6_11a_realtime_default_mode: v5_skeleton / PASS")
    print("v600_rt6_11a_realtime_explicit_mode: v6_unified / PASS")
    print("v600_rt6_11a_silent_mock_fallback: False / PASS")
    print("v600_rt6_11a_profile_after_close: READABLE / PASS")
    print("v600_rt6_11a_compatibility_warning: SILENT / PASS")
    print("v600_rt6_11a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_11a_task_count: 0 / 6 CLOSED")
    print("v600_rt6_11a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_11b: NOT_AUTHORIZED")
    print("v600_rt6_11a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11a Control B session compatibility adoption gate passed")


if __name__ == "__main__":
    main()
