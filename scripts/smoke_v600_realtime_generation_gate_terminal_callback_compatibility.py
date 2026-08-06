"""FW-RT6-2d Control C corrective 1 terminal callback compatibility smoke.

Offline/mock-safe: verifies the exact three-file corrective, terminal callback
late-operation compatibility, normal post-turn no-active interrupt behavior,
accepted generation/race behavior, and prior terminal aggregate acceptance
without provider, network, microphone, playback, real VTube Studio, private
configuration, or DRC repository execution.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "7e26f3663f1a0121280dea57114fdfbf79b751dc"
EXPECTED_BASELINE_PARENT = "56ca83965f288d0c591a3969c45cb92b820a380a"
EXPECTED_BASELINE_SUBJECT = "test/docs: verify realtime generation race alignment"

EXPECTED_SURFACE = {
    "docs/v600_realtime_generation_gate_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_generation_gate_terminal_callback_compatibility.py",
}

UNCHANGED_RUNTIME_PATHS = (
    "framework/realtime_generation_gate.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_terminal_registry.py",
    "framework/vtube_studio_pyvts_transport.py",
    "framework/vtube_studio_transport.py",
    "framework/public_api.py",
    "framework/__init__.py",
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
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
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
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected corrective surface: {sorted(_changed_paths())}",
    )
    for relative in UNCHANGED_RUNTIME_PATHS:
        _assert(
            _git("hash-object", relative) == _git("rev-parse", f"HEAD:{relative}"),
            f"unrelated runtime source changed: {relative}",
        )
    print("[OK] exact three-file corrective surface and baseline conform")


def check_source_contract() -> None:
    source = (
        PROJECT_ROOT / "framework" / "realtime_session.py"
    ).read_text(encoding="utf-8")
    expected = """        current_turn_id = (
            self._generation_gate.current_turn_id
            or self._active_turn_id
        )
"""
    _assert(
        source.count(expected) == 1,
        "interrupt current-turn fallback is missing or duplicated",
    )
    interrupt_start = source.index("    def _interrupt_serialized(")
    cancel_start = source.index("    def cancel_current_turn(", interrupt_start)
    interrupt_source = source[interrupt_start:cancel_start]
    _assert(
        interrupt_source.index("current_turn_id = (")
        < interrupt_source.index("no_active_turn ="),
        "fallback occurs after no-active classification",
    )
    _assert(
        interrupt_source.index("current_turn_id = (")
        < interrupt_source.index("resolved_turn_id ="),
        "fallback occurs after resolved-turn selection",
    )
    _assert(
        "or self._active_turn_id" in interrupt_source,
        "currently executing terminal turn is not retained",
    )
    print("[OK] interrupt turn resolution preserves terminal callback identity")


def _diagnostic_snapshot(session: Any) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    return (
        dict(session.generation_diagnostics),
        dict(session.event_diagnostics),
        dict(session.terminal_diagnostics),
    )


def check_terminal_callback_late_operations() -> None:
    import framework

    session = framework.create_realtime_session()
    session.set_barge_in_policy(framework.BargeInPolicy.hard_cancel())
    canonical_events: list[Any] = []
    legacy_events: list[Any] = []
    observations: list[tuple[Any, ...]] = []
    nested = False

    def callback(event: Any) -> None:
        nonlocal nested
        canonical_events.append(event)
        if event.type is not framework.RealtimeEventType.TURN_COMPLETED or nested:
            return
        nested = True
        before = (
            session.state,
            session.phase,
            len(session.event_history),
            session.event_diagnostics["emitted_event_count"],
            dict(session.generation_diagnostics),
        )
        first_result = session.terminal_results[0]
        duplicate = session.run_turn(
            framework.RealtimeTurn(
                turn_id=event.turn_id,
                input_text="must-not-run",
            )
        )
        interrupt = session.interrupt()
        cancel = session.cancel_current_turn()
        flush = session.flush_output()
        barge = session.decide_barge_in()
        after = (
            session.state,
            session.phase,
            len(session.event_history),
            session.event_diagnostics["emitted_event_count"],
            dict(session.generation_diagnostics),
        )
        observations.append(
            (first_result, duplicate, interrupt, cancel, flush, barge, before, after)
        )

    session.on_event(callback)
    session.on_legacy_event(legacy_events.append)
    result = session.run_turn(input_text="terminal-callback-corrective")

    _assert(len(observations) == 1, "terminal callback observation missing")
    (
        first_result,
        duplicate,
        interrupt,
        cancel,
        flush,
        barge,
        before,
        after,
    ) = observations[0]

    _assert(result is first_result, "outer result identity drift")
    _assert(duplicate is first_result, "duplicate terminal result identity drift")
    _assert(
        interrupt.outcome is framework.InterruptOutcome.NO_ACTIVE_TURN,
        "terminal callback interrupt outcome drift",
    )
    _assert(
        cancel.outcome is framework.InterruptOutcome.NO_ACTIVE_TURN,
        "terminal callback cancel outcome drift",
    )
    _assert(
        flush.outcome is framework.OutputFlushOutcome.NOTHING_TO_FLUSH,
        "terminal callback flush outcome drift",
    )
    _assert(not barge.accepted, "terminal callback barge-in was accepted")
    _assert(before == after, "terminal callback late operations mutated session/event state")
    _assert(
        all(
            event.type
            not in {
                framework.RealtimeEventType.INTERRUPT_REQUESTED,
                framework.RealtimeEventType.INTERRUPT_UNSUPPORTED,
                framework.RealtimeEventType.BARGE_IN_DETECTED,
                framework.RealtimeEventType.BARGE_IN_ACCEPTED,
                framework.RealtimeEventType.BARGE_IN_REJECTED,
            }
            for event in canonical_events
            if event.type is not framework.RealtimeEventType.TURN_COMPLETED
        ),
        "terminal callback emitted a late interrupt/barge event",
    )
    _assert(
        [int(event.sequence) for event in canonical_events]
        == list(range(1, len(canonical_events) + 1)),
        "canonical sequence drift",
    )
    _assert(
        session.terminal_diagnostics["terminal_commit_count"] == 1,
        "terminal commit count drift",
    )
    _assert(
        session.terminal_diagnostics["duplicate_terminal_count"] == 1,
        "duplicate terminal count drift",
    )
    _assert(
        session.terminal_diagnostics["late_non_terminal_count"] == 4,
        "terminal late-operation count drift",
    )
    _assert(
        session.state is framework.RealtimeState.IDLE
        and session.phase is framework.RealtimePhase.IDLE,
        "outer turn did not restore idle",
    )
    session.close()
    print("[OK] terminal callback interrupt/cancel preserve typed results and emit no events")


def check_normal_post_turn_no_active_interrupt() -> None:
    import framework

    session = framework.create_realtime_session()
    session.run_turn(input_text="normal-post-turn")
    before_events = list(session.event_history)
    before_generation = dict(session.generation_diagnostics)

    result = session.interrupt()

    after_events = list(session.event_history)
    _assert(
        result.outcome is framework.InterruptOutcome.NO_ACTIVE_TURN,
        "normal post-turn interrupt outcome drift",
    )
    _assert(
        len(after_events) == len(before_events) + 2,
        "normal post-turn no-active events were not preserved",
    )
    _assert(
        [event.type for event in after_events[-2:]]
        == [
            framework.RealtimeEventType.INTERRUPT_REQUESTED,
            framework.RealtimeEventType.INTERRUPT_UNSUPPORTED,
        ],
        "normal post-turn no-active event types drift",
    )
    _assert(
        dict(session.generation_diagnostics) == before_generation,
        "normal post-turn no-active interrupt changed generation diagnostics",
    )
    _assert(
        session.state is framework.RealtimeState.IDLE
        and session.phase is framework.RealtimePhase.IDLE,
        "normal post-turn no-active interrupt changed idle state",
    )
    session.close()
    print("[OK] normal post-turn no-active interrupt behavior remains preserved")


def _run_historical_with_repository_contract_bypassed(
    script_name: str,
    expected_phrases: tuple[str, ...],
) -> None:
    code = f"""
import importlib.util
from pathlib import Path
root = Path({str(PROJECT_ROOT)!r})
path = root / "scripts" / {script_name!r}
spec = importlib.util.spec_from_file_location("_corrective_history", path)
if spec is None or spec.loader is None:
    raise AssertionError(f"cannot load {{path}}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.check_repository_contract = lambda: print("[OK] repository contract supplied by corrective smoke")
module.main()
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    _assert(
        completed.returncode == 0,
        f"{script_name} regression failed:\n{output}",
    )
    for phrase in expected_phrases:
        _assert(phrase in output, f"{script_name} output missing: {phrase}")
    print(f"[OK] {script_name} regression conforms")


def check_historical_acceptance() -> None:
    _run_historical_with_repository_contract_bypassed(
        "check_v600_realtime_terminal_registry_acceptance.py",
        (
            "v600_rt6_2c_control_d_one_terminal_event_per_turn: PASS",
            "v600_rt6_2c_control_d_duplicate_terminal_suppressed: PASS",
            "v600_rt6_2c_control_d_state_regression_rejected: PASS",
            "[OK] FW-RT6-2c Control D aggregate terminal-registry acceptance conforms",
        ),
    )
    _run_historical_with_repository_contract_bypassed(
        "smoke_v600_realtime_generation_gate_primitives.py",
        (
            "v600_rt6_2d_control_a_retired_completion_rejected: True",
            "v600_rt6_2d_control_a_vts_alignment: verified-Control-C",
        ),
    )
    _run_historical_with_repository_contract_bypassed(
        "smoke_v600_realtime_generation_gate_session_adoption.py",
        (
            "v600_rt6_2d_control_b_stale_completion_delivered: False",
            "v600_rt6_2d_control_b_post_close_stale_count_observable: True",
        ),
    )
    _run_historical_with_repository_contract_bypassed(
        "smoke_v600_realtime_generation_gate_race_alignment.py",
        (
            "v600_rt6_2d_control_c_completion_interrupt_both_winners: True",
            "v600_rt6_2d_control_c_completion_cancel_both_winners: True",
            "v600_rt6_2d_control_c_completion_close_both_winners: True",
            "v600_rt6_2d_control_c_completion_new_turn_both_winners: True",
            "v600_rt6_2d_control_c_terminal_callback_reentry_stale: True",
            "v600_rt6_2d_control_c_vts_source_changed: False",
        ),
    )
    print("[OK] prior terminal acceptance and generation Controls A/B/C remain conformant")


def check_public_compatibility_and_docs() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == ("project_root", "public_metadata", "real_runtime_enabled"),
        "create_realtime_session signature drift",
    )
    session = framework.create_realtime_session()
    generation_keys = set(session.generation_diagnostics)
    event_keys = set(session.event_diagnostics)
    terminal_keys = set(session.terminal_diagnostics)
    _assert(
        generation_keys
        == {
            "generation_start_count",
            "generation_advance_count",
            "accepted_completion_count",
            "stale_completion_count",
            "active_generation_count",
            "registry_size",
        },
        "generation diagnostics keys changed",
    )
    _assert(
        event_keys
        == {
            "emitted_event_count",
            "callback_error_count",
            "slow_callback_count",
            "history_overflow_count",
            "rejected_after_close_count",
            "subscriber_count",
            "history_limit",
        },
        "event diagnostics keys changed",
    )
    _assert(
        terminal_keys
        == {
            "terminal_commit_count",
            "duplicate_terminal_count",
            "terminal_regression_count",
            "late_non_terminal_count",
            "registry_size",
        },
        "terminal diagnostics keys changed",
    )
    session.close()

    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_generation_gate_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "FW-RT6-2d-C1-TERMINAL-CALLBACK-COMPATIBILITY:BEGIN",
        "terminal callback reentry:",
        "normal operation after run_turn returns:",
        "Control D candidate:",
        "ROLLED BACK",
        "Control D:",
        "NOT_AUTHORIZED",
    ):
        _assert(phrase in contract, f"corrective contract missing: {phrase}")
    print("[OK] public compatibility, diagnostics, and corrective documentation conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime modules loaded: {forbidden}")
    print("[OK] corrective validation stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_source_contract()
    check_import_safety()
    check_terminal_callback_late_operations()
    check_normal_post_turn_no_active_interrupt()
    check_historical_acceptance()
    check_public_compatibility_and_docs()
    check_import_safety()

    print("v600_rt6_2d_control_c_corrective1_status: implemented-awaiting-review")
    print("v600_rt6_2d_control_c_corrective1_exact_change_surface_count: 3")
    print("v600_rt6_2d_control_c_corrective1_terminal_callback_interrupt_events: 0")
    print("v600_rt6_2d_control_c_corrective1_terminal_callback_cancel_events: 0")
    print("v600_rt6_2d_control_c_corrective1_terminal_callback_state_phase_history_mutated: False")
    print("v600_rt6_2d_control_c_corrective1_normal_post_turn_no_active_preserved: True")
    print("v600_rt6_2d_control_c_corrective1_terminal_acceptance_regression: PASS")
    print("v600_rt6_2d_control_c_corrective1_generation_controls_a_b_c_regression: PASS")
    print("v600_rt6_2d_control_c_corrective1_root_public_names: 121 / unchanged")
    print("v600_rt6_2d_control_c_corrective1_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2d_control_d_candidate_rolled_back: True")
    print("v600_rt6_2d_control_d_authorized: False")
    print("[OK] FW-RT6-2d Control C corrective 1 terminal callback compatibility conforms")


if __name__ == "__main__":
    main()
