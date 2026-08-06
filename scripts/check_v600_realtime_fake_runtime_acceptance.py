"""FW-RT6-3b Control C aggregate deterministic fake-runtime acceptance check.

Offline/mock-safe: validates Control A/B commit history, the exact six-file
Control C docs/test-only surface, deterministic controller and actual
generation-gate/terminal-registry adoption, reproducible race decisions, public
compatibility, truthful aggregate documentation, and frozen version metadata
without provider, network, microphone, playback, real VTube Studio, DRC, or
root-draft stash access.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "5a565afbb19e81f55d35e89486c2327a47d87ab5"
EXPECTED_BASELINE_PARENT = "c3999bd16b2d6104fc90d6282da9a60c84068875"
EXPECTED_BASELINE_SUBJECT = "feat/test: adopt deterministic realtime race harness"

CONTROL_A = EXPECTED_BASELINE_PARENT
CONTROL_A_PARENT = "dc02a13b98cb6fd7a8ff300366dac77b9b6f5873"
CONTROL_A_SUBJECT = "feat/test: add deterministic fake runtime controller"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_fake_runtime_contract.md",
    "framework/realtime_fake_runtime.py",
    "scripts/smoke_v600_realtime_fake_runtime_controller.py",
}

CONTROL_B = EXPECTED_BASELINE
CONTROL_B_PARENT = CONTROL_A
CONTROL_B_SUBJECT = EXPECTED_BASELINE_SUBJECT
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_fake_runtime_contract.md",
    "framework/realtime_fake_runtime.py",
    "scripts/smoke_v600_realtime_fake_runtime_adoption.py",
}

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_fake_runtime_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}

UNCHANGED_ACCEPTED_PATHS = (
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_fake_runtime_contract.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime_fake_runtime.py",
    "framework/realtime_session.py",
    "framework/realtime_stage.py",
    "framework/realtime_generation_gate.py",
    "framework/realtime_terminal_registry.py",
    "framework/realtime_event_hub.py",
    "scripts/smoke_v600_realtime_fake_runtime_controller.py",
    "scripts/smoke_v600_realtime_fake_runtime_adoption.py",
    "scripts/check_v600_realtime_stage_protocol_acceptance.py",
    "scripts/smoke_v600_realtime_stage_protocols.py",
    "scripts/smoke_v600_realtime_stage_injection.py",
)

README_MARKER = "FW-RT6-3b-C-FAKE-RUNTIME-ACCEPTANCE:BEGIN"
TASKLIST_MARKER = "FW-RT6-3b-C-ACCEPTANCE-SYNC:BEGIN"
GAP_MARKER = "FW-RT6-3b-C-GAP-RESOLUTION-SYNC:BEGIN"
FORBIDDEN_IMPORT_FRAGMENTS = (
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
)


def _assert(condition: bool, message: str) -> None:
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


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).splitlines()
        if line.strip()
    }


def _check_commit(
    *,
    commit: str,
    parent: str,
    subject: str,
    surface: set[str],
    label: str,
) -> None:
    _assert(_git("rev-parse", f"{commit}^") == parent, f"{label} parent drift")
    _assert(
        _git("show", "-s", "--format=%s", commit) == subject,
        f"{label} subject drift",
    )
    _assert(_commit_surface(commit) == surface, f"{label} surface drift")


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected HEAD")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "Control B parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "Control B subject drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control C surface: {sorted(_changed_paths())}",
    )
    _check_commit(
        commit=CONTROL_A,
        parent=CONTROL_A_PARENT,
        subject=CONTROL_A_SUBJECT,
        surface=CONTROL_A_SURFACE,
        label="Control A",
    )
    _check_commit(
        commit=CONTROL_B,
        parent=CONTROL_B_PARENT,
        subject=CONTROL_B_SUBJECT,
        surface=CONTROL_B_SURFACE,
        label="Control B",
    )
    for relative in UNCHANGED_ACCEPTED_PATHS:
        _assert(
            _git("hash-object", relative) == _git("rev-parse", f"HEAD:{relative}"),
            f"accepted runtime/source changed during Control C: {relative}",
        )
    print("[OK] Control A/B history and exact six-file Control C surface conform")


def _load_script(relative_path: str, module_name: str) -> ModuleType:
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    _assert(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_control_a_b_runtime_regressions() -> None:
    # Run the accepted Control B functional checks directly, but do not re-enter
    # its historical wrapper that eventually invokes the FW-RT6-3a manifest and
    # version gates. Those older gates intentionally pin the previous next
    # checkpoint (FW-RT6-3b), while this Control C candidate truthfully advances
    # the current manifest/version outputs to FW-RT6-3c. This checker owns the
    # current manifest/version assertions in check_manifest_and_version_gates().
    control_b = _load_script(
        "scripts/smoke_v600_realtime_fake_runtime_adoption.py",
        "_rt6_3b_control_b_acceptance_regression",
    )
    for name in (
        "check_source_and_import_safety",
        "check_public_test_support_surface",
        "check_generation_gate_adoption",
        "check_terminal_registry_adoption",
        "check_reproducible_adoption_race",
        "check_deferred_boundaries_and_docs",
    ):
        getattr(control_b, name)()

    control_a = _load_script(
        "scripts/smoke_v600_realtime_fake_runtime_controller.py",
        "_rt6_3b_control_a_acceptance_regression",
    )
    for name in (
        "check_clock_scheduler_and_artificial_delay",
        "check_pause_resume",
        "check_race_and_fault_injections",
        "check_queue_overflow_and_close",
        "check_trace_assertion_helper",
    ):
        getattr(control_a, name)()

    stage_acceptance = _load_script(
        "scripts/check_v600_realtime_stage_protocol_acceptance.py",
        "_rt6_3b_stage_acceptance_regression",
    )
    for name in (
        "check_source_contract",
        "check_public_compatibility",
        "check_stage_controls_and_runtime_regressions",
        "check_aggregate_docs",
        "check_import_safety",
    ):
        getattr(stage_acceptance, name)()

    print(
        "[OK] Controls A/B deterministic fake-runtime and accepted stage "
        "regressions conform"
    )


def check_aggregate_docs() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(
        encoding="utf-8"
    )
    gap = (
        PROJECT_ROOT / "docs" / "v600_current_source_gap_inventory.md"
    ).read_text(encoding="utf-8")

    _assert(README_MARKER in readme, "README aggregate marker missing")
    _assert(TASKLIST_MARKER in tasklist, "tasklist aggregate marker missing")
    _assert(GAP_MARKER in gap, "gap inventory aggregate marker missing")

    for task in (
        "fake clock/schedulerを追加する。",
        "stage pause/resumeを追加する。",
        "artificial delayを追加する。",
        "late completion injectionを追加する。",
        "duplicate terminal injectionを追加する。",
        "cancellation timeout injectionを追加する。",
        "queue overflow injectionを追加する。",
        "deterministic event trace assertion helperを追加する。",
    ):
        _assert(f"- [x] {task}" in tasklist, f"task not accepted: {task}")

    for text, label in (
        (readme, "README"),
        (tasklist, "tasklist"),
        (gap, "gap inventory"),
    ):
        for phrase in (
            "Control A deterministic fake runtime controller: ACCEPTED",
            "Control B generation-gate / terminal-registry adoption: ACCEPTED",
            "race reproducible: True",
            "root-public names: 121 / UNCHANGED",
            "RealtimeSession orchestration changed: False",
            "event-hub trace projection: DEFERRED",
            "provider / network / microphone / playback / real VTS execution: False",
            "next checkpoint: FW-RT6-3c",
            "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED",
        ):
            _assert(phrase in text, f"{label} aggregate fact missing: {phrase}")

    _assert(
        "G-16 deterministic fake runtime controller: RESOLVED" in gap,
        "G-16 fake runtime resolution missing",
    )
    _assert(
        "G-16 normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c"
        in gap,
        "normal unit-test layer must remain unresolved",
    )
    print("[OK] README, tasklist, and gap inventory record truthful FW-RT6-3b acceptance")


def _run_script(filename: str, expected_phrases: tuple[str, ...]) -> None:
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / filename)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"{filename} failed:\n{output}")
    for phrase in expected_phrases:
        _assert(phrase in output, f"{filename} output missing: {phrase}")
    print(f"[OK] {filename} conforms")


def check_manifest_and_version_gates() -> None:
    common = (
        "v600_realtime_fake_runtime_status: accepted",
        "v600_realtime_fake_runtime_generation_gate_adoption: True",
        "v600_realtime_fake_runtime_terminal_registry_adoption: True",
        "v600_realtime_fake_runtime_race_reproducible: True",
        "v600_realtime_fake_runtime_session_orchestration_changed: False",
        "v600_next_checkpoint: FW-RT6-3c",
        "v600_next_checkpoint_authorized: False",
    )
    _run_script("smoke_v600_public_api_manifest.py", common)
    _run_script("smoke_v600_version_metadata.py", common)
    print("[OK] public manifest and frozen version metadata record FW-RT6-3b acceptance")


def check_import_safety() -> None:
    probe = f"""
import sys
sys.path.insert(0, {str(PROJECT_ROOT)!r})
import framework
assert len(framework.__all__) == 121
assert "framework.realtime_fake_runtime" not in sys.modules
before = set(sys.modules)
from framework.realtime_fake_runtime import (
    DeterministicFakeRuntimeController,
    DeterministicRealtimeRaceHarness,
)
assert DeterministicFakeRuntimeController is not None
assert DeterministicRealtimeRaceHarness is not None
for forbidden in {FORBIDDEN_IMPORT_FRAGMENTS!r}:
    assert not any(
        module == forbidden or module.startswith(forbidden + ".")
        for module in set(sys.modules) - before
    )
"""
    subprocess.run(
        [sys.executable, "-I", "-c", probe],
        cwd=PROJECT_ROOT,
        check=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    print("[OK] Control C validation stayed provider/runtime safe")


def main() -> None:
    checks: tuple[Callable[[], None], ...] = (
        check_repository_contract,
        check_control_a_b_runtime_regressions,
        check_aggregate_docs,
        check_manifest_and_version_gates,
        check_import_safety,
    )
    for check in checks:
        check()

    print("v600_rt6_3b_control_c_status: implemented-awaiting-review")
    print("v600_rt6_3b_control_c_exact_change_surface_count: 6")
    print("v600_rt6_3b_control_c_runtime_source_changed: False")
    print("v600_rt6_3b_control_c_control_a_status: accepted")
    print("v600_rt6_3b_control_c_control_b_status: accepted")
    print("v600_rt6_3b_control_c_task_count_accepted: 8")
    print("v600_rt6_3b_control_c_generation_gate_adoption: True")
    print("v600_rt6_3b_control_c_terminal_registry_adoption: True")
    print("v600_rt6_3b_control_c_race_reproducible: True")
    print("v600_rt6_3b_control_c_root_public_names: 121 / unchanged")
    print("v600_rt6_3b_control_c_realtime_session_orchestration_changed: False")
    print("v600_rt6_3b_control_c_event_hub_trace_projection: deferred")
    print("v600_rt6_3b_control_c_normal_unit_test_layer: deferred / FW-RT6-3c")
    print("v600_rt6_3b_control_c_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3b_control_c_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3b_control_c_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_3c_authorized: False")
    print("[OK] FW-RT6-3b deterministic fake runtime aggregate acceptance conforms")


if __name__ == "__main__":
    main()
