"""FW-RT6-10d Control B callback/plugin runtime-adoption gate."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "5fd2f84b74a769d9158ca7785f98e3ea88f42a5a"
EXPECTED_SURFACE = {
    "core/events.py",
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/facade.py",
    "framework/motion_session.py",
    "framework/realtime_session.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_callback_isolation_control_b.py",
    "tests/test_callback_isolation_control_b.py",
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


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-10d Control B baseline",
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
    print("[OK] baseline and exact nine-file FW-RT6-10d Control B surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_and_public_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.callback_isolation' not in sys.modules; "
        "assert not hasattr(framework, 'CallbackIsolationPolicy'); "
        "assert len(framework.__all__) == 127; "
        "assert framework.RealtimeSessionInfo().api_version == '5.2.0'; "
        "assert framework.MotionSessionInfo().api_version == '5.5.0'"
    )
    _run("-c", code)
    print("[OK] root import stays lazy and isolation names remain explicit-only")


def check_runtime_adoption() -> None:
    _run("-m", "unittest", "tests.test_callback_isolation_control_b")

    expected = {
        "core/events.py": (
            "dispatch_isolated_callbacks_async",
            "CallbackBoundary.PLUGIN_HOOK",
        ),
        "framework/facade.py": (
            "dispatch_isolated_callbacks",
            "stage_criticality",
        ),
        "framework/voice_input_session.py": (
            "dispatch_isolated_callbacks",
            "_release_save",
        ),
        "framework/motion_session.py": (
            "dispatch_isolated_callbacks",
            "_callback_failure_count",
        ),
        "framework/realtime_session.py": (
            "_callback_delivery_window",
            "_isolated_stage_failure_envelope",
            "_callback_window_condition",
        ),
    }
    for relative, markers in expected.items():
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for marker in markers:
            _require(marker in source, f"runtime adoption missing: {relative}: {marker}")

    policy_source = (PROJECT_ROOT / "framework/callback_isolation.py").read_text(
        encoding="utf-8"
    )
    _require(
        "FW-RT6-10d Control A defines" in policy_source,
        "accepted Control A policy owner drifted",
    )
    print("[OK] text, voice-input, motion, realtime, and plugin adopters conform")
    print("[OK] callback failures continue stable delivery without corrupting success")
    print("[OK] public callbacks run lock-free and accepted reentrant paths do not deadlock")
    print("[OK] critical/non-critical stage exceptions become public-safe typed results")
    print("[OK] close cleanup failures stay truthful while sessions remain closed")


def check_privacy_and_boundaries() -> None:
    for relative in EXPECTED_SURFACE:
        if not relative.startswith(("core/", "framework/")):
            continue
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8").lower()
        for forbidden_import in (
            "import openai",
            "import websocket",
            "import pyvts",
            "import pyaudio",
            "import sounddevice",
        ):
            _require(
                forbidden_import not in source,
                f"provider/runtime import escaped: {relative}: {forbidden_import}",
            )

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split(
        "## FW-RT6-10d — Callback and plugin isolation",
        1,
    )[1].split("## FW-RT6-11a", 1)[0]
    _require(section.count("- [ ]") == 6, "FW-RT6-10d task count drifted")
    _require(section.count("- [x]") == 0, "Control B closed aggregate tasks")
    _require(
        not (PROJECT_ROOT / "scripts/check_v600_callback_isolation_acceptance.py").exists(),
        "Control C acceptance gate escaped into Control B",
    )
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("FW-RT6-10d-B-RUNTIME-ISOLATION:BEGIN" in text,
                 f"Control B contract missing from {relative}")
        _require("FW-RT6-10d aggregate tasks: 0 / 6 CLOSED" in text,
                 f"aggregate boundary missing from {relative}")
        _require("Control C" in text and "NOT_AUTHORIZED" in text,
                 f"later-control boundary missing from {relative}")
    print("[OK] provider/private data isolation and later-control boundaries conform")
    print("[OK] FW-RT6-10d aggregate tasks remain 0 / 6 closed")


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
    check_import_and_public_contract()
    check_runtime_adoption()
    check_privacy_and_boundaries()
    print("v600_rt6_10d_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10d_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10d_control_b_exact_surface: 9 files")
    print("v600_rt6_10d_isolation_owner: framework.callback_isolation / REUSED")
    print("v600_rt6_10d_event_owner: RealtimeEventHub / REUSED")
    print("v600_rt6_10d_public_callback_failure: ISOLATED / CONTINUE")
    print("v600_rt6_10d_plugin_hook_failure: ISOLATED / SYNC+ASYNC CONTINUE")
    print("v600_rt6_10d_session_lock_during_callback: False / PASS")
    print("v600_rt6_10d_reentrant_deadlock: False / PASS")
    print("v600_rt6_10d_stage_failure: TYPED / CRITICALITY_APPLIED")
    print("v600_rt6_10d_close_cleanup_truth: RETAINED / PASS")
    print("v600_rt6_10d_task_count: 0 / 6 CLOSED")
    print("v600_rt6_10d_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10d_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10d Control B callback/plugin runtime-adoption gate passed")


if __name__ == "__main__":
    main()
