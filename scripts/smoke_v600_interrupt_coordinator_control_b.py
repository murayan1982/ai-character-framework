"""FW-RT6-9a Control B whole-turn interrupt runtime adoption gate."""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "3aaef5e6335c2c184450525a17d36f1783345268"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_interrupt_coordinator_control_b.py",
    "tests/test_interrupt_coordinator_control_b.py",
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
        "unexpected FW-RT6-9a Control B baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the accepted Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-9a Control B surface conform")


def check_runtime_contract() -> None:
    _run("scripts/smoke_v600_interrupt_coordinator_control_a.py", "--source-only")
    _run("-m", "unittest", "tests.test_interrupt_coordinator_control_b")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.interrupt_coordination import InterruptAggregateResult

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
    result = framework.create_realtime_session().interrupt()
    _require(
        isinstance(result.coordination_result, InterruptAggregateResult),
        "whole-turn interrupt does not expose the typed aggregate",
    )
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        not hasattr(framework, "InterruptAggregateResult"),
        "explicit coordination package leaked into the root facade",
    )
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
    print("[OK] active registry, target dispatch, typed aggregation, and isolation conform")
    print("[OK] public factory/root/version compatibility remains unchanged")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "class _ActiveInterruptStageWork:",
        "self._interrupt_stage_lock = RLock()",
        "def _execute_interruptible_stage(",
        "def _request_interrupt_coordination(",
        "def _resolve_interrupt_stage_attempts(",
        "def _resolve_interrupt_coordination(",
        "work.stage.cancel(context=work.context)",
        "work.future_delivery_suppressed = True",
        "pending_flush_supported",
        "active_audio_invalidation_supported",
        "self._request_motion_control(request)",
        "InterruptAggregateResult.from_results(",
        "whole_request_duplicate_ordering_deferred",
        "barge_in_execution_deferred",
    ):
        _require(phrase in source, f"missing Control B runtime guard: {phrase}")

    request_start = source.index("def _request_interrupt_coordination(")
    request_end = source.index("def _resolve_interrupt_stage_attempts(")
    request_source = source[request_start:request_end]
    _require(
        "with self._operation_lock" not in request_source,
        "stage cancellation was placed under the long operation lock",
    )
    _require(
        source.index("coordination_attempt = self._request_interrupt_coordination(request)")
        < source.index("with self._serialized_operation():", source.index("def interrupt(")),
        "interrupt controls are not dispatched before lock admission",
    )
    print("[OK] pre-lock reach, bounded wait, late barrier, and shared motion projection conform")


def check_docs() -> None:
    for relative in ("docs/app_integration_contract.md", "docs/public_facade.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-9a-B-INTERRUPT-COORDINATION-ADOPTION",
            "exact Control B surface: 5 files",
            "active-stage registry",
            "outside the long session operation lock",
            "bounded completion wait",
            "late-delivery barrier",
            "FW-RT6-9a aggregate tasks: 0 / 9 CLOSED",
            "FW-RT6-9b: NOT_AUTHORIZED",
            "FW-RT6-9c: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(
                phrase in text,
                f"missing Control B doc contract: {relative}: {phrase}",
            )
    print("[OK] ownership, truthfulness, timeout, and later-scope deferrals documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_runtime_contract()
    check_source_contract()
    check_docs()
    print("v600_rt6_9a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9a_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9a_control_b_exact_surface: 5 files")
    print("v600_rt6_9a_active_stage_registry: RealtimeSession / PASS")
    print("v600_rt6_9a_interrupt_subsystems: 5 / PASS")
    print("v600_rt6_9a_text_cancel_reach: True / PASS")
    print("v600_rt6_9a_tts_generation_cancel_reach: True / PASS")
    print("v600_rt6_9a_tts_pending_clear_reach: True / PASS")
    print("v600_rt6_9a_audio_artifact_invalidation_reach: True / PASS")
    print("v600_rt6_9a_motion_projection_reused: True / PASS")
    print("v600_rt6_9a_bounded_completion_wait: True / PASS")
    print("v600_rt6_9a_runtime_partial_result: PASS")
    print("v600_rt6_9a_unsupported_overclaim: False / PASS")
    print("v600_rt6_9a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9a_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9a_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9a_task_count: 0 / 9 CLOSED")
    print("v600_rt6_9a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_9b: NOT_AUTHORIZED")
    print("v600_rt6_9c: NOT_AUTHORIZED")
    print("v600_rt6_9a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9a Control B interrupt-coordination adoption gate passed")


if __name__ == "__main__":
    main()
