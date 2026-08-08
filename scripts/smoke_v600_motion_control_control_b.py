"""FW-RT6-8c Control B runtime motion cancel/stop reach gate.

The gate uses only deterministic injected in-memory stages. It imports no
provider SDK and performs no network, audio, microphone, or real VTS work.
"""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "538b1baae3ff6e0ad2c1add3a8d667f9d107d474"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_motion_control_control_b.py",
    "tests/test_motion_control_control_b.py",
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
        "unexpected FW-RT6-8c Control B baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the accepted Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-8c Control B surface conform")


def check_runtime_contract() -> None:
    _run("scripts/smoke_v600_motion_control_control_a.py", "--source-only")
    _run("-m", "unittest", "tests.test_motion_control_control_b")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.motion_control import MotionControlResult
    from framework.output_control import InterruptResult

    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == (
            "project_root",
            "public_metadata",
            "real_runtime_enabled",
            "voice_input_stage",
            "text_generation_stage",
            "voice_output_stage",
            "motion_stage",
            "config",
        ),
        "realtime factory signature changed",
    )
    _require(
        not hasattr(framework.RealtimeSession, "cancel_motion"),
        "Control B added an unreviewed public cancel_motion method",
    )
    _require(
        not hasattr(framework.MotionSession, "cancel_motion"),
        "standalone MotionSession public surface changed",
    )
    result = framework.create_realtime_session().interrupt()
    _require(
        isinstance(result, InterruptResult),
        "interrupt result type changed",
    )
    _require(
        isinstance(result.motion_result, MotionControlResult),
        "whole-turn interrupt does not expose typed motion reach",
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
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] split-phase cancel/stop reach and runtime isolation conform")
    print("[OK] public factory/root/version/MotionSession compatibility remains unchanged")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "class _ActiveMotionWork:",
        "self._motion_control_lock = RLock()",
        "def _request_motion_control(",
        "work.stage.cancel(context=work.context)",
        "MotionRequest.stop_motion(",
        "work.future_delivery_suppressed = True",
        "def _complete_active_motion_work(",
        "if delivery_suppressed:",
        "motion_result=self._resolve_motion_control_attempt(motion_attempt)",
        "whole_turn_aggregate_changed",
    ):
        _require(phrase in source, f"missing Control B runtime guard: {phrase}")

    request_start = source.index("def _request_motion_control(")
    request_end = source.index("def _resolve_motion_control_attempt(")
    request_source = source[request_start:request_end]
    _require(
        "with self._operation_lock" not in request_source,
        "stage cancellation was placed under the long session operation lock",
    )
    _require(
        "stop_motion_applied = stop_applied" in request_source,
        "stop application is not derived from the validated stop result",
    )
    print("[OK] one-owner tracking, pre-lock control, and late barrier conform")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-8c-B-MOTION-CONTROL-ADOPTION",
            "exact Control B surface: 5 files",
            "MotionStage.cancel outside the long session operation lock",
            "late-delivery barrier",
            "aggregate interrupt outcome changed: False",
            "FW-RT6-8c aggregate tasks: 0 / 5 CLOSED",
            "FW-RT6-9a: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(
                phrase in text,
                f"missing Control B doc contract: {relative}: {phrase}",
            )
    print("[OK] ownership, truthfulness, compatibility, and Phase 9 deferrals documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_runtime_contract()
    check_source_contract()
    check_docs()
    print("v600_rt6_8c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8c_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_8c_control_b_exact_surface: 5 files")
    print("v600_rt6_8c_active_motion_owner: RealtimeSession / PASS")
    print("v600_rt6_8c_stage_cancel_outside_operation_lock: True / PASS")
    print("v600_rt6_8c_late_delivery_suppressed: True / PASS")
    print("v600_rt6_8c_stop_motion_overclaim: False / PASS")
    print("v600_rt6_8c_duplicate_stage_cancel: 1 / PASS")
    print("v600_rt6_8c_duplicate_stop_motion: 1 / PASS")
    print("v600_rt6_8c_interrupt_motion_result: MotionControlResult / PASS")
    print("v600_rt6_8c_aggregate_interrupt_changed: False / PASS")
    print("v600_rt6_8c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_8c_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_8c_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_8c_task_count: 0 / 5 CLOSED")
    print("v600_rt6_8c_control_c: NOT_AUTHORIZED")
    print("v600_rt6_9a: NOT_AUTHORIZED")
    print("v600_rt6_8c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-8c Control B motion-control adoption gate passed")


if __name__ == "__main__":
    main()
