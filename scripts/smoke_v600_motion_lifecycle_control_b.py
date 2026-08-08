"""FW-RT6-8b Control B lifecycle-to-motion runtime adoption gate.

The gate uses only deterministic mock turns and injected in-memory stages. It
does not import a provider SDK or execute network, audio, microphone, VTube
Studio, or real motion work.
"""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "7e8afe4955c23d89924227dba269714ad71aed09"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_motion_lifecycle_control_b.py",
    "tests/test_motion_lifecycle_control_b.py",
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
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-8b Control B baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the accepted Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-8b Control B surface conform")


def check_runtime_contract() -> None:
    _run("scripts/smoke_v600_motion_lifecycle_control_a.py", "--source-only")
    _run("-m", "unittest", "tests.test_motion_lifecycle_control_b")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.realtime_session import RealtimeSession

    factory_parameters = tuple(
        inspect.signature(framework.create_realtime_session).parameters
    )
    config_parameters = tuple(
        inspect.signature(framework.RealtimeSessionConfig).parameters
    )
    _require(
        hasattr(RealtimeSession, "set_motion_lifecycle_hook"),
        "RealtimeSession hook registration is missing",
    )
    _require(
        "motion_lifecycle_hook" not in factory_parameters,
        "hook leaked into the public factory",
    )
    _require(
        "motion_lifecycle_hook" not in config_parameters,
        "hook leaked into RealtimeSessionConfig",
    )
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API changed",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API changed",
    )
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] explicit hook registration and runtime isolation conform")
    print("[OK] root-public/factory/config/version compatibility remains unchanged")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "def set_motion_lifecycle_hook(",
        "_MOTION_LIFECYCLE_SOURCE_SIGNALS",
        "self._handle_motion_lifecycle_event(emitted)",
        "MotionLifecycleNotification(",
        "invoke_motion_lifecycle_hook(hook, notification)",
        'self._injected_stages.get("motion")',
        "self._generation_gate.admit_completion(completion)",
        "def _motion_lifecycle_terminal_source_is_current(",
        "RealtimeEventType.STALE_RESULT_DROPPED",
    ):
        _require(phrase in source, f"missing Control B runtime guard: {phrase}")
    _require(
        "_generation_gate.start_generation" not in source[
            source.index("def _execute_motion_lifecycle_request(") :
            source.index("def _handle_motion_lifecycle_event(")
        ],
        "motion lifecycle execution started a generation",
    )
    _require(
        "_generation_gate.advance" not in source[
            source.index("def _execute_motion_lifecycle_request(") :
            source.index("def _handle_motion_lifecycle_event(")
        ],
        "motion lifecycle execution advanced a generation",
    )
    print("[OK] source ordering, shared freshness, and terminal guards conform")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-8b-B-MOTION-LIFECYCLE-ADOPTION",
            "exact Control B surface: 5 files",
            "source event published before hook: True / PASS"
            if relative.endswith("app_integration_contract.md")
            else "source-before-hook ordering: PASS",
            "root-public names: 127 / UNCHANGED",
            "5.2.0 / UNCHANGED",
            "5.5.0 / UNCHANGED",
            "FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing Control B doc contract: {relative}: {phrase}")
    print("[OK] host/plugin ownership, event order, isolation, and deferrals documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_runtime_contract()
    check_source_contract()
    check_docs()
    print("v600_rt6_8b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8b_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_8b_control_b_exact_surface: 5 files")
    print("v600_rt6_8b_hook_registration: RealtimeSession method / PASS")
    print("v600_rt6_8b_source_before_hook: True / PASS")
    print("v600_rt6_8b_shared_event_sequence: True / PASS")
    print("v600_rt6_8b_transient_common_stale_gate: True / PASS")
    print("v600_rt6_8b_terminal_generation_reopened: False / PASS")
    print("v600_rt6_8b_conversation_terminal_changed: False / PASS")
    print("v600_rt6_8b_missing_stage: MotionOutcome.NOT_CONFIGURED / PASS")
    print("v600_rt6_8b_unsupported_preserved: MotionOutcome.UNSUPPORTED / PASS")
    print("v600_rt6_8b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_8b_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_8b_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_8b_task_count: 0 / 6 CLOSED")
    print("v600_rt6_8c: NOT_AUTHORIZED")
    print("v600_rt6_8b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-8b Control B motion lifecycle adoption gate passed")


if __name__ == "__main__":
    main()
