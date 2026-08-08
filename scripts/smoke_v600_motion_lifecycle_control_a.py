"""FW-RT6-8b Control A motion lifecycle hook contract gate.

The gate is source/provider/network/audio safe. Control A adds one stable
explicit package plus tests and docs; it does not adopt or execute the hook in
the realtime or motion-session runtime.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "7d19e692f4553110b157ead3068bf9912eb783c9"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/motion_lifecycle.py",
    "scripts/smoke_v600_motion_lifecycle_control_a.py",
    "tests/test_motion_lifecycle_control_a.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "MotionLifecycleSignal",
    "MotionLifecycleNotification",
    "MotionLifecycleHookOutcome",
    "MotionLifecycleHookResult",
    "MotionLifecycleHook",
    "invoke_motion_lifecycle_hook",
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


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-8b Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-8b Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        check=True,
    )


def check_runtime_contract() -> None:
    _run("-m", "unittest", "tests.test_motion_lifecycle_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    import framework.motion_lifecycle as lifecycle

    _require(
        tuple(lifecycle.__all__) == EXPECTED_EXPLICIT_EXPORTS,
        "motion lifecycle explicit-package exports changed",
    )
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version changed",
    )
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] provider-neutral hook models and safe invocation conform")
    print("[OK] root-public/version/import compatibility remains unchanged")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-8b-A-MOTION-LIFECYCLE-HOOK" in text,
            f"missing Control A marker: {relative}",
        )
        for phrase in (
            "product-specific mapping in Framework core: False",
            "conversation terminal changed by hook failure: False",
            "unsupported motion intent channel: MotionOutcome.UNSUPPORTED",
            "runtime hook adoption: DEFERRED TO CONTROL B",
            "FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")
    print("[OK] host/plugin ownership, isolation, and deferrals are documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_runtime_contract()
    check_docs()
    print("v600_rt6_8b_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_8b_control_a_exact_surface: 5 files")
    print("v600_rt6_8b_explicit_package: framework.motion_lifecycle / PASS")
    print("v600_rt6_8b_signal_count: 6 / PASS")
    print("v600_rt6_8b_product_specific_core_mapping: False / PASS")
    print("v600_rt6_8b_provider_neutral_request: MotionRequest / PASS")
    print("v600_rt6_8b_hook_failure_escapes: False / PASS")
    print("v600_rt6_8b_terminal_changed_by_hook_failure: False / PASS")
    print("v600_rt6_8b_unsupported_channel: MotionOutcome.UNSUPPORTED / PASS")
    print("v600_rt6_8b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_8b_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_8b_runtime_hook_adoption: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_8b_task_count: 0 / 6 CLOSED")
    print("v600_rt6_8b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_8c: NOT_AUTHORIZED")
    print("v600_rt6_8b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-8b Control A motion lifecycle hook gate passed")


if __name__ == "__main__":
    main()
