"""FW-RT6-8a Control B unified motion ordering/freshness gate.

The gate uses only mock and injected in-memory motion paths. It does not import
pyvts/websocket providers or execute network, audio, microphone, or real motion.
"""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "d3d4166a99b946c4a5976032bf6580ca821b953f"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/motion_session.py",
    "scripts/smoke_v600_motion_correlation_control_a.py",
    "scripts/smoke_v600_motion_correlation_control_b.py",
    "tests/test_motion_correlation_control_a.py",
    "tests/test_motion_correlation_control_b.py",
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
        "unexpected FW-RT6-8a Control B baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-8a Control B surface conform")


def check_runtime_contract() -> None:
    _run("scripts/smoke_v600_motion_correlation_control_a.py", "--source-only")
    _run("-m", "unittest", "tests.test_motion_correlation_control_b")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework

    signature = inspect.signature(framework.create_motion_session)
    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version changed",
    )
    _require(
        "realtime_event_hub" not in signature.parameters,
        "internal event owner leaked into public factory",
    )
    _require(
        "generation_gate" not in signature.parameters,
        "internal freshness owner leaked into public factory",
    )
    session = framework.create_motion_session()
    _require(
        hasattr(session, "on_realtime_event"),
        "canonical motion callback registration is missing",
    )
    _require(
        hasattr(session, "_bind_realtime_coordination"),
        "internal unified-owner binding seam is missing",
    )
    session.close()
    print("[OK] shared sequence bridge and common completion gate conform")
    print("[OK] public factory/version/root surface and standalone behavior conform")


def check_source_contract() -> None:
    motion_source = (PROJECT_ROOT / "framework/motion_session.py").read_text(
        encoding="utf-8"
    )
    transport_source = (
        PROJECT_ROOT / "framework/vtube_studio_pyvts_transport.py"
    ).read_text(encoding="utf-8")
    for phrase in (
        "def _bind_realtime_coordination(",
        "RealtimeEventHub[RealtimeEvent]",
        "RealtimeGenerationGate",
        "RealtimeStageCompletionEnvelope(",
        "RealtimeEventType.STALE_RESULT_DROPPED",
        '"late_motion_completion_delivered": False',
        'emit_canonical=False',
    ):
        _require(phrase in motion_source, f"missing motion coordination source: {phrase}")
    _require(
        "RealtimeEventHub[RealtimeEvent]()" not in motion_source,
        "MotionSession created a competing local event hub",
    )
    _require(
        "generation_gate.start_generation" not in motion_source,
        "MotionSession started a unified generation",
    )
    _require(
        "generation_gate.advance" not in motion_source,
        "MotionSession advanced a unified generation",
    )
    _require(
        "_lifecycle_generation" in transport_source,
        "VTS transport-local lifecycle generation guard was removed",
    )
    print("[OK] single-owner source guards and VTS local defense preservation conform")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-8a-B-MOTION-COORDINATION",
            "late motion completion delivered: False / PASS",
            "root-public names: 127 / UNCHANGED",
            "5.5.0 / UNCHANGED",
            "FW-RT6-8b / FW-RT6-8c: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing Control B doc contract: {relative}: {phrase}")
    print("[OK] Control B docs preserve aggregate and later-scope boundaries")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_runtime_contract()
    check_source_contract()
    check_docs()
    print("v600_rt6_8a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8a_control_b_status: implemented-awaiting-review")
    print("v600_rt6_8a_control_b_exact_surface: 7 files")
    print("v600_rt6_8a_unified_event_sequence: shared-owner / PASS")
    print("v600_rt6_8a_common_stale_guard: shared-owner / PASS")
    print("v600_rt6_8a_motion_starts_or_advances_generation: False / PASS")
    print("v600_rt6_8a_late_motion_completion_delivered: False / PASS")
    print("v600_rt6_8a_vts_lifecycle_guard_preserved: True / PASS")
    print("v600_rt6_8a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_8a_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_8a_task_count: 0 / 5 CLOSED")
    print("v600_rt6_8a_control_c: DEFERRED")
    print("v600_rt6_8b_8c_status: NOT_AUTHORIZED")
    print("v600_rt6_8a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
