"""FW-RT6-3b Control A deterministic fake-runtime controller smoke.

Offline/mock-safe: validates the exact five-file candidate, deterministic
clock/scheduler ordering, pause/resume, artificial delay, late completion,
duplicate terminal, cancellation timeout, queue overflow, trace assertions,
public-safe metadata, import safety, and preserved FW-RT6-3a boundaries without
provider, network, microphone, playback, real VTube Studio, DRC repository, or
root-draft stash access.
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

EXPECTED_BASELINE = "dc02a13b98cb6fd7a8ff300366dac77b9b6f5873"
EXPECTED_BASELINE_PARENT = "8db6a4ff1c9687b9e9d04b2f55a38611e27e0a5e"
EXPECTED_BASELINE_SUBJECT = "docs/test: accept realtime stage protocols"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_fake_runtime_contract.md",
    "framework/realtime_fake_runtime.py",
    "scripts/smoke_v600_realtime_fake_runtime_controller.py",
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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected HEAD")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(_changed_paths() == EXPECTED_SURFACE, "exact five-file surface drift")
    for path in UNCHANGED_ACCEPTED_PATHS:
        result = subprocess.run(
            ["git", "diff", "--quiet", "--", path],
            cwd=PROJECT_ROOT,
            check=False,
        )
        _assert(result.returncode == 0, f"accepted path changed: {path}")
    print("[OK] FW-RT6-3a history and exact five-file Control A surface conform")


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

    probe = f"""
import sys
sys.path.insert(0, {str(PROJECT_ROOT)!r})
import framework
assert "framework.realtime_fake_runtime" not in sys.modules
assert len(framework.__all__) == 121
before = set(sys.modules)
import framework.realtime_fake_runtime as fake
assert tuple(fake.__all__) == (
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
)
assert not any(name in framework.__all__ for name in fake.__all__)
for forbidden in (
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
):
    assert not any(
        module == forbidden or module.startswith(forbidden + ".")
        for module in set(sys.modules) - before
    )
"""
    subprocess.run(
        [sys.executable, "-I", "-c", probe],
        cwd=PROJECT_ROOT,
        check=True,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT),
        },
    )
    print("[OK] explicit fake-runtime import is root-neutral and provider/runtime safe")


def check_public_surface() -> None:
    module = importlib.import_module("framework.realtime_fake_runtime")
    _assert(tuple(module.__all__) == EXPECTED_EXPORTS, "fake-runtime exports drift")
    for name in EXPECTED_EXPORTS:
        _assert(hasattr(module, name), f"missing export: {name}")

    from framework.realtime_fake_runtime import (
        DeterministicFakeRuntimeController,
        FakeRuntimeAction,
        FakeRuntimeActionKind,
        FakeRuntimeTraceEvent,
        FakeRuntimeTraceKind,
    )
    from framework.realtime_stage import RealtimeStageKind

    action = FakeRuntimeAction(
        action_id="fake-action-safe",
        sequence=1,
        kind=FakeRuntimeActionKind.CUSTOM,
        due_tick=4,
        stage_kind=RealtimeStageKind.TEXT_GENERATION,
        correlation_key="generation-safe",
        public_metadata={
            "api_token": "private",
            "private_path": "C:\\private\\artifact.wav",
            "nested": {"password": "private"},
        },
    )
    _assert(action.public_metadata["api_token"] == "<redacted>", "token leaked")
    _assert(
        action.public_metadata["private_path"] == "<redacted:path>",
        "private path leaked",
    )
    nested = action.public_metadata["nested"]
    _assert(nested["password"] == "<redacted>", "nested secret leaked")
    _assert("artifact.wav" not in repr(action), "action repr leaked private metadata")

    event = FakeRuntimeTraceEvent(
        index=0,
        tick=0,
        kind=FakeRuntimeTraceKind.ACTION_SCHEDULED,
        action_id=action.action_id,
        action_kind=action.kind,
        stage_kind=action.stage_kind,
        correlation_key=action.correlation_key,
        public_metadata={"secret": "private"},
    )
    _assert(event.public_metadata["secret"] == "<redacted>", "trace secret leaked")
    _assert("private" not in repr(event), "trace repr leaked private metadata")

    controller = DeterministicFakeRuntimeController()
    _assert(controller.pending_count == 0, "new controller queue not empty")
    _assert(controller.clock.now_tick == 0, "new controller tick drift")
    print("[OK] public fake-runtime models and metadata remain provider-neutral and safe")


def check_clock_scheduler_and_artificial_delay() -> None:
    from framework.realtime_fake_runtime import (
        DeterministicFakeClock,
        DeterministicFakeRuntimeController,
        FakeRuntimeActionKind,
    )
    from framework.realtime_stage import RealtimeStageKind

    clock = DeterministicFakeClock(3)
    _assert(clock.advance_by(2) == 5, "clock advance_by drift")
    _assert(clock.advance_to(9) == 9, "clock advance_to drift")
    try:
        clock.advance_to(8)
    except ValueError:
        pass
    else:
        raise AssertionError("clock moved backwards")

    observed: list[tuple[str, int, FakeRuntimeActionKind]] = []
    controller = DeterministicFakeRuntimeController(initial_tick=10)
    controller.schedule_stage_action(
        RealtimeStageKind.VOICE_OUTPUT,
        lambda action: observed.append(
            ("voice", controller.clock.now_tick, action.kind)
        ),
        delay_ticks=5,
        correlation_key="voice-delay",
    )
    controller.schedule_stage_action(
        RealtimeStageKind.TEXT_GENERATION,
        lambda action: observed.append(
            ("text", controller.clock.now_tick, action.kind)
        ),
        delay_ticks=2,
        correlation_key="text-delay",
    )
    executed = controller.run_until_idle()
    _assert(
        observed
        == [
            ("text", 12, FakeRuntimeActionKind.STAGE_ACTION),
            ("voice", 15, FakeRuntimeActionKind.STAGE_ACTION),
        ],
        "artificial-delay order drift",
    )
    _assert(
        [action.stage_kind for action in executed]
        == [
            RealtimeStageKind.TEXT_GENERATION,
            RealtimeStageKind.VOICE_OUTPUT,
        ],
        "scheduler insertion/due ordering drift",
    )
    _assert(controller.clock.now_tick == 15, "final fake tick drift")
    print("[OK] fake clock/scheduler and artificial delay are deterministic")


def check_pause_resume() -> None:
    from framework.realtime_fake_runtime import DeterministicFakeRuntimeController
    from framework.realtime_stage import RealtimeStageKind

    observed: list[str] = []
    controller = DeterministicFakeRuntimeController()
    _assert(
        controller.pause_stage(RealtimeStageKind.VOICE_INPUT),
        "first pause not accepted",
    )
    _assert(
        not controller.pause_stage(RealtimeStageKind.VOICE_INPUT),
        "duplicate pause changed state",
    )
    controller.schedule_stage_action(
        RealtimeStageKind.VOICE_INPUT,
        lambda action: observed.append("voice"),
        delay_ticks=1,
        correlation_key="paused-voice",
    )
    controller.schedule_stage_action(
        RealtimeStageKind.TEXT_GENERATION,
        lambda action: observed.append("text"),
        delay_ticks=2,
        correlation_key="free-text",
    )
    controller.advance_by(2)
    _assert(observed == ["text"], "paused stage executed")
    _assert(controller.pending_count == 1, "paused action not retained")
    _assert(
        controller.resume_stage(RealtimeStageKind.VOICE_INPUT),
        "resume not accepted",
    )
    _assert(
        not controller.resume_stage(RealtimeStageKind.VOICE_INPUT),
        "duplicate resume changed state",
    )
    controller.run_due()
    _assert(observed == ["text", "voice"], "resumed action did not execute")
    _assert(controller.pending_count == 0, "resumed queue not drained")
    print("[OK] stage pause/resume preserves due work and deterministic release")


def _race_scenario() -> tuple[tuple[str, ...], tuple[str, ...]]:
    from framework.realtime_fake_runtime import DeterministicFakeRuntimeController
    from framework.realtime_stage import RealtimeStageKind

    observed: list[str] = []
    controller = DeterministicFakeRuntimeController(initial_tick=40)
    controller.schedule_stage_action(
        RealtimeStageKind.TEXT_GENERATION,
        lambda action: observed.append(
            f"stage:{action.correlation_key}:{controller.clock.now_tick}"
        ),
        delay_ticks=1,
        correlation_key="new-generation",
    )
    controller.inject_duplicate_terminal(
        RealtimeStageKind.TEXT_GENERATION,
        lambda action: observed.append(
            f"terminal:{action.correlation_key}:{controller.clock.now_tick}"
        ),
        correlation_key="turn-terminal",
        copies=2,
        delay_ticks=2,
    )
    controller.inject_late_completion(
        RealtimeStageKind.VOICE_OUTPUT,
        lambda action: observed.append(
            f"late:{action.correlation_key}:{controller.clock.now_tick}"
        ),
        correlation_key="retired-generation",
        delay_ticks=3,
    )
    controller.inject_cancellation_timeout(
        RealtimeStageKind.VOICE_OUTPUT,
        lambda action: observed.append(
            f"timeout:{action.correlation_key}:{controller.clock.now_tick}"
        ),
        correlation_key="cancel-generation",
        timeout_ticks=4,
    )
    controller.run_until_idle()
    return tuple(observed), controller.trace_signature()


def check_race_and_fault_injections() -> None:
    from framework.realtime_fake_runtime import FakeRuntimeTraceKind

    first_observed, first_trace = _race_scenario()
    second_observed, second_trace = _race_scenario()
    _assert(first_observed == second_observed, "race callback order is not reproducible")
    _assert(first_trace == second_trace, "race trace is not reproducible")
    _assert(
        first_observed
        == (
            "stage:new-generation:41",
            "terminal:turn-terminal:42",
            "terminal:turn-terminal:42",
            "late:retired-generation:43",
            "timeout:cancel-generation:44",
        ),
        "race/fault callback sequence drift",
    )
    trace_kinds = tuple(item.split("|")[2] for item in first_trace)
    for required in (
        FakeRuntimeTraceKind.DUPLICATE_TERMINAL_INJECTED.value,
        FakeRuntimeTraceKind.LATE_COMPLETION_INJECTED.value,
        FakeRuntimeTraceKind.CANCELLATION_TIMEOUT_INJECTED.value,
    ):
        _assert(required in trace_kinds, f"missing injection trace: {required}")
    print("[OK] late, duplicate-terminal, and cancellation-timeout races reproduce exactly")


def check_queue_overflow_and_close() -> None:
    from framework.realtime_fake_runtime import (
        DeterministicFakeRuntimeController,
        FakeRuntimeClosedError,
        FakeRuntimeQueueOverflow,
        FakeRuntimeTraceKind,
    )
    from framework.realtime_stage import RealtimeStageKind

    controller = DeterministicFakeRuntimeController(max_queue_size=1)
    controller.schedule_stage_action(
        RealtimeStageKind.MOTION,
        lambda action: None,
        correlation_key="queue-slot",
    )
    try:
        controller.schedule_stage_action(
            RealtimeStageKind.MOTION,
            lambda action: None,
            correlation_key="queue-overflow",
        )
    except FakeRuntimeQueueOverflow:
        pass
    else:
        raise AssertionError("capacity overflow was not raised")
    _assert(controller.pending_count == 1, "overflow mutated existing queue")
    _assert(
        controller.trace[-1].kind is FakeRuntimeTraceKind.QUEUE_OVERFLOW_INJECTED,
        "capacity overflow trace missing",
    )

    explicit = DeterministicFakeRuntimeController()
    try:
        explicit.inject_queue_overflow(
            stage_kind=RealtimeStageKind.VOICE_OUTPUT,
            correlation_key="explicit-overflow",
        )
    except FakeRuntimeQueueOverflow:
        pass
    else:
        raise AssertionError("explicit overflow injection did not raise")
    _assert(
        explicit.trace[-1].kind is FakeRuntimeTraceKind.QUEUE_OVERFLOW_INJECTED,
        "explicit overflow trace missing",
    )

    controller.close()
    controller.close()
    _assert(controller.closed, "controller close state missing")
    _assert(controller.pending_count == 0, "close did not clear queue")
    try:
        controller.schedule_stage_action(
            RealtimeStageKind.MOTION,
            lambda action: None,
        )
    except FakeRuntimeClosedError:
        pass
    else:
        raise AssertionError("post-close scheduling was accepted")
    _assert(
        sum(
            event.kind is FakeRuntimeTraceKind.CONTROLLER_CLOSED
            for event in controller.trace
        )
        == 1,
        "controller close trace is not once-only",
    )
    print("[OK] queue overflow and once-only close faults remain deterministic")


def check_trace_assertion_helper() -> None:
    from framework.realtime_fake_runtime import (
        DeterministicFakeRuntimeController,
        assert_deterministic_trace,
        deterministic_trace_signature,
    )
    from framework.realtime_stage import RealtimeStageKind

    controller = DeterministicFakeRuntimeController()
    controller.schedule_stage_action(
        RealtimeStageKind.MOTION,
        lambda action: None,
        delay_ticks=1,
        correlation_key="trace",
    )
    controller.run_until_idle()
    signature = deterministic_trace_signature(controller.trace)
    controller.assert_trace(signature)
    assert_deterministic_trace(controller.trace, signature)
    try:
        controller.assert_trace((*signature[:-1], "mismatch"))
    except AssertionError as error:
        message = str(error)
        _assert("metadata" not in message, "trace mismatch exposed metadata")
        _assert("private" not in message, "trace mismatch exposed private data")
    else:
        raise AssertionError("trace mismatch was not rejected")
    print("[OK] deterministic event trace assertion helper is exact and metadata-free")


def check_docs() -> None:
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
        _assert(CONTROL_A_MARKER in text, f"{label} marker missing")
        _assert("network" in text.lower(), f"{label} network boundary missing")
        _assert("provider SDK" in text, f"{label} provider boundary missing")
        _assert("race reproducible" in text, f"{label} race acceptance missing")
        _assert("Control B" in text, f"{label} deferred Control B missing")
    _assert(
        "RealtimeSession orchestration changed: False" in contract,
        "contract overclaims session orchestration",
    )
    _assert(
        "tasklist checkboxes changed: False" in contract,
        "contract does not preserve aggregate acceptance",
    )
    print("[OK] docs record Control A without overclaiming session adoption or aggregate acceptance")


def _load_regression_script(relative_path: str, module_name: str) -> object:
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load regression script: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_prior_stage_regressions() -> None:
    # The accepted FW-RT6-3a aggregate checker is the current compatibility
    # authority. Its repository-contract entry point intentionally pins the
    # already committed Control C HEAD, so this later five-file candidate loads
    # the checker as a module and runs only its reusable source/runtime/public
    # checks. The current smoke remains authoritative for this candidate's HEAD
    # and exact dirty surface.
    acceptance = _load_regression_script(
        "scripts/check_v600_realtime_stage_protocol_acceptance.py",
        "_rt6_3b_prior_stage_acceptance_regression",
    )
    for name in (
        "check_source_contract",
        "check_public_compatibility",
        "check_stage_controls_and_runtime_regressions",
        "check_aggregate_docs",
        "check_manifest_and_version_gates",
        "check_import_safety",
    ):
        getattr(acceptance, name)()

    print("[OK] accepted FW-RT6-3a stage protocol and runtime regressions conform")

def main() -> None:
    checks: tuple[Callable[[], None], ...] = (
        check_repository_contract,
        check_source_and_import_safety,
        check_public_surface,
        check_clock_scheduler_and_artificial_delay,
        check_pause_resume,
        check_race_and_fault_injections,
        check_queue_overflow_and_close,
        check_trace_assertion_helper,
        check_docs,
        check_prior_stage_regressions,
    )
    for check in checks:
        check()

    print("v600_rt6_3b_control_a_status: implemented-awaiting-review")
    print("v600_rt6_3b_control_a_exact_change_surface_count: 5")
    print("v600_rt6_3b_control_a_explicit_package: framework.realtime_fake_runtime")
    print("v600_rt6_3b_control_a_root_public_names: 121 / unchanged")
    print("v600_rt6_3b_control_a_fake_clock_scheduler: True")
    print("v600_rt6_3b_control_a_stage_pause_resume: True")
    print("v600_rt6_3b_control_a_artificial_delay: True")
    print("v600_rt6_3b_control_a_late_completion_injection: True")
    print("v600_rt6_3b_control_a_duplicate_terminal_injection: True")
    print("v600_rt6_3b_control_a_cancellation_timeout_injection: True")
    print("v600_rt6_3b_control_a_queue_overflow_injection: True")
    print("v600_rt6_3b_control_a_deterministic_trace_helper: True")
    print("v600_rt6_3b_control_a_race_reproducible: True")
    print("v600_rt6_3b_control_a_wall_clock_sleep_or_background_thread: False")
    print("v600_rt6_3b_control_a_realtime_session_orchestration_changed: False")
    print("v600_rt6_3b_control_a_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3b_control_a_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3b_control_a_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_3b_control_b_authorized: False")
    print("[OK] FW-RT6-3b Control A deterministic fake runtime controller conforms")


if __name__ == "__main__":
    main()
