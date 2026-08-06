"""FW-RT6-3b Control B deterministic gate/terminal adoption smoke.

Offline/mock-safe: validates the exact five-file candidate, the accepted Control A
controller regression, deterministic adoption of the real generation gate and
terminal registry, reproducible late/duplicate races, truthful deferred
boundaries, root-public compatibility, and provider/runtime safety.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "c3999bd16b2d6104fc90d6282da9a60c84068875"
EXPECTED_BASELINE_PARENT = "dc02a13b98cb6fd7a8ff300366dac77b9b6f5873"
EXPECTED_BASELINE_SUBJECT = "feat/test: add deterministic fake runtime controller"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_fake_runtime_contract.md",
    "framework/realtime_fake_runtime.py",
    "scripts/smoke_v600_realtime_fake_runtime_controller.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_fake_runtime_contract.md",
    "framework/realtime_fake_runtime.py",
    "scripts/smoke_v600_realtime_fake_runtime_adoption.py",
}
UNCHANGED_ACCEPTED_PATHS = (
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime_session.py",
    "framework/realtime_stage.py",
    "framework/realtime_generation_gate.py",
    "framework/realtime_terminal_registry.py",
    "framework/realtime_event_hub.py",
    "scripts/check_v600_realtime_stage_protocol_acceptance.py",
    "scripts/smoke_v600_realtime_stage_protocols.py",
    "scripts/smoke_v600_realtime_stage_injection.py",
    "scripts/smoke_v600_realtime_fake_runtime_controller.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
)
EXPECTED_EXPORTS = (
    "FakeRuntimeActionKind",
    "FakeRuntimeTraceKind",
    "FakeRuntimeQueueOverflow",
    "FakeRuntimeClosedError",
    "DeterministicFakeClock",
    "FakeRuntimeAction",
    "FakeRuntimeTraceEvent",
    "deterministic_trace_signature",
    "assert_deterministic_trace",
    "DeterministicFakeScheduler",
    "DeterministicFakeRuntimeController",
    "FakeGenerationAdmissionRecord",
    "FakeTerminalCommitRecord",
    "DeterministicRealtimeRaceHarness",
)
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
CONTROL_A_MARKER = "FW-RT6-3b-A-DETERMINISTIC-FAKE-RUNTIME"
CONTROL_B_MARKER = "FW-RT6-3b-B-GATE-TERMINAL-ADOPTION"


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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected HEAD")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "Control A parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "Control A subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == CONTROL_A_SURFACE,
        "Control A committed surface drift",
    )
    _assert(_changed_paths() == EXPECTED_SURFACE, "exact five-file surface drift")
    for path in UNCHANGED_ACCEPTED_PATHS:
        result = subprocess.run(
            ["git", "diff", "--quiet", "--", path],
            cwd=PROJECT_ROOT,
            check=False,
        )
        _assert(result.returncode == 0, f"accepted path changed: {path}")
    print("[OK] Control A commit and exact five-file Control B surface conform")


def check_source_and_import_safety() -> None:
    source_path = PROJECT_ROOT / "framework" / "realtime_fake_runtime.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    lowered = "\n".join(sorted(imported)).lower()
    for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
        _assert(fragment not in lowered, f"forbidden import: {fragment}")
    _assert("time" not in imported, "wall-clock time import is forbidden")
    _assert("threading" not in imported, "background-thread scheduling is forbidden")
    _assert("asyncio" not in imported, "event-loop timing is forbidden")
    for required in (
        "RealtimeGenerationGate",
        "RealtimeTerminalRegistry",
        "DeterministicRealtimeRaceHarness",
        CONTROL_B_MARKER,
    ):
        _assert(required in source, f"Control B source marker missing: {required}")

    probe = f"""
import sys
sys.path.insert(0, {str(PROJECT_ROOT)!r})
import framework
assert "framework.realtime_fake_runtime" not in sys.modules
assert len(framework.__all__) == 121
before = set(sys.modules)
import framework.realtime_fake_runtime as fake
assert tuple(fake.__all__) == {EXPECTED_EXPORTS!r}
assert not any(name in framework.__all__ for name in fake.__all__)
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
    print("[OK] explicit adoption import is root-neutral and provider/runtime safe")


def check_public_test_support_surface() -> None:
    module = importlib.import_module("framework.realtime_fake_runtime")
    _assert(tuple(module.__all__) == EXPECTED_EXPORTS, "fake-runtime exports drift")
    for name in EXPECTED_EXPORTS:
        _assert(hasattr(module, name), f"missing export: {name}")

    from framework.realtime_fake_runtime import (
        DeterministicRealtimeRaceHarness,
        FakeGenerationAdmissionRecord,
        FakeTerminalCommitRecord,
    )

    harness = DeterministicRealtimeRaceHarness[str, str]()
    _assert(harness.pending_count == 0, "new harness queue not empty")
    _assert(harness.generation_admissions == (), "new generation records not empty")
    _assert(harness.terminal_commits == (), "new terminal records not empty")
    print("[OK] Control B adds only explicit test-support records and harness")


def check_generation_gate_adoption() -> None:
    from framework.realtime_fake_runtime import DeterministicRealtimeRaceHarness
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        StaleCompletionReason,
    )
    from framework.realtime_stage import RealtimeStageKind

    harness = DeterministicRealtimeRaceHarness[str, str](initial_tick=20)
    old_generation = harness.start_generation("turn-old")
    harness.inject_late_generation_completion(
        RealtimeStageKind.VOICE_OUTPUT,
        turn_id="turn-old",
        generation_id=old_generation,
        value="old-audio",
        correlation_key="old-generation",
        delay_ticks=3,
        public_metadata={"api_token": "private"},
    )
    current_generation = harness.start_generation("turn-current")
    harness.schedule_generation_completion(
        RealtimeStageKind.TEXT_GENERATION,
        turn_id="turn-current",
        generation_id=current_generation,
        value="current-text",
        correlation_key="current-generation",
        delay_ticks=1,
    )
    harness.run_until_idle()

    records = harness.generation_admissions
    _assert(len(records) == 2, "generation admission count drift")
    _assert(records[0].accepted, "current generation completion rejected")
    _assert(records[0].tick == 21, "current completion tick drift")
    _assert(not records[1].accepted, "retired generation completion accepted")
    _assert(
        records[1].stale_reason is StaleCompletionReason.RETIRED_GENERATION,
        "late completion stale reason drift",
    )
    _assert(
        records[1].retired_by is GenerationAdvanceReason.NEW_TURN,
        "late completion retirement reason drift",
    )
    diagnostics = harness.generation_diagnostics
    _assert(diagnostics["accepted_completion_count"] == 1, "accepted count drift")
    _assert(diagnostics["stale_completion_count"] == 1, "stale count drift")
    _assert(
        "old-audio" not in repr(records[1]),
        "generation admission repr exposed completion value",
    )
    print("[OK] late completion is classified by the accepted generation gate")


def check_terminal_registry_adoption() -> None:
    from framework.lifecycle import TurnOutcome
    from framework.realtime_fake_runtime import DeterministicRealtimeRaceHarness
    from framework.realtime_stage import RealtimeStageKind
    from framework.realtime_terminal_registry import TerminalCommitStatus

    harness = DeterministicRealtimeRaceHarness[str, str](initial_tick=30)
    harness.inject_duplicate_terminal(
        RealtimeStageKind.TEXT_GENERATION,
        turn_id="turn-terminal",
        outcome=TurnOutcome.COMPLETED,
        result="terminal-result",
        reason="fake-complete",
        correlation_key="terminal-race",
        copies=3,
        delay_ticks=2,
        interval_ticks=0,
    )
    harness.run_until_idle()

    records = harness.terminal_commits
    _assert(len(records) == 3, "terminal decision count drift")
    _assert(
        tuple(record.status for record in records)
        == (
            TerminalCommitStatus.FIRST_TERMINAL,
            TerminalCommitStatus.DUPLICATE_TERMINAL,
            TerminalCommitStatus.DUPLICATE_TERMINAL,
        ),
        "duplicate terminal classification drift",
    )
    _assert(tuple(record.accepted for record in records) == (True, False, False),
            "duplicate terminal acceptance drift")
    diagnostics = harness.terminal_diagnostics
    _assert(diagnostics.terminal_commit_count == 1, "terminal commit count drift")
    _assert(diagnostics.duplicate_terminal_count == 2, "duplicate count drift")
    _assert(diagnostics.registry_size == 1, "terminal registry size drift")
    _assert(len(harness.terminal_records) == 1, "first terminal record not retained")
    _assert(
        "terminal-result" not in repr(records[0]),
        "terminal decision repr exposed retained result",
    )
    print("[OK] duplicate terminal race is classified by the accepted registry")


def _mixed_scenario() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    from framework.lifecycle import TurnOutcome
    from framework.realtime_fake_runtime import DeterministicRealtimeRaceHarness
    from framework.realtime_stage import RealtimeStageKind

    harness = DeterministicRealtimeRaceHarness[str, str](initial_tick=50)
    retired = harness.start_generation("turn-retired")
    harness.inject_late_generation_completion(
        RealtimeStageKind.VOICE_OUTPUT,
        turn_id="turn-retired",
        generation_id=retired,
        value="old",
        correlation_key="late",
        delay_ticks=4,
    )
    current = harness.start_generation("turn-current")
    harness.schedule_generation_completion(
        RealtimeStageKind.TEXT_GENERATION,
        turn_id="turn-current",
        generation_id=current,
        value="new",
        correlation_key="current",
        delay_ticks=1,
    )
    harness.inject_duplicate_terminal(
        RealtimeStageKind.TEXT_GENERATION,
        turn_id="turn-current",
        outcome=TurnOutcome.COMPLETED,
        result="done",
        correlation_key="terminal",
        copies=2,
        delay_ticks=2,
    )
    harness.run_until_idle()
    generation = tuple(
        "accepted" if record.accepted else record.stale_reason.value
        for record in harness.generation_admissions
    )
    terminal = tuple(record.status.value for record in harness.terminal_commits)
    return generation, terminal, harness.trace_signature()


def check_reproducible_adoption_race() -> None:
    first = _mixed_scenario()
    second = _mixed_scenario()
    _assert(first == second, "gate/terminal adoption race is not reproducible")
    _assert(
        first[0] == ("accepted", "retired_generation"),
        "mixed generation decisions drift",
    )
    _assert(
        first[1] == ("first_terminal", "duplicate_terminal"),
        "mixed terminal decisions drift",
    )
    print("[OK] actual gate/registry race decisions and trace reproduce exactly")


def check_deferred_boundaries_and_docs() -> None:
    app_contract = (
        PROJECT_ROOT / "docs" / "app_integration_contract.md"
    ).read_text(encoding="utf-8")
    public_facade = (
        PROJECT_ROOT / "docs" / "public_facade.md"
    ).read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_fake_runtime_contract.md"
    ).read_text(encoding="utf-8")
    for text, label in (
        (app_contract, "app integration contract"),
        (public_facade, "public facade"),
        (contract, "fake runtime contract"),
    ):
        _assert(CONTROL_A_MARKER in text, f"{label} Control A marker missing")
        _assert(CONTROL_B_MARKER in text, f"{label} Control B marker missing")
        _assert("RealtimeGenerationGate" in text, f"{label} gate adoption missing")
        _assert("RealtimeTerminalRegistry" in text, f"{label} registry adoption missing")
    for required in (
        "RealtimeSession orchestration changed: False",
        "event-hub trace projection: DEFERRED",
        "tasklist checkboxes changed: False",
        "aggregate FW-RT6-3b acceptance: DEFERRED",
        "provider SDK / network / microphone / playback / real VTS execution: False",
    ):
        _assert(required in contract, f"deferred boundary missing: {required}")
    print("[OK] docs record deterministic adoption without orchestration overclaim")


def _load_script(relative_path: str, module_name: str) -> object:
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load regression script: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_control_a_and_prior_regressions() -> None:
    control_a = _load_script(
        "scripts/smoke_v600_realtime_fake_runtime_controller.py",
        "_rt6_3b_control_a_functional_regression",
    )
    for name in (
        "check_clock_scheduler_and_artificial_delay",
        "check_pause_resume",
        "check_race_and_fault_injections",
        "check_queue_overflow_and_close",
        "check_trace_assertion_helper",
        "check_prior_stage_regressions",
    ):
        getattr(control_a, name)()
    print("[OK] Control A controller and accepted FW-RT6-3a regressions conform")


def main() -> None:
    checks: tuple[Callable[[], None], ...] = (
        check_repository_contract,
        check_source_and_import_safety,
        check_public_test_support_surface,
        check_generation_gate_adoption,
        check_terminal_registry_adoption,
        check_reproducible_adoption_race,
        check_deferred_boundaries_and_docs,
        check_control_a_and_prior_regressions,
    )
    for check in checks:
        check()

    print("v600_rt6_3b_control_b_status: implemented-awaiting-review")
    print("v600_rt6_3b_control_b_exact_change_surface_count: 5")
    print("v600_rt6_3b_control_b_explicit_package: framework.realtime_fake_runtime")
    print("v600_rt6_3b_control_b_generation_gate_adoption: True")
    print("v600_rt6_3b_control_b_terminal_registry_adoption: True")
    print("v600_rt6_3b_control_b_late_completion_classified_by_actual_gate: True")
    print("v600_rt6_3b_control_b_duplicate_terminal_classified_by_actual_registry: True")
    print("v600_rt6_3b_control_b_race_reproducible: True")
    print("v600_rt6_3b_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_3b_control_b_realtime_session_orchestration_changed: False")
    print("v600_rt6_3b_control_b_event_hub_trace_projection: deferred")
    print("v600_rt6_3b_control_b_tasklist_checkboxes_changed: False")
    print("v600_rt6_3b_control_b_aggregate_acceptance: deferred")
    print("v600_rt6_3b_control_b_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3b_control_b_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3b_control_b_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_3b_control_c_authorized: False")
    print("[OK] FW-RT6-3b Control B deterministic gate/terminal adoption conforms")


if __name__ == "__main__":
    main()
