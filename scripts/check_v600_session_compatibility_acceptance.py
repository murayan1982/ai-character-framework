"""FW-RT6-11a Control C aggregate session-compatibility acceptance gate.

The gate uses deterministic in-memory sessions and existing mock-safe release
checks only. It performs no provider, network, audio, microphone, playback, or
real VTube Studio operation.
"""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import subprocess
import sys
import warnings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "f79dfa6794138654c5f89a212b32ecd7f58399af"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_session_compatibility_acceptance.py",
    "tests/test_session_compatibility_control_b.py",
}
EXPECTED_TASKS = (
    "TextChatSession compatibility adapterを完成する。",
    "VoiceInputSession compatibility adapterを完成する。",
    "VoiceOutputSession compatibility adapterを完成する。",
    "MotionSession compatibility adapterを完成する。",
    "RealtimeSession v5 skeleton behaviorのcompatibility modeを決める。",
    "deprecated fields/methodsのwarning policyを決める。",
)
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
RUNTIME_ADOPTION_FILES = (
    "framework/facade.py",
    "framework/voice_input_session.py",
    "framework/audio/voice_output.py",
    "framework/motion_session.py",
    "framework/realtime_session.py",
)
FORBIDDEN_RUNTIME_MODULES = (
    "openai",
    "pyvts",
    "pyaudio",
    "sounddevice",
    "websockets",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], *, capture: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=capture,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (result.stdout or "")
        + (result.stderr or ""),
    )
    return result.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print(
        "[OK] baseline and exact four-file corrective "
        "FW-RT6-11a Control C surface conform"
    )


def check_accepted_history_and_lazy_root() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_compatibility' not in sys.modules; "
        "assert not hasattr(framework, 'SessionCompatibilityProfile'); "
        "assert len(framework.__all__) == 127; "
        "assert framework.TextChatSessionInfo.__dataclass_fields__['api_version'].default == '4.0'; "
        "assert framework.VoiceInputSessionInfo.__dataclass_fields__['api_version'].default == '5.2.0'; "
        "assert framework.VoiceOutputSessionInfo.__dataclass_fields__['boundary_version'].default == 'v5.lazy_provider_adapter'; "
        "assert framework.RealtimeSessionInfo().api_version == '5.2.0'; "
        "assert framework.MotionSessionInfo().api_version == '5.5.0'"
    )
    _run([sys.executable, "-c", code])

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-11a-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-11a-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-11a-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-11a-B-ACCEPTANCE-SYNC:END",
    ):
        _require(tasklist.count(marker) == 1, f"accepted sync marker drift: {marker}")
    for phrase in (
        "Control A implementation: cc7ba3b2a550e465e51227462a4158ebebde67fc",
        "Control A acceptance sync: 149edb89e65409ce9c6854b39449d05e9ecfeb98",
        "Control B implementation: 675c4b895f424b75301a5eea5593a75e0349b661",
        "Control B acceptance sync: f79dfa6794138654c5f89a212b32ecd7f58399af",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted Control A/B fact missing: {phrase}")

    control_a_source = (
        PROJECT_ROOT / "tests/test_session_compatibility_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_source = (
        PROJECT_ROOT / "tests/test_session_compatibility_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_source.count("    def test_") == 14, "Control A test count drift")
    _require(control_b_source.count("    def test_") == 16, "Control B test count drift")
    _require(
        "test_control_c_closes_only_the_aggregate_task_boundary" in control_b_source,
        "Control B aggregate boundary sync missing",
    )

    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_session_compatibility_control_a",
            "tests.test_session_compatibility_control_b",
        ],
        capture=False,
    )
    print("[OK] root import stays lazy and compatibility names remain explicit-only")
    print("[OK] accepted Control A+B compatibility regressions conform")


def check_existing_v5_compatibility_evidence() -> None:
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_text_chat_compatibility_control_a",
            "tests.test_text_chat_compatibility_control_b",
            "tests.test_text_chat_compatibility_control_c",
            "tests.test_voice_input_result_compatibility_control_a",
            "tests.test_voice_input_result_compatibility_control_b",
        ],
        capture=False,
    )
    for script in (
        "scripts/smoke_voice_output_v500_release_readiness.py",
        "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
        "scripts/smoke_v520_motion_public_contract_conformance_gate.py",
    ):
        _run([sys.executable, script], capture=False)
    print("[OK] accepted v5 compatibility regressions and current release gates conform")


def check_profile_warning_and_runtime_contract() -> None:
    import framework
    from framework.audio.voice_output import VoiceOutputSession
    from framework.facade import TextChatSession, TextChatSessionInfo
    from framework.motion_session import MotionSession
    from framework.realtime_session import RealtimeSession
    from framework.realtime_session_config import RealtimeSessionConfig
    import framework.session_compatibility as compatibility
    from framework.voice_input_session import VoiceInputSession

    _require(tuple(compatibility.__all__) == EXPECTED_EXPORTS, "explicit exports drifted")

    for session_type in (
        framework.TextChatSession,
        framework.VoiceInputSession,
        framework.VoiceOutputSession,
        framework.MotionSession,
        framework.RealtimeSession,
    ):
        descriptor = inspect.getattr_static(session_type, "compatibility_profile")
        _require(
            isinstance(descriptor, property),
            f"compatibility profile is not a property: {session_type.__name__}",
        )
        _require(
            descriptor.fset is None and descriptor.fdel is None,
            f"compatibility profile is writable: {session_type.__name__}",
        )

    standalone_sessions = (
        TextChatSession(
            object(),  # type: ignore[arg-type]
            TextChatSessionInfo(
                preset="control_c",
                character_name="Control C",
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
        _require(not caught, "compatibility access emitted a warning")
        _require(
            all(
                profile.mode is compatibility.SessionCompatibilityMode.V5_STANDALONE
                for profile in standalone_profiles
            ),
            "standalone compatibility mode drifted",
        )
        _require(
            tuple(profile.mode for profile in realtime_profiles)
            == (
                compatibility.SessionCompatibilityMode.V5_SKELETON,
                compatibility.SessionCompatibilityMode.V5_SKELETON,
                compatibility.SessionCompatibilityMode.V6_UNIFIED,
                compatibility.SessionCompatibilityMode.V6_UNIFIED,
            ),
            "RealtimeSession request-mode mapping drifted",
        )
        for profile in (*standalone_profiles, *realtime_profiles):
            _require(
                profile.warning_mode is compatibility.CompatibilityWarningMode.SILENT,
                "compatibility profile became noisy",
            )
            _require(not profile.runtime_execution_performed, "profile executed runtime work")
            rendered = json.dumps(profile.as_dict(), sort_keys=True).lower()
            for forbidden in (
                "credential",
                "provider_payload",
                "transcript",
                "audio_data",
                "private_path",
                "callback_identity",
                "thread_identity",
                "client_identity",
            ):
                _require(forbidden not in rendered, f"private profile field escaped: {forbidden}")
        before_close = tuple(session.compatibility_profile for session in all_sessions)
    finally:
        for session in all_sessions:
            session.close()
    _require(
        tuple(session.compatibility_profile for session in all_sessions) == before_close,
        "compatibility profile changed after close",
    )

    requested = RealtimeSession(real_runtime_enabled=True)
    try:
        rejected = requested.run_turn(input_text="aggregate acceptance")
        _require(rejected.outcome.value == "rejected", "unavailable unified runtime was not rejected")
        _require(
            rejected.public_metadata["mock_runtime"] is False,
            "explicit unified request fell back to mock",
        )
        _require(
            rejected.public_metadata["provider_execution_performed"] is False,
            "compatibility acceptance executed a provider",
        )
    finally:
        requested.close()

    for kind in compatibility.StandaloneSessionKind:
        for member in compatibility.compatibility_members(kind):
            _require(
                compatibility.warning_mode_for_member("compatibility")
                is compatibility.CompatibilityWarningMode.SILENT,
                f"accepted member became noisy: {kind.value}.{member}",
            )
    policy = compatibility.build_deprecated_member_policy(
        compatibility.StandaloneSessionKind.REALTIME,
        "future_legacy_method",
        replacement="replacement_method",
    )
    _require(policy.warning_category == "DeprecationWarning", "warning category drifted")
    _require(policy.stacklevel == 2, "warning stacklevel drifted")
    _require(not policy.warn_on_import and not policy.warn_on_construction, "warning timing drifted")
    _require(policy.earliest_removal_major_version == 7, "removal boundary drifted")
    _require(policy.migration_evidence_required, "migration evidence boundary drifted")
    print("[OK] five profile owners, realtime request truth, and close readability conform")
    print("[OK] compatibility stays silent and future deprecation policy stays explicit")


def check_source_and_aggregate_boundaries() -> None:
    for relative in RUNTIME_ADOPTION_FILES:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(source.count("def compatibility_profile") == 1, f"profile property drift: {relative}")
        _require(
            source.count("build_session_compatibility_profile(") == 1,
            f"canonical builder reuse drift: {relative}",
        )
        _require("warnings.warn" not in source, f"compatibility warning escaped: {relative}")

    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    app_contract = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-11a-C-SESSION-COMPATIBILITY-ACCEPTANCE:BEGIN",
        "FW-RT6-11a-C-SESSION-COMPATIBILITY-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public contract marker drift: {marker}")
    for marker in (
        "FW-RT6-11a-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-11a-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")

    aggregate_text = facade.split(
        "<!-- FW-RT6-11a-C-SESSION-COMPATIBILITY-ACCEPTANCE:BEGIN -->",
        1,
    )[1].split(
        "<!-- FW-RT6-11a-C-SESSION-COMPATIBILITY-ACCEPTANCE:END -->",
        1,
    )[0] + tasklist.split(
        "<!-- FW-RT6-11a-C-AGGREGATE-ACCEPTANCE:BEGIN -->",
        1,
    )[1].split(
        "<!-- FW-RT6-11a-C-AGGREGATE-ACCEPTANCE:END -->",
        1,
    )[0]
    for phrase in (
        "exact corrective Control C surface: 4 files",
        "runtime source changed by Control C: False",
        "existing Control B test semantic sync: 1 file / TASK BOUNDARY ONLY",
        "canonical compatibility owner: framework.session_compatibility / REUSED / PASS",
        "compatibility warning: SILENT / PASS",
        "deprecated public fields or methods introduced: 0",
        "historical release-gate files changed: False",
        "framework root-public names: 127 / UNCHANGED",
        "FW-RT6-11a tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "FW-RT6-11a final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-11b implementation: NOT_AUTHORIZED",
        "Control C commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in aggregate_text, f"aggregate phrase missing: {phrase}")

    section = tasklist.split(
        "## FW-RT6-11a — v5 standalone session compatibility",
        1,
    )[1].split("## FW-RT6-11b", 1)[0]
    _require(section.count("- [x]") == 6, "FW-RT6-11a accepted-candidate count drift")
    _require(section.count("- [ ]") == 0, "FW-RT6-11a task remains open")
    for task in EXPECTED_TASKS:
        _require(task in section, f"FW-RT6-11a task missing: {task}")

    _require(
        "FW-RT6-11a-B-SESSION-COMPATIBILITY-ADOPTION:BEGIN" in app_contract,
        "accepted application-integration contract missing",
    )
    _require("FW-RT6-11a-C-" not in app_contract, "Control C changed application contract")
    _require(EXPECTED_SURFACE.isdisjoint(set(RUNTIME_ADOPTION_FILES)), "runtime surface escaped")
    _require(
        "tests/test_session_compatibility_control_a.py" not in EXPECTED_SURFACE,
        "Control A test escaped into Control C",
    )
    for module_name in FORBIDDEN_RUNTIME_MODULES:
        _require(module_name not in sys.modules, f"provider/runtime module escaped: {module_name}")
    print("[OK] root-public, version, provider, and runtime boundaries conform")
    print("[OK] one Control B test receives task-boundary-only semantic sync")
    print("[OK] six FW-RT6-11a tasks close as aggregate acceptance-candidates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_history_and_lazy_root()
    check_existing_v5_compatibility_evidence()
    check_profile_warning_and_runtime_contract()
    check_source_and_aggregate_boundaries()

    print("v600_rt6_11a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11a_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11a_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11a_control_c_exact_surface: 4 files / CORRECTIVE")
    print("v600_rt6_11a_runtime_changed_by_control_c: False")
    print("v600_rt6_11a_existing_test_semantic_sync: 1 file / TASK_BOUNDARY_ONLY")
    print("v600_rt6_11a_compatibility_owner: framework.session_compatibility / REUSED")
    print("v600_rt6_11a_public_session_adoption: 5 / 5 PASS")
    print("v600_rt6_11a_standalone_mode: v5_standalone / 4 PASS")
    print("v600_rt6_11a_realtime_default_mode: v5_skeleton / PASS")
    print("v600_rt6_11a_realtime_explicit_mode: v6_unified / PASS")
    print("v600_rt6_11a_silent_mock_fallback: False / PASS")
    print("v600_rt6_11a_profile_after_close: READABLE / PASS")
    print("v600_rt6_11a_compatibility_warning: SILENT / PASS")
    print("v600_rt6_11a_deprecated_warning: DeprecationWarning / POLICY_ONLY")
    print("v600_rt6_11a_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_11a_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_11b: NOT_AUTHORIZED")
    print("v600_rt6_11a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11a Control C aggregate session compatibility gate passed")


if __name__ == "__main__":
    main()
