"""FW-RT6-9b Control A duplicate/race ordering contract gate."""

from __future__ import annotations

import argparse
from dataclasses import fields
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "8165d0c9eaf132f3a9008e9f56e01d4dd9a3646f"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/interrupt_ordering.py",
    "scripts/smoke_v600_interrupt_ordering_control_a.py",
    "tests/test_interrupt_ordering_control_a.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "DEFAULT_INTERRUPT_ORDERING_POLICY",
    "InterruptAdmissionOutcome",
    "InterruptOrderingDecision",
    "InterruptOrderingKey",
    "InterruptOrderingPolicy",
    "InterruptOrderingRule",
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
        "unexpected FW-RT6-9b Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-9b Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.interrupt_ordering' not in sys.modules; "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] root import remains lazy and ordering names stay explicit-only")


def check_model_contract() -> None:
    _run("-m", "unittest", "tests.test_interrupt_ordering_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.interrupt_ordering as ordering
    from framework.output_control import InterruptRequest, InterruptResult

    _require(
        tuple(ordering.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "interrupt ordering explicit-package exports changed",
    )
    policy = ordering.DEFAULT_INTERRUPT_ORDERING_POLICY
    _require(not policy.request_id_required, "interrupt request ID was invented")
    _require(
        policy.idempotency_key_fields == ("session_id", "resolved_turn_id"),
        "turn idempotency key changed",
    )
    _require(
        tuple(item.name for item in fields(InterruptRequest))[-1:] == (
            "timeout_seconds",
        ),
        "accepted InterruptRequest fields changed",
    )
    _require(
        tuple(item.name for item in fields(InterruptResult))[-1:] == (
            "motion_result",
        ),
        "accepted InterruptResult dataclass fields changed",
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
    runtime_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    _require(
        "interrupt_ordering" not in runtime_source,
        "runtime ordering was adopted before Control B",
    )
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] turn-key policy and truthful ordering decisions conform")
    print("[OK] root-public/version/runtime compatibility remains unchanged")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-9b-A-INTERRUPT-ORDERING" in text,
            f"missing Control A marker: {relative}",
        )
        for phrase in (
            "public interrupt request ID introduced: False",
            "idempotency key: (session_id, resolved_turn_id)",
            "duplicate result: REPLAY OWNER TERMINAL RESULT",
            "multiple turn terminal events: False",
            "runtime adoption: DEFERRED TO CONTROL B",
            "FW-RT6-9b aggregate tasks: 0 / 7 CLOSED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")
    print("[OK] duplicate identity and five deterministic race rules are documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_model_contract()
    check_docs()
    print("v600_rt6_9b_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9b_control_a_exact_surface: 5 files")
    print("v600_rt6_9b_explicit_package: framework.interrupt_ordering / PASS")
    print("v600_rt6_9b_public_interrupt_request_id: False / PASS")
    print("v600_rt6_9b_idempotency_key: session+resolved-turn / PASS")
    print("v600_rt6_9b_duplicate_policy: REPLAY_OWNER_TERMINAL_RESULT / PASS")
    print("v600_rt6_9b_normal_completion_race: FIXED / PASS")
    print("v600_rt6_9b_close_race: FIXED / PASS")
    print("v600_rt6_9b_flush_race: FIXED / PASS")
    print("v600_rt6_9b_new_turn_during_interrupt: TYPED_REJECT / PASS")
    print("v600_rt6_9b_multiple_turn_terminal_events: False / CONTRACT")
    print("v600_rt6_9b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9b_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9b_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9b_runtime_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_9b_task_count: 0 / 7 CLOSED")
    print("v600_rt6_9b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_9c: NOT_AUTHORIZED")
    print("v600_rt6_9b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9b Control A interrupt ordering contract gate passed")


if __name__ == "__main__":
    main()
