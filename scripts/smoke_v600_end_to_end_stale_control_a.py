"""FW-RT6-9d Control A atomic stale-delivery ingress gate."""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_HEAD = "9bb6571d3c29a2c5be444cc1b6a49a3ef94225ef"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime_generation_gate.py",
    "scripts/smoke_v600_end_to_end_stale_control_a.py",
    "tests/test_end_to_end_stale_control_a.py",
}
EXPECTED_DIAGNOSTIC_KEYS = {
    "generation_start_count",
    "generation_advance_count",
    "accepted_completion_count",
    "stale_completion_count",
    "active_generation_count",
    "registry_size",
}
EXPECTED_STAGES = (
    "text_generation_delta",
    "voice_input_transcript",
    "voice_output_artifact",
    "motion_completion",
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
        "unexpected FW-RT6-9d Control A baseline",
    )
    _require(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact five-file FW-RT6-9d Control A surface conform")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def check_import_contract() -> None:
    code = (
        "import sys, framework; "
        "assert not hasattr(framework, 'RealtimeGenerationGate'); "
        "assert not hasattr(framework, 'RealtimeStageCompletionEnvelope'); "
        "assert len(framework.__all__) == 127; "
        "assert 'pyvts' not in sys.modules; "
        "assert 'websockets' not in sys.modules"
    )
    _run("-c", code)
    print("[OK] generation gate names remain absent from the root-public surface")


def check_atomic_ingress_contract() -> None:
    _run("-m", "unittest", "tests.test_end_to_end_stale_control_a")

    sys.path.insert(0, str(PROJECT_ROOT))
    import framework
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
        RealtimeStageCompletionEnvelope,
    )

    signature = inspect.signature(RealtimeGenerationGate.apply_completion)
    _require(
        tuple(signature.parameters) == ("self", "envelope", "deliver"),
        "atomic ingress signature drifted",
    )
    _require(
        signature.parameters["deliver"].kind
        is inspect.Parameter.KEYWORD_ONLY,
        "deliver must remain keyword-only",
    )
    _require(
        set(RealtimeGenerationGate().diagnostics) == EXPECTED_DIAGNOSTIC_KEYS,
        "generation diagnostics keys changed",
    )

    for stage in EXPECTED_STAGES:
        gate = RealtimeGenerationGate()
        generation_id = gate.start_generation("turn-a")
        gate.advance(GenerationAdvanceReason.INTERRUPT)
        delivered = []
        decision = gate.apply_completion(
            RealtimeStageCompletionEnvelope(
                turn_id="turn-a",
                generation_id=generation_id,
                stage=stage,
                value=stage,
            ),
            deliver=delivered.append,
        )
        _require(not decision.accepted, f"stale stage was accepted: {stage}")
        _require(not delivered, f"stale stage was delivered: {stage}")
        _require(
            decision.retired_by is GenerationAdvanceReason.INTERRUPT,
            f"retirement reason was lost: {stage}",
        )
        _require(
            gate.diagnostics["stale_completion_count"] == 1,
            f"stale count was not recorded: {stage}",
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
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] atomic check/application, stale count, and reason retention conform")
    print("[OK] root-public/version/provider isolation remains unchanged")


def check_control_boundary() -> None:
    runtime_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    _require(
        "_generation_gate.apply_completion(" in runtime_source,
        "accepted atomic ingress is not adopted by Control B",
    )
    owner_sources = {
        "text_generation_delta": "framework/realtime_text_generation.py",
        "voice_input_transcript": "framework/voice_input_session.py",
        "voice_output_artifact": "framework/_realtime_voice_output_control.py",
        "motion_completion": "framework/motion_session.py",
    }
    for stage, relative in owner_sources.items():
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            ".apply_completion(" in source and f'stage="{stage}"' in source,
            f"Control B owner adoption is incomplete: {stage}",
        )
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-9d", 1)[1].split("## FW-RT6-10a", 1)[0]
    _require(section.count("- [ ]") == 6, "Control B closed an aggregate task")
    print("[OK] accepted Control A primitive remains intact after Control B adoption")


def check_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            text.count("FW-RT6-9d-A-ATOMIC-DELIVERY-INGRESS:BEGIN") == 1,
            f"missing or duplicate Control A begin marker: {relative}",
        )
        _require(
            text.count("FW-RT6-9d-A-ATOMIC-DELIVERY-INGRESS:END") == 1,
            f"missing or duplicate Control A end marker: {relative}",
        )
        for phrase in (
            "existing freshness owner reused",
            "generation diagnostics keys changed: False",
            "FW-RT6-9d aggregate tasks: 0 / 6 CLOSED",
            "Control B runtime adoption: NOT_AUTHORIZED",
            "FW-RT6-10a implementation: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing contract phrase in {relative}: {phrase}")
    print("[OK] owner reuse, diagnostics, and later-scope boundaries are documented")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_repository_contract()
    check_import_contract()
    check_atomic_ingress_contract()
    check_control_boundary()
    check_docs()
    print("v600_rt6_9d_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9d_control_a_exact_surface: 5 files")
    print("v600_rt6_9d_freshness_owner: RealtimeGenerationGate / REUSED")
    print("v600_rt6_9d_atomic_delivery_ingress: PASS")
    print("v600_rt6_9d_stage_vocabulary: 4 / PASS")
    print("v600_rt6_9d_retired_delivery: False / PASS")
    print("v600_rt6_9d_stale_count_reason: RETAINED / PASS")
    print("v600_rt6_9d_generation_diagnostics_keys: UNCHANGED")
    print("v600_rt6_9d_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_9d_realtime_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_9d_motion_api_version: 5.5.0 / UNCHANGED")
    print("v600_rt6_9d_runtime_adoption: ADOPTED_BY_CONTROL_B")
    print("v600_rt6_9d_task_count: 0 / 6 CLOSED")
    print("v600_rt6_9d_control_b: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10a: NOT_AUTHORIZED")
    print("v600_rt6_9d_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9d Control A atomic stale-delivery gate passed")


if __name__ == "__main__":
    main()
