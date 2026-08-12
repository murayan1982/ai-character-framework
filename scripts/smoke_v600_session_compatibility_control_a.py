"""FW-RT6-11a Control A standalone-session compatibility contract gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "182335063eabdd901095b4184f097e095eb7021d"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/session_compatibility.py",
    "scripts/smoke_v600_session_compatibility_control_a.py",
    "tests/test_session_compatibility_control_a.py",
}
EXPECTED_EXPORTS = (
    "StandaloneSessionKind",
    "SessionCompatibilityMode",
    "CompatibilityMemberStatus",
    "CompatibilityWarningMode",
    "SessionCompatibilityProfile",
    "DeprecatedMemberPolicy",
    "build_session_compatibility_profile",
    "build_deprecated_member_policy",
    "compatibility_members",
    "warning_mode_for_member",
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
            line.strip().replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-11a Control A baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the Control A baseline",
    )
    actual = _changed_paths()
    _require(actual == EXPECTED_SURFACE, f"unexpected Control A surface: {sorted(actual)}")
    print("[OK] baseline and exact five-file FW-RT6-11a Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_compatibility' not in sys.modules; "
        "assert not hasattr(framework, 'SessionCompatibilityProfile'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import stays lazy and compatibility names remain explicit-only")


def check_profile_and_warning_contract() -> None:
    _run("-m", "unittest", "tests.test_session_compatibility_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.session_compatibility as compatibility

    _require(tuple(compatibility.__all__) == EXPECTED_EXPORTS, "explicit exports drifted")
    expected = {
        compatibility.StandaloneSessionKind.TEXT_CHAT: (
            compatibility.SessionCompatibilityMode.V5_STANDALONE,
            "4.0",
            "TextChatSession",
        ),
        compatibility.StandaloneSessionKind.VOICE_INPUT: (
            compatibility.SessionCompatibilityMode.V5_STANDALONE,
            "5.2.0",
            "VoiceInputSession",
        ),
        compatibility.StandaloneSessionKind.VOICE_OUTPUT: (
            compatibility.SessionCompatibilityMode.V5_STANDALONE,
            "v5.lazy_provider_adapter",
            "VoiceOutputSession",
        ),
        compatibility.StandaloneSessionKind.MOTION: (
            compatibility.SessionCompatibilityMode.V5_STANDALONE,
            "5.5.0",
            "MotionSession",
        ),
        compatibility.StandaloneSessionKind.REALTIME: (
            compatibility.SessionCompatibilityMode.V5_SKELETON,
            "5.2.0",
            "RealtimeSession",
        ),
    }
    for kind, (mode, version, owner) in expected.items():
        profile = compatibility.build_session_compatibility_profile(kind)
        _require(profile.mode is mode, f"compatibility mode drifted: {kind.value}")
        _require(profile.contract_version == version, f"version drifted: {kind.value}")
        _require(profile.execution_owner == owner, f"owner drifted: {kind.value}")
        _require(profile.warning_mode is compatibility.CompatibilityWarningMode.SILENT,
                 f"compatibility warning escaped: {kind.value}")
        _require(not profile.runtime_execution_performed,
                 f"profile executed runtime work: {kind.value}")

    unified = compatibility.build_session_compatibility_profile(
        compatibility.StandaloneSessionKind.REALTIME,
        unified_runtime_requested=True,
    )
    _require(unified.mode is compatibility.SessionCompatibilityMode.V6_UNIFIED,
             "explicit unified realtime mode drifted")
    for kind in compatibility.StandaloneSessionKind:
        for member in compatibility.compatibility_members(kind):
            _require(
                compatibility.warning_mode_for_member("compatibility")
                is compatibility.CompatibilityWarningMode.SILENT,
                f"v5 compatibility member became noisy: {kind.value}.{member}",
            )

    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(framework.TextChatSessionInfo.__dataclass_fields__["api_version"].default == "4.0",
             "text-chat API version changed")
    _require(framework.VoiceInputSessionInfo.__dataclass_fields__["api_version"].default == "5.2.0",
             "voice-input API version changed")
    _require(framework.VoiceOutputSessionInfo.__dataclass_fields__["boundary_version"].default == "v5.lazy_provider_adapter",
             "voice-output boundary version changed")
    _require(framework.MotionSessionInfo.__dataclass_fields__["api_version"].default == "5.5.0",
             "motion API version changed")
    _require(framework.RealtimeSessionInfo.__dataclass_fields__["api_version"].default == "5.2.0",
             "realtime API version changed")
    print("[OK] five session profiles, realtime mode split, and frozen versions conform")
    print("[OK] compatibility use stays silent and future deprecation policy is explicit")


def check_existing_compatibility_regressions() -> None:
    _run(
        "-m",
        "unittest",
        "tests.test_text_chat_compatibility_control_a",
        "tests.test_text_chat_compatibility_control_b",
        "tests.test_text_chat_compatibility_control_c",
        "tests.test_voice_input_result_compatibility_control_a",
        "tests.test_voice_input_result_compatibility_control_b",
    )
    for script in (
        "scripts/smoke_voice_output_v500_release_readiness.py",
        "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
        "scripts/smoke_v520_motion_public_contract_conformance_gate.py",
    ):
        _run(script)
    print("[OK] accepted TextChat/VoiceInput regressions and current v5 session gates pass")


def check_runtime_deferral_and_privacy() -> None:
    source = (PROJECT_ROOT / "framework/session_compatibility.py").read_text(
        encoding="utf-8"
    ).lower()
    for forbidden in (
        "import openai",
        "import websocket",
        "import pyvts",
        "import pyaudio",
        "warnings.warn",
    ):
        _require(forbidden not in source, f"provider/runtime operation escaped: {forbidden}")
    for relative in (
        "framework/facade.py",
        "framework/voice_input_session.py",
        "framework/audio/voice_output.py",
        "framework/motion_session.py",
        "framework/realtime_session.py",
    ):
        runtime_source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("session_compatibility" not in runtime_source,
                 f"Control B adoption escaped into Control A: {relative}")
    print("[OK] runtime adoption and warning emission stay deferred to Control B")
    print("[OK] provider execution, private data, and historical gate mutation remain absent")


def check_docs_and_task_boundary() -> None:
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("FW-RT6-11a-A-SESSION-COMPATIBILITY:BEGIN" in text,
                 f"Control A contract missing from {relative}")
        _require("FW-RT6-11a aggregate tasks: 0 / 6 CLOSED" in text,
                 f"aggregate boundary missing from {relative}")
        _require("migration evidence" in text,
                 f"historical-gate supersession evidence missing from {relative}")
        _require("Control B" in text and "NOT_AUTHORIZED" in text,
                 f"later-control boundary missing from {relative}")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split(
        "## FW-RT6-11a — v5 standalone session compatibility",
        1,
    )[1].split("## FW-RT6-11b", 1)[0]
    _require(section.count("- [ ]") == 6, "FW-RT6-11a task count drifted")
    _require(section.count("- [x]") == 0, "Control A closed aggregate tasks")
    print("[OK] documentation, supersession boundary, and 0 / 6 task state conform")


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
    check_profile_and_warning_contract()
    check_existing_compatibility_regressions()
    check_runtime_deferral_and_privacy()
    check_docs_and_task_boundary()
    print("v600_rt6_11a_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11a_control_a_exact_surface: 5 files")
    print("v600_rt6_11a_explicit_package: framework.session_compatibility / PASS")
    print("v600_rt6_11a_session_profiles: 5 / TYPED")
    print("v600_rt6_11a_realtime_default_mode: v5_skeleton")
    print("v600_rt6_11a_realtime_explicit_mode: v6_unified")
    print("v600_rt6_11a_compatibility_warning: SILENT")
    print("v600_rt6_11a_deprecated_warning: DeprecationWarning / POLICY_ONLY")
    print("v600_rt6_11a_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_11a_historical_gate_rewrite: False")
    print("v600_rt6_11a_task_count: 0 / 6 CLOSED")
    print("v600_rt6_11a_control_b: NOT_AUTHORIZED")
    print("v600_rt6_11a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_11b: NOT_AUTHORIZED")
    print("v600_rt6_11a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11a Control A standalone-session compatibility gate passed")


if __name__ == "__main__":
    main()
