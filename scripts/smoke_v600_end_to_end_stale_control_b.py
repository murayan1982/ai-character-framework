"""FW-RT6-9d Control B end-to-end stale-delivery runtime gate."""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "d01476a02586940dc7950ae18f7c8f2e96f706fe"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/_realtime_voice_output_control.py",
    "framework/motion_session.py",
    "framework/realtime_session.py",
    "framework/realtime_text_generation.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_end_to_end_stale_control_a.py",
    "scripts/smoke_v600_end_to_end_stale_control_b.py",
    "tests/test_end_to_end_stale_control_b.py",
}
OWNER_SOURCES = {
    "text_generation_delta": "framework/realtime_text_generation.py",
    "voice_input_transcript": "framework/voice_input_session.py",
    "voice_output_artifact": "framework/_realtime_voice_output_control.py",
    "motion_completion": "framework/motion_session.py",
}
EXPECTED_DIAGNOSTIC_KEYS = {
    "generation_start_count",
    "generation_advance_count",
    "accepted_completion_count",
    "stale_completion_count",
    "active_generation_count",
    "registry_size",
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
    paths = {
        line.replace("\\", "/")
        for line in _git(
            "-c",
            "core.safecrlf=false",
            "diff",
            "HEAD",
            "--name-only",
        ).splitlines()
        if line.strip()
    }
    paths.update(
        line.replace("\\", "/")
        for line in _git("ls-files", "--others", "--exclude-standard").splitlines()
        if line.strip()
    )
    return paths


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-9d Control B baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main is not the accepted Control A baseline",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        (
            "unexpected Control B surface; "
            f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}"
        ),
    )
    print("[OK] baseline and exact ten-file FW-RT6-9d Control B surface conform")


def check_owner_source_contract() -> None:
    for stage, relative in OWNER_SOURCES.items():
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            ".apply_completion(" in source,
            f"atomic application is missing from {relative}",
        )
        _require(
            f'stage="{stage}"' in source,
            f"exact delivery label is missing: {stage}",
        )
        _require(
            ".admit_completion(" not in source,
            f"split admission remains in Control B owner: {relative}",
        )

    session_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    _require(
        "self._generation_gate.apply_completion(" in session_source,
        "RealtimeSession central ingress did not adopt atomic application",
    )
    _require(
        'stage="motion_completion"' in session_source,
        "RealtimeSession motion lifecycle label drifted",
    )

    text_source = (PROJECT_ROOT / "framework/realtime_text_generation.py").read_text(
        encoding="utf-8"
    )
    _require(
        "generation_gate: RealtimeGenerationGate | None = None" in text_source,
        "text stream optional common-gate composition is missing",
    )
    _require(
        "self._next_delta_index += 1" in text_source,
        "text delta bounded state application is missing",
    )

    input_source = (PROJECT_ROOT / "framework/voice_input_session.py").read_text(
        encoding="utf-8"
    )
    _require(
        "GenerationAdvanceReason.SESSION_CLOSED" in input_source,
        "voice-input close does not retire its in-flight generation",
    )

    voice_source = (
        PROJECT_ROOT / "framework/_realtime_voice_output_control.py"
    ).read_text(encoding="utf-8")
    _require(
        "deliver=lambda delivered: self._bind_result_artifact(" in voice_source,
        "voice artifact binding is outside atomic application",
    )

    motion_source = (PROJECT_ROOT / "framework/motion_session.py").read_text(
        encoding="utf-8"
    )
    _require(
        "def _apply_motion_completion(" in motion_source,
        "motion completion owner did not adopt atomic application",
    )
    print("[OK] four existing delivery owners use the exact atomic ingress labels")


def check_runtime_contract() -> None:
    _run("-m", "unittest", "tests.test_end_to_end_stale_control_b")
    _run("scripts/smoke_v600_end_to_end_stale_control_a.py", "--source-only")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.realtime_generation_gate import RealtimeGenerationGate
    from framework.realtime_text_generation import ProviderNeutralTextGenerationStream

    signature = inspect.signature(ProviderNeutralTextGenerationStream)
    _require(
        "generation_gate" in signature.parameters,
        "text stream common generation-gate composition is missing",
    )
    _require(
        signature.parameters["generation_gate"].default is None,
        "standalone text stream compatibility changed",
    )
    _require(
        set(RealtimeGenerationGate().diagnostics) == EXPECTED_DIAGNOSTIC_KEYS,
        "generation diagnostics keys changed",
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
    _require(
        not hasattr(framework.RealtimeSession, "reset"),
        "FW-RT6-10a reset API escaped into Control B",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] current/stale/race behavior and accepted Control A regression conform")
    print("[OK] root-public/version/provider isolation remains unchanged")


def check_root_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.realtime_text_generation' not in sys.modules; "
        "assert not hasattr(framework, 'RealtimeGenerationGate'); "
        "assert len(framework.__all__) == 127"
    )
    _run("-c", code)
    print("[OK] text package remains lazy and generation-gate names stay explicit-only")


def check_docs_and_scope() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            text.count("FW-RT6-9d-B-RUNTIME-ADOPTION:BEGIN") == 1,
            f"missing or duplicate Control B begin marker: {relative}",
        )
        _require(
            text.count("FW-RT6-9d-B-RUNTIME-ADOPTION:END") == 1,
            f"missing or duplicate Control B end marker: {relative}",
        )
        for phrase in (
            "exact Control B surface: 10 files",
            "focused Control B tests: 14 / PASS",
            "full Framework unit suite: 493 / PASS",
            "FW-RT6-9d aggregate tasks: 0 / 6 CLOSED",
            "Control B acceptance sync: NOT_AUTHORIZED",
            "FW-RT6-10a implementation: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-9d", 1)[1].split("## FW-RT6-10a", 1)[0]
    _require(section.count("- [ ]") == 6, "Control B closed an aggregate task")
    print("[OK] tasklist, acceptance-sync, Control C, and FW-RT6-10a boundaries hold")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_owner_source_contract()
    check_root_import_contract()
    check_runtime_contract()
    check_docs_and_scope()

    print("v600_rt6_9d_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9d_control_b_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9d_control_b_exact_surface: 10 files")
    print("v600_rt6_9d_delivery_owner_count: 4 / PASS")
    print("v600_rt6_9d_atomic_text_delta: PASS")
    print("v600_rt6_9d_atomic_voice_input_transcript: PASS")
    print("v600_rt6_9d_atomic_voice_output_artifact: PASS")
    print("v600_rt6_9d_atomic_motion_completion: PASS")
    print("v600_rt6_9d_stale_count_reason: RETAINED / PASS")
    print("v600_rt6_9d_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9d_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9d_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9d_task_count: 0 / 6 CLOSED")
    print("v600_rt6_9d_control_b_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_9d_control_c: NOT_AUTHORIZED")
    print("v600_rt6_10a: NOT_AUTHORIZED")
    print("v600_rt6_9d_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9d Control B end-to-end stale-delivery gate passed")


if __name__ == "__main__":
    main()
