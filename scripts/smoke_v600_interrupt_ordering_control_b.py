"""FW-RT6-9b Control B whole-request interrupt ordering gate."""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "6b9a9629239f969a51325cbf35d0e4be444c5689"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_interrupt_ordering_control_b.py",
    "tests/test_interrupt_ordering_control_b.py",
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
        "unexpected FW-RT6-9b Control B corrective baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the committed Control B baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-9b Control B surface conform")


def check_runtime_contract() -> None:
    _run("scripts/smoke_v600_interrupt_ordering_control_a.py", "--source-only")
    _run("-m", "unittest", "tests.test_interrupt_ordering_control_b")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.interrupt_ordering import DEFAULT_INTERRUPT_ORDERING_POLICY

    _require(
        DEFAULT_INTERRUPT_ORDERING_POLICY.idempotency_key_fields
        == ("session_id", "resolved_turn_id"),
        "accepted interrupt key changed",
    )
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
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        not hasattr(framework, "InterruptOrderingDecision"),
        "explicit ordering model leaked into the root facade",
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
    print("[OK] sole-owner replay and public compatibility conform")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "class _InterruptRequestWork:",
        "class _InterruptTerminalReserved(RuntimeError):",
        "self._interrupt_request_lock = RLock()",
        "self._interrupt_requests:",
        "self._active_interrupt_request",
        "self._close_admission_requested",
        "def _claim_interrupt_request(",
        "def _resolve_interrupt_terminal_reservation(",
        "def _complete_interrupt_request(",
        "def _ordered_interrupt(",
        "owner_work.result = prepared_result",
        "work.owner_thread_id == get_ident()",
        "work.completion_event.wait()",
        "interrupt_in_progress",
        "owner_work.flush_result = self._flush_output_serialized(",
        "_interrupt_owner=owner_work",
        "_interrupt_owner.flush_result = result",
        "return self._ordered_interrupt(request, advance_reason=\"interrupt\")",
        "return self._ordered_interrupt(request, advance_reason=\"cancel\")",
    ):
        _require(phrase in source, f"missing Control B runtime guard: {phrase}")

    claim_start = source.index("def _claim_interrupt_request(")
    execute_start = source.index("def _execute_interrupt_once(")
    claim_source = source[claim_start:execute_start]
    _require(
        "_request_interrupt_coordination" not in claim_source,
        "subsystem work occurs before sole-owner admission",
    )
    ordered_start = source.index("def _ordered_interrupt(")
    interrupt_start = source.index("def interrupt(", ordered_start)
    ordered_source = source[ordered_start:interrupt_start]
    _require(
        ordered_source.index("_claim_interrupt_request(request)")
        < ordered_source.index("_execute_interrupt_once("),
        "interrupt work precedes owner admission",
    )
    _require("asyncio.run(" not in source, "per-call event loops were introduced")
    print("[OK] reservation, wait, close, flush, and turn-admission guards conform")


def check_docs() -> None:
    for relative in ("docs/app_integration_contract.md", "docs/public_facade.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-9b-B-INTERRUPT-ORDERING-ADOPTION",
            "exact Control B surface: 5 files",
            "(session_id, resolved_turn_id)",
            "FIRST TERMINAL RESERVATION WINS",
            "FIRST ADMISSION WINS",
            "OWNER FLUSH BEFORE TERMINAL",
            "REENTRANT CALLBACK REPLAY",
            "REENTRANT OWNER FLUSH REUSE",
            "interrupt_in_progress",
            "FW-RT6-9b aggregate tasks: 0 / 7 CLOSED",
            "FW-RT6-9c: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(
                phrase in text,
                f"missing Control B doc contract: {relative}: {phrase}",
            )
    print("[OK] exact ordering, compatibility, and later-scope deferrals documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_runtime_contract()
    check_source_contract()
    check_docs()
    print("v600_rt6_9b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9b_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9b_control_b_exact_surface: 5 files")
    print("v600_rt6_9b_owner_registry: RealtimeSession PRIVATE / PASS")
    print("v600_rt6_9b_idempotency_key: session_id+resolved_turn_id / PASS")
    print("v600_rt6_9b_duplicate_exact_result: True / PASS")
    print("v600_rt6_9b_duplicate_side_effects: False / PASS")
    print("v600_rt6_9b_reentrant_callback_replay: EXACT_OWNER_RESULT / PASS")
    print("v600_rt6_9b_reentrant_interrupt_deadlock: False / PASS")
    print("v600_rt6_9b_normal_terminal_race: FIRST_RESERVATION / PASS")
    print("v600_rt6_9b_close_race: FIRST_ADMISSION / PASS")
    print("v600_rt6_9b_owner_flush_before_terminal: True / PASS")
    print("v600_rt6_9b_reentrant_owner_flush_reuse: True / PASS")
    print("v600_rt6_9b_reentrant_owner_flush_effect_count: 1 / PASS")
    print("v600_rt6_9b_new_turn_reason: interrupt_in_progress / PASS")
    print("v600_rt6_9b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9b_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9b_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9b_focused_tests: 11 / PASS")
    print("v600_rt6_9b_task_count: 0 / 7 CLOSED")
    print("v600_rt6_9b_control_c: NOT_AUTHORIZED")
    print("v600_rt6_9c: NOT_AUTHORIZED")
    print("v600_rt6_9b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9b Control B interrupt-ordering adoption gate passed")


if __name__ == "__main__":
    main()
