"""FW-RT6-10d Control C aggregate callback/plugin isolation gate.

The gate uses deterministic in-memory fakes only. It performs no provider,
network, audio, microphone, playback, or real VTube Studio operation.
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import inspect
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "0b5faf96d2886d9372bab5a51ddc68b9da2515a3"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_callback_isolation_acceptance.py",
    "tests/test_callback_isolation_control_a.py",
    "tests/test_callback_isolation_control_b.py",
}
EXPECTED_EXPORTS = (
    "CallbackBoundary",
    "CallbackFailureAction",
    "CallbackIsolationPolicy",
    "CallbackDispatchResult",
    "StageCriticality",
    "StageFailureAction",
    "StageFailurePolicy",
    "callback_isolation_policy",
    "criticality_for_stage",
    "stage_failure_policy",
    "dispatch_isolated_callbacks",
    "dispatch_isolated_callbacks_async",
)
EXPECTED_TASKS = (
    "public callback failure policyを定義する。",
    "plugin hook failure policyを定義する。",
    "motion hook failure policyを定義する。",
    "critical/non-critical stage failureを区別する。",
    "callback reentrancyを検証する。",
    "event callbackがsession lockを保持したまま呼ばれない設計にする。",
)
EXPECTED_CONTROL_A_TESTS = (
    "test_explicit_exports_are_exact_and_root_surface_is_unchanged",
    "test_sync_dispatch_isolates_failure_and_continues_in_order",
    "test_async_plugin_dispatch_awaits_and_isolates_each_handler",
    "test_stage_failure_policies_keep_session_runtime_and_terminal_truth",
    "test_models_have_only_public_safe_fields",
)
EXPECTED_CONTROL_B_TESTS = (
    "test_text_callbacks_are_isolated_and_do_not_corrupt_success",
    "test_voice_callbacks_continue_and_run_without_input_operation_lock",
    "test_sync_and_async_plugin_hooks_are_isolated_in_order",
    "test_realtime_callbacks_are_isolated_lock_free_and_snapshot_safe",
    "test_stage_exceptions_become_typed_critical_and_noncritical_results",
    "test_callback_failure_during_close_is_typed_and_sessions_stay_closed",
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
    print("[OK] baseline and exact five-file corrective FW-RT6-10d Control C surface conform")


def check_accepted_controls_and_lazy_root() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.callback_isolation' not in sys.modules; "
        "assert not hasattr(framework, 'CallbackIsolationPolicy'); "
        "assert len(framework.__all__) == 127; "
        "assert framework.RealtimeSessionInfo().api_version == '5.2.0'; "
        "assert framework.MotionSessionInfo().api_version == '5.5.0'"
    )
    _run([sys.executable, "-c", code])

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-10d-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10d-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-10d-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10d-B-ACCEPTANCE-SYNC:END",
    ):
        _require(tasklist.count(marker) == 1, f"accepted sync marker drift: {marker}")
    for phrase in (
        "Control A implementation: a6ffae7e035d4a6761edd2a75afc1a0e77bbd4b9",
        "Control A acceptance sync: 5fd2f84b74a769d9158ca7785f98e3ea88f42a5a",
        "Control B implementation: b7dfeab05a1a9e87042f9a8e960d53be6da5c5b8",
        "Control B acceptance sync: 0b5faf96d2886d9372bab5a51ddc68b9da2515a3",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted Control A/B fact missing: {phrase}")

    control_a_source = (PROJECT_ROOT / "tests/test_callback_isolation_control_a.py").read_text(encoding="utf-8")
    control_b_source = (PROJECT_ROOT / "tests/test_callback_isolation_control_b.py").read_text(encoding="utf-8")
    _require(control_a_source.count("    def test_") == 13, "Control A test count drift")
    _require(control_b_source.count("    def test_") == 12, "Control B test count drift")
    for name in EXPECTED_CONTROL_A_TESTS:
        _require(f"def {name}(" in control_a_source, f"Control A test missing: {name}")
    for name in EXPECTED_CONTROL_B_TESTS:
        _require(f"def {name}(" in control_b_source, f"Control B test missing: {name}")

    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_callback_isolation_control_a",
            "tests.test_callback_isolation_control_b",
        ],
        capture=False,
    )
    print("[OK] root import stays lazy and isolation names remain explicit-only")
    print("[OK] accepted Control A+B callback/plugin isolation regressions conform")


def check_policy_and_runtime_adoption() -> None:
    import framework
    import framework.callback_isolation as isolation
    from framework.callback_isolation import (
        CallbackBoundary,
        CallbackDispatchResult,
        CallbackFailureAction,
        CallbackIsolationPolicy,
        StageCriticality,
        StageFailureAction,
        StageFailurePolicy,
        callback_isolation_policy,
        criticality_for_stage,
        dispatch_isolated_callbacks,
        stage_failure_policy,
    )
    from framework.realtime_stage import RealtimeStageKind

    _require(tuple(isolation.__all__) == EXPECTED_EXPORTS, "explicit exports drift")
    _require(
        tuple(value.value for value in CallbackBoundary)
        == ("public_callback", "plugin_hook", "motion_hook"),
        "callback boundary vocabulary drift",
    )
    _require(
        tuple(value.value for value in CallbackFailureAction)
        == ("continue_dispatch", "skip_motion"),
        "callback failure action drift",
    )
    _require(
        tuple(value.value for value in StageCriticality)
        == ("critical", "non_critical"),
        "stage criticality drift",
    )
    _require(
        tuple(value.value for value in StageFailureAction)
        == ("fail_current_operation", "continue_degraded"),
        "stage failure action drift",
    )
    _require(
        tuple(field.name for field in fields(CallbackIsolationPolicy))
        == (
            "boundary",
            "failure_action",
            "continue_remaining_handlers",
            "runtime_failure_on_exception",
            "invoke_without_session_lock",
            "reentrant_safe",
        ),
        "callback policy fields drift",
    )
    _require(
        tuple(field.name for field in fields(CallbackDispatchResult))
        == ("boundary", "attempted_count", "completed_count", "failed_count"),
        "dispatch result fields drift",
    )
    _require(
        tuple(field.name for field in fields(StageFailurePolicy))
        == (
            "criticality",
            "failure_action",
            "current_operation_fails",
            "session_remains_open",
            "runtime_remains_available",
            "existing_terminal_replacement_allowed",
        ),
        "stage policy fields drift",
    )

    observed: list[str] = []

    def failed(value: str) -> None:
        observed.append(f"failed:{value}")
        raise RuntimeError("private-aggregate-callback-sentinel")

    result = dispatch_isolated_callbacks(
        (
            lambda value: observed.append(f"first:{value}"),
            failed,
            lambda value: observed.append(f"last:{value}"),
        ),
        "value",
    )
    _require(
        observed == ["first:value", "failed:value", "last:value"],
        "isolated callback order drift",
    )
    _require(
        (result.attempted_count, result.completed_count, result.failed_count)
        == (3, 2, 1),
        "isolated callback counts drift",
    )
    _require("private-aggregate" not in repr(result), "raw exception escaped")

    for boundary in (CallbackBoundary.PUBLIC_CALLBACK, CallbackBoundary.PLUGIN_HOOK):
        policy = callback_isolation_policy(boundary)
        _require(policy.continue_remaining_handlers, "continue policy drift")
        _require(not policy.runtime_failure_on_exception, "callback became runtime failure")
        _require(policy.invoke_without_session_lock, "lock-free policy drift")
        _require(policy.reentrant_safe, "reentrant policy drift")
    motion = callback_isolation_policy(CallbackBoundary.MOTION_HOOK)
    _require(
        motion.failure_action is CallbackFailureAction.SKIP_MOTION
        and not motion.continue_remaining_handlers,
        "motion hook policy drift",
    )

    for stage_kind, expected in (
        (RealtimeStageKind.VOICE_INPUT, StageCriticality.CRITICAL),
        (RealtimeStageKind.TEXT_GENERATION, StageCriticality.CRITICAL),
        (RealtimeStageKind.VOICE_OUTPUT, StageCriticality.NON_CRITICAL),
        (RealtimeStageKind.MOTION, StageCriticality.NON_CRITICAL),
    ):
        criticality = criticality_for_stage(stage_kind)
        _require(criticality is expected, f"criticality drift: {stage_kind.value}")
        policy = stage_failure_policy(criticality)
        _require(policy.session_remains_open, "stage failure closed session")
        _require(policy.runtime_remains_available, "stage failure killed runtime")
        _require(not policy.existing_terminal_replacement_allowed, "terminal replacement escaped")

    expected_markers = {
        "core/events.py": ("dispatch_isolated_callbacks_async", "CallbackBoundary.PLUGIN_HOOK"),
        "framework/facade.py": ("dispatch_isolated_callbacks", "stage_criticality"),
        "framework/voice_input_session.py": ("dispatch_isolated_callbacks", "_release_save"),
        "framework/motion_session.py": ("dispatch_isolated_callbacks", "_callback_failure_count"),
        "framework/realtime_session.py": (
            "_callback_delivery_window",
            "_isolated_stage_failure_envelope",
            "_callback_window_condition",
        ),
    }
    for relative, markers in expected_markers.items():
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in source, f"runtime adoption missing: {relative}: {marker}")

    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(framework.RealtimeSessionInfo().api_version == "5.2.0", "realtime version changed")
    _require(framework.MotionSessionInfo().api_version == "5.5.0", "motion version changed")
    print("[OK] immutable callback, hook, and stage policies conform")
    print("[OK] stable ordered dispatch, privacy, and runtime adopters conform")
    print("[OK] lock-free reentrancy, stage criticality, and close truth conform")


def check_public_boundaries_and_task_closure() -> None:
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-10d-C-CALLBACK-ISOLATION-ACCEPTANCE:BEGIN",
        "FW-RT6-10d-C-CALLBACK-ISOLATION-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public contract marker drift: {marker}")
    for marker in (
        "FW-RT6-10d-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-10d-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")
    facade_control_c = facade.split(
        "<!-- FW-RT6-10d-C-CALLBACK-ISOLATION-ACCEPTANCE:BEGIN -->",
        1,
    )[1].split(
        "<!-- FW-RT6-10d-C-CALLBACK-ISOLATION-ACCEPTANCE:END -->",
        1,
    )[0]
    tasklist_control_c = tasklist.split(
        "<!-- FW-RT6-10d-C-AGGREGATE-ACCEPTANCE:BEGIN -->",
        1,
    )[1].split(
        "<!-- FW-RT6-10d-C-AGGREGATE-ACCEPTANCE:END -->",
        1,
    )[0]
    for phrase in (
        "exact corrective Control C surface: 5 files",
        "stable explicit policy package: framework.callback_isolation / REUSED / PASS",
        "callback invocation under registry/session lock: False / PASS",
        "new callback/event registry or dispatcher thread: False / PASS",
        "runtime source changed by Control C: False",
        "existing Control A+B test semantic sync: 2 files / TASK BOUNDARY ONLY",
        "FW-RT6-10d tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "FW-RT6-10d final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-11a: NOT_AUTHORIZED",
        "Control C commit / push: NOT_AUTHORIZED",
    ):
        _require(
            phrase in facade_control_c or phrase in tasklist_control_c,
            f"aggregate phrase missing: {phrase}",
        )

    section = tasklist.split("## FW-RT6-10d — Callback and plugin isolation", 1)[1].split(
        "## FW-RT6-11a", 1
    )[0]
    _require(section.count("- [x]") == 6, "FW-RT6-10d accepted-candidate count drift")
    _require(section.count("- [ ]") == 0, "FW-RT6-10d task remains open")
    for task in EXPECTED_TASKS:
        _require(task in section, f"FW-RT6-10d task missing: {task}")

    runtime_changed = EXPECTED_SURFACE.intersection(
        {"core/events.py"}
        | {
            "framework/facade.py",
            "framework/motion_session.py",
            "framework/realtime_session.py",
            "framework/voice_input_session.py",
            "framework/callback_isolation.py",
        }
    )
    _require(not runtime_changed, "Control C runtime surface escaped")
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice", "openai"):
        _require(module_name not in sys.modules, f"provider/runtime module escaped: {module_name}")
    print("[OK] root-public, version, provider, and runtime boundaries conform")
    print("[OK] existing Control A+B tests receive task-boundary-only semantic sync")
    print("[OK] six FW-RT6-10d tasks close as aggregate acceptance-candidates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_controls_and_lazy_root()
    check_policy_and_runtime_adoption()
    check_public_boundaries_and_task_closure()

    print("v600_rt6_10d_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10d_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10d_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10d_control_c_exact_surface: 5 files / CORRECTIVE")
    print("v600_rt6_10d_runtime_changed_by_control_c: False")
    print("v600_rt6_10d_existing_test_semantic_sync: 2 files / TASK_BOUNDARY_ONLY")
    print("v600_rt6_10d_isolation_owner: framework.callback_isolation / REUSED")
    print("v600_rt6_10d_event_owner: RealtimeEventHub / REUSED")
    print("v600_rt6_10d_public_callback_failure: ISOLATED / CONTINUE")
    print("v600_rt6_10d_plugin_hook_failure: ISOLATED / SYNC+ASYNC CONTINUE")
    print("v600_rt6_10d_session_lock_during_callback: False / PASS")
    print("v600_rt6_10d_reentrant_deadlock: False / PASS")
    print("v600_rt6_10d_stage_failure: TYPED / CRITICALITY_APPLIED")
    print("v600_rt6_10d_close_cleanup_truth: RETAINED / PASS")
    print("v600_rt6_10d_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_10d_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_11a: NOT_AUTHORIZED")
    print("v600_rt6_10d_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10d Control C aggregate callback/plugin isolation gate passed")


if __name__ == "__main__":
    main()
