"""FW-RT6-2c Control C reentrant/concurrent terminal integration smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or DRC repository operation occurs.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Thread

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "24cf8f3ff151d3732ad99617d78e1999c1d86ed2"
EXPECTED_BASELINE_PARENT = "d41d6ae09c18f9d53996490780ca53035952165c"
EXPECTED_BASELINE_SUBJECT = "refactor/test: adopt realtime terminal registry"
EXPECTED_BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_terminal_registry_session_adoption.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_terminal_registry_reentrant_concurrency.py",
}
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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_BASELINE, "origin/main drift")
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
        _commit_surface(EXPECTED_BASELINE) == EXPECTED_BASELINE_SURFACE,
        "accepted Control B surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control C surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted Control B baseline and exact five-file Control C surface conform")


def check_source_contract() -> None:
    path = PROJECT_ROOT / "framework" / "realtime_session.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for phrase in (
        "_TURN_TERMINAL_EVENT_TYPES = frozenset(",
        "class _LateNonTerminalRejected(RuntimeError):",
        "event_type is not RealtimeEventType.SESSION_CLOSED",
        "not self._terminal_registry.admit_non_terminal(turn_id)",
        "except _LateNonTerminalRejected as rejection:",
        "except _LateNonTerminalRejected:",
        "with self._serialized_operation():\n            request = InterruptRequest(",
        'safe_message="Realtime turn is already terminal."',
    ):
        _assert(phrase in source, f"Control C source phrase missing: {phrase}")

    session_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RealtimeSession"
    )
    methods = {
        node.name: node
        for node in session_class.body
        if isinstance(node, ast.FunctionDef)
    }
    transition_source = ast.get_source_segment(source, methods["_transition"]) or ""
    _assert(
        transition_source.index("admit_non_terminal")
        < transition_source.index("self._set_phase(new_phase)"),
        "terminal admission occurs after phase mutation",
    )
    _assert(
        transition_source.index("admit_non_terminal")
        < transition_source.index("self._state = new_state"),
        "terminal admission occurs after state mutation",
    )
    print("[OK] turn-scoped non-terminal admission precedes all transition mutation")


def check_reentrant_terminal_callback_rejection() -> None:
    import framework

    session = framework.create_realtime_session()
    session.set_barge_in_policy(framework.BargeInPolicy.hard_cancel())
    canonical_events = []
    legacy_events = []
    observations = []
    nested = False

    def callback(event) -> None:
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
        )
        observations.append(
            (first_result, duplicate, interrupt, cancel, flush, barge, before, after)
        )

    session.on_event(callback)
    session.on_legacy_event(legacy_events.append)
    result = session.run_turn(input_text="control-c-reentrant")

    _assert(len(observations) == 1, "terminal callback observation missing")
    first_result, duplicate, interrupt, cancel, flush, barge, before, after = observations[0]
    _assert(result is first_result, "outer result identity drift")
    _assert(duplicate is first_result, "reentrant duplicate did not return first result")
    _assert(
        interrupt.outcome is framework.InterruptOutcome.NO_ACTIVE_TURN,
        "late interrupt result drift",
    )
    _assert(
        cancel.outcome is framework.InterruptOutcome.NO_ACTIVE_TURN,
        "late cancel result drift",
    )
    _assert(
        flush.outcome is framework.OutputFlushOutcome.NOTHING_TO_FLUSH,
        "late flush result drift",
    )
    _assert(not barge.accepted, "late barge-in was accepted")
    _assert(before == after, "late operations changed state/phase/history/event count")
    _assert(len(canonical_events) == 9, "late operation emitted canonical event")
    _assert(len(legacy_events) == 8, "late operation emitted legacy event")
    _assert(
        [int(event.sequence) for event in canonical_events] == list(range(1, 10)),
        "canonical sequence changed during late rejection",
    )
    diagnostics = session.terminal_diagnostics
    _assert(diagnostics["terminal_commit_count"] == 1, "terminal commit count drift")
    _assert(diagnostics["duplicate_terminal_count"] == 1, "duplicate count drift")
    _assert(diagnostics["terminal_regression_count"] == 0, "regression count drift")
    _assert(diagnostics["late_non_terminal_count"] == 4, "late rejection count drift")
    _assert(diagnostics["registry_size"] == 1, "terminal registry size drift")
    _assert(session.state is framework.RealtimeState.IDLE, "outer turn did not restore idle")
    _assert(session.phase is framework.RealtimePhase.IDLE, "outer phase did not restore idle")
    print("[OK] terminal callback reentry returns typed results and emits no late events")


def check_same_turn_concurrent_run_is_one_group() -> None:
    import framework

    session = framework.create_realtime_session()
    events = []
    session.on_event(events.append)
    turn_id = framework.TurnId.new()
    thread_count = 6
    barrier = Barrier(thread_count)
    results = []
    failures = []

    def run(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            results.append(
                session.run_turn(
                    framework.RealtimeTurn(
                        turn_id=turn_id,
                        input_text=f"same-turn-{index}",
                    )
                )
            )
        except Exception as exc:
            failures.append(exc)

    threads = [Thread(target=run, args=(index,)) for index in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    _assert(not any(thread.is_alive() for thread in threads), "same-turn thread hung")
    _assert(not failures, f"same-turn concurrency failure: {failures!r}")
    _assert(len(results) == thread_count, "same-turn result count drift")
    _assert(all(result is results[0] for result in results), "same-turn results differ")
    _assert(len(events) == 9, "same-turn duplicate lifecycle group emitted")
    _assert(
        sum(event.type is framework.RealtimeEventType.TURN_COMPLETED for event in events) == 1,
        "same-turn terminal event count drift",
    )
    diagnostics = session.terminal_diagnostics
    _assert(diagnostics["terminal_commit_count"] == 1, "same-turn commit count drift")
    _assert(diagnostics["duplicate_terminal_count"] == thread_count - 1, "same-turn duplicate count drift")
    _assert(diagnostics["late_non_terminal_count"] == 0, "same-turn late count drift")
    _assert(diagnostics["registry_size"] == 1, "same-turn registry size drift")
    print("[OK] concurrent same-turn callers share one complete lifecycle/result")


def check_different_turn_groups_remain_serialized() -> None:
    import framework

    session = framework.create_realtime_session()
    events = []
    session.on_event(events.append)
    barrier = Barrier(2)
    results = []
    failures = []

    def run(label: str) -> None:
        try:
            barrier.wait(timeout=5)
            results.append(session.run_turn(input_text=label))
        except Exception as exc:
            failures.append(exc)

    threads = [Thread(target=run, args=(label,)) for label in ("one", "two")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    _assert(not any(thread.is_alive() for thread in threads), "different-turn thread hung")
    _assert(not failures, f"different-turn concurrency failure: {failures!r}")
    _assert(len(results) == 2, "different-turn result count drift")
    _assert(len(events) == 18, "different-turn event count drift")
    first_ids = {event.turn_id for event in events[:9]}
    second_ids = {event.turn_id for event in events[9:]}
    _assert(len(first_ids) == 1 and len(second_ids) == 1, "event groups interleaved")
    _assert(first_ids != second_ids, "different turns shared one ID")
    _assert(
        [int(event.sequence) for event in events] == list(range(1, 19)),
        "different-turn sequence drift",
    )
    _assert(session.terminal_diagnostics["registry_size"] == 2, "different-turn registry drift")
    print("[OK] different-turn concurrent operations remain complete serialized groups")


def check_close_contract_is_preserved() -> None:
    import framework

    session = framework.create_realtime_session()
    events = []
    close_requested = False

    def callback(event) -> None:
        nonlocal close_requested
        events.append(event)
        if event.type is framework.RealtimeEventType.TURN_STARTED and not close_requested:
            close_requested = True
            session.close()

    session.on_event(callback)
    result = session.run_turn(input_text="deferred-close")
    _assert(result.is_completed, "deferred close changed turn result")
    _assert(session.is_closed, "deferred close did not complete")
    _assert(events[-1].type is framework.RealtimeEventType.SESSION_CLOSED, "close event missing")
    _assert(
        sum(event.type is framework.RealtimeEventType.SESSION_CLOSED for event in events) == 1,
        "SESSION_CLOSED emitted more than once",
    )
    terminal_results = session.terminal_results
    terminal_diagnostics = dict(session.terminal_diagnostics)
    count = len(events)
    _assert(session.run_turn(input_text="after-close").outcome is framework.TurnOutcome.CLOSED, "closed result drift")
    _assert(len(events) == count, "post-close event emitted")
    _assert(session.terminal_results == terminal_results, "close erased terminal results")
    _assert(dict(session.terminal_diagnostics) == terminal_diagnostics, "close changed terminal diagnostics")
    print("[OK] deferred close and post-close terminal observability remain unchanged")


def check_public_compatibility_and_docs() -> None:
    import inspect
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert("_LateNonTerminalRejected" not in framework.__all__, "private rejection leaked")
    _assert(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == ("project_root", "public_metadata", "real_runtime_enabled"),
        "factory signature drift",
    )
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_realtime_terminal_registry_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-2c-C-REENTRANT-LATE-NON-TERMINAL:BEGIN",
            "RealtimeTerminalRegistry.admit_non_terminal(turn_id) required",
            'terminal_diagnostics["late_non_terminal_count"] only',
            "DEFERRED / FW-RT6-2d",
        ):
            _assert(phrase in text, f"Control C docs missing {phrase}: {relative}")
    print("[OK] root-public compatibility and Control C documentation conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] Control C validation stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_source_contract()
    check_import_safety()
    check_reentrant_terminal_callback_rejection()
    check_same_turn_concurrent_run_is_one_group()
    check_different_turn_groups_remain_serialized()
    check_close_contract_is_preserved()
    check_public_compatibility_and_docs()
    check_import_safety()

    print("v600_rt6_2c_control_c_status: implemented-awaiting-review")
    print("v600_rt6_2c_control_c_exact_change_surface_count: 5")
    print("v600_rt6_2c_control_c_root_public_names: 121 / unchanged")
    print("v600_rt6_2c_control_c_late_admission_before_mutation: True")
    print("v600_rt6_2c_control_c_terminal_callback_late_events: 0")
    print("v600_rt6_2c_control_c_late_diagnostic_policy: count-only")
    print("v600_rt6_2c_control_c_same_turn_concurrent_full_groups: 1")
    print("v600_rt6_2c_control_c_same_turn_terminal_events: 1")
    print("v600_rt6_2c_control_c_same_turn_terminal_records: 1")
    print("v600_rt6_2c_control_c_different_turn_groups_serialized: PASS")
    print("v600_rt6_2c_control_c_close_contract_preserved: PASS")
    print("v600_rt6_2c_control_c_event_diagnostics_changed: False")
    print("v600_rt6_2c_control_c_stale_result_rejection: deferred-FW-RT6-2d")
    print("v600_rt6_2c_control_c_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2c_next_control: FW-RT6-2c Control D")
    print("v600_rt6_2c_next_control_authorized: False")
    print("[OK] FW-RT6-2c Control C reentrant/concurrent terminal integration conforms")


if __name__ == "__main__":
    main()
