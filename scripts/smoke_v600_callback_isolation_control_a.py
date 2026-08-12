"""FW-RT6-10d Control A callback/plugin isolation contract gate."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "ac729f10f4875347f7b222ef55ac560ac9d76eb2"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/callback_isolation.py",
    "scripts/smoke_v600_callback_isolation_control_a.py",
    "tests/test_callback_isolation_control_a.py",
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
        "unexpected FW-RT6-10d Control A baseline",
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
    print("[OK] baseline and exact five-file FW-RT6-10d Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.callback_isolation' not in sys.modules; "
        "assert not hasattr(framework, 'CallbackIsolationPolicy'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import stays lazy and isolation names remain explicit-only")


def check_policy_and_dispatch_contract() -> None:
    _run("-m", "unittest", "tests.test_callback_isolation_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.callback_isolation as control
    from framework.realtime_stage import RealtimeStageKind

    _require(tuple(control.__all__) == EXPECTED_EXPORTS, "explicit exports drifted")
    for boundary in (
        control.CallbackBoundary.PUBLIC_CALLBACK,
        control.CallbackBoundary.PLUGIN_HOOK,
        control.CallbackBoundary.MOTION_HOOK,
    ):
        policy = control.callback_isolation_policy(boundary)
        _require(not policy.runtime_failure_on_exception,
                 "callback failure became runtime failure")
        _require(policy.invoke_without_session_lock,
                 "session-unlocked invocation contract drifted")
        _require(policy.reentrant_safe, "reentrancy contract drifted")

    observed: list[str] = []

    def failing(value: str) -> None:
        observed.append(f"failed:{value}")
        raise RuntimeError("private callback failure")

    result = control.dispatch_isolated_callbacks(
        (
            lambda value: observed.append(f"first:{value}"),
            failing,
            lambda value: observed.append(f"last:{value}"),
        ),
        "event",
    )
    _require(
        observed == ["first:event", "failed:event", "last:event"],
        "sync callback ordering/isolation drifted",
    )
    _require(result.failed_count == 1 and not result.runtime_failed,
             "sync callback failure was not isolated")
    _require("private" not in repr(result), "raw callback detail escaped result")

    async_observed: list[str] = []

    async def async_failing(value: str) -> None:
        async_observed.append(f"failed:{value}")
        await asyncio.sleep(0)
        raise RuntimeError("private async hook failure")

    async def scenario():
        return await control.dispatch_isolated_callbacks_async(
            (
                lambda value: async_observed.append(f"first:{value}"),
                async_failing,
                lambda value: async_observed.append(f"last:{value}"),
            ),
            "hook",
        )

    async_result = asyncio.run(scenario())
    _require(
        async_observed == ["first:hook", "failed:hook", "last:hook"],
        "async plugin hook ordering/isolation drifted",
    )
    _require(async_result.failed_count == 1 and not async_result.runtime_failed,
             "async plugin hook failure was not isolated")

    expected_criticality = {
        RealtimeStageKind.VOICE_INPUT: control.StageCriticality.CRITICAL,
        RealtimeStageKind.TEXT_GENERATION: control.StageCriticality.CRITICAL,
        RealtimeStageKind.VOICE_OUTPUT: control.StageCriticality.NON_CRITICAL,
        RealtimeStageKind.MOTION: control.StageCriticality.NON_CRITICAL,
    }
    for stage_kind, criticality in expected_criticality.items():
        _require(control.criticality_for_stage(stage_kind) is criticality,
                 f"stage criticality drifted: {stage_kind.value}")
        stage_policy = control.stage_failure_policy(criticality)
        _require(stage_policy.session_remains_open,
                 "stage failure closed the session by policy")
        _require(stage_policy.runtime_remains_available,
                 "stage failure killed the runtime by policy")
        _require(not stage_policy.existing_terminal_replacement_allowed,
                 "stage failure may replace an existing terminal")

    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(framework.RealtimeSessionInfo().api_version == "5.2.0",
             "realtime API version changed")
    _require(framework.MotionSessionInfo().api_version == "5.5.0",
             "motion API version changed")
    print("[OK] public callback and sync/async plugin-hook isolation policies conform")
    print("[OK] motion-hook skip and critical/non-critical stage policies conform")
    print("[OK] reentrant lock-free reference dispatch and public-safe results conform")


def check_runtime_deferral_and_privacy() -> None:
    source = (PROJECT_ROOT / "framework/callback_isolation.py").read_text(
        encoding="utf-8"
    )
    for forbidden_import in (
        "import openai",
        "import websocket",
        "import pyvts",
        "import pyaudio",
        "import sounddevice",
    ):
        _require(forbidden_import not in source.lower(),
                 f"provider/runtime import escaped: {forbidden_import}")
    for relative in (
        "core/events.py",
        "plugins/manager.py",
        "framework/facade.py",
        "framework/voice_input_session.py",
        "framework/motion_session.py",
        "framework/realtime_session.py",
    ):
        runtime_source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("callback_isolation" not in runtime_source,
                 f"Control B adoption escaped into Control A: {relative}")
    motion_lifecycle = (PROJECT_ROOT / "framework/motion_lifecycle.py").read_text(
        encoding="utf-8"
    )
    _require("except Exception:" in motion_lifecycle,
             "existing motion hook isolation owner disappeared")
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] runtime adoption stays deferred and existing motion resolver is reused")
    print("[OK] provider, callback identity, exception, and private-value isolation conform")


def check_docs_and_task_boundary() -> None:
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("FW-RT6-10d-A-CALLBACK-ISOLATION:BEGIN" in text,
                 f"Control A contract missing from {relative}")
        _require("FW-RT6-10d aggregate tasks: 0 / 6 CLOSED" in text,
                 f"aggregate boundary missing from {relative}")
        _require("Control B" in text and "NOT_AUTHORIZED" in text,
                 f"later-control boundary missing from {relative}")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split(
        "## FW-RT6-10d — Callback and plugin isolation",
        1,
    )[1].split("## FW-RT6-11a", 1)[0]
    _require(section.count("- [ ]") == 6, "FW-RT6-10d task count drifted")
    _require(section.count("- [x]") == 0, "Control A closed aggregate tasks")
    print("[OK] documentation and 0 / 6 aggregate task boundary conform")


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
    check_policy_and_dispatch_contract()
    check_runtime_deferral_and_privacy()
    check_docs_and_task_boundary()
    print("v600_rt6_10d_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10d_control_a_exact_surface: 5 files")
    print("v600_rt6_10d_explicit_package: framework.callback_isolation / PASS")
    print("v600_rt6_10d_public_callback_failure: ISOLATED / CONTINUE")
    print("v600_rt6_10d_plugin_hook_failure: ISOLATED / CONTINUE")
    print("v600_rt6_10d_motion_hook_failure: SKIP_MOTION / RUNTIME_CONTINUES")
    print("v600_rt6_10d_stage_criticality: 2 CRITICAL / 2 NON_CRITICAL")
    print("v600_rt6_10d_session_lock_during_callback: FORBIDDEN_BY_CONTRACT")
    print("v600_rt6_10d_reentrant_deadlock: False / REFERENCE_PASS")
    print("v600_rt6_10d_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_10d_task_count: 0 / 6 CLOSED")
    print("v600_rt6_10d_control_b: NOT_AUTHORIZED")
    print("v600_rt6_10d_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10d_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10d Control A callback/plugin isolation contract gate passed")


if __name__ == "__main__":
    main()
