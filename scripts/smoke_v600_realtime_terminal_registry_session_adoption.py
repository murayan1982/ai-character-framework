"""FW-RT6-2c Control B RealtimeSession terminal-registry adoption smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or DRC repository operation occurs.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "d41d6ae09c18f9d53996490780ca53035952165c"
EXPECTED_BASELINE_PARENT = "9d0913b9c302b34a2317c4000e3117b814e90447"
EXPECTED_BASELINE_SUBJECT = "feat/test: add realtime terminal registry primitives"
EXPECTED_BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_terminal_registry.py",
    "scripts/smoke_v600_realtime_terminal_registry_primitives.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_terminal_registry_session_adoption.py",
}
EXPECTED_EVENT_DIAGNOSTIC_KEYS = {
    "emitted_event_count",
    "callback_error_count",
    "slow_callback_count",
    "history_overflow_count",
    "rejected_after_close_count",
    "subscriber_count",
    "history_limit",
}
EXPECTED_TERMINAL_DIAGNOSTIC_KEYS = {
    "terminal_commit_count",
    "duplicate_terminal_count",
    "terminal_regression_count",
    "late_non_terminal_count",
    "registry_size",
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
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^")
        == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == EXPECTED_BASELINE_SURFACE,
        "accepted Control A surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted Control A baseline and exact five-file Control B surface conform")


def check_source_contract() -> None:
    session_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    source = session_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(session_path))

    for phrase in (
        "RealtimeTerminalRegistry[RealtimeTurnResult]()",
        "def terminal_results",
        "def terminal_diagnostics",
        "def _duplicate_terminal_result",
        "def _commit_terminal_result",
        "existing_terminal = self._duplicate_terminal_result(turn.turn_id)",
        "committed_result = self._commit_terminal_result(",
        "if decision.accepted:",
    ):
        _assert(phrase in source, f"RealtimeSession source missing: {phrase}")

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")

    for forbidden in (
        "openai",
        "elevenlabs",
        "pyvts",
        "websocket",
        "sounddevice",
        "speech_recognition",
    ):
        _assert(
            not any(forbidden in imported.lower() for imported in imported_modules),
            f"session source imported {forbidden}",
        )

    print("[OK] RealtimeSession source adopts the internal terminal registry without provider coupling")


def check_public_compatibility() -> None:
    import inspect
    import framework
    from framework import create_realtime_session
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert(
        "RealtimeTerminalRegistry" not in framework.__all__,
        "internal registry leaked root-public",
    )
    _assert(
        tuple(inspect.signature(create_realtime_session).parameters)
        == ("project_root", "public_metadata", "real_runtime_enabled"),
        "create_realtime_session signature drift",
    )

    print("[OK] root-public manifest and RealtimeSession factory signature remain unchanged")


def check_atomic_terminal_delivery_and_duplicate_suppression() -> None:
    from framework import (
        RealtimeEventType,
        RealtimeTurn,
        TurnId,
        TurnOutcome,
        create_realtime_session,
    )

    session = create_realtime_session()
    canonical_events = []
    legacy_events = []
    callback_observations = []

    def on_event(event) -> None:
        canonical_events.append(event)
        if event.type is RealtimeEventType.TURN_COMPLETED:
            callback_observations.append(
                (
                    tuple(session.terminal_results),
                    dict(session.terminal_diagnostics),
                )
            )

    session.on_event(on_event)
    session.on_legacy_event(legacy_events.append)

    first_turn_id = TurnId.new()
    first_turn = RealtimeTurn(
        turn_id=first_turn_id,
        input_text="first-input",
        public_metadata={"attempt": "first"},
    )
    first_result = session.run_turn(
        first_turn,
        public_metadata={"attempt": "first"},
    )

    _assert(first_result.outcome is TurnOutcome.COMPLETED, "first outcome drift")
    _assert(len(callback_observations) == 1, "terminal callback count drift")
    callback_results, callback_diagnostics = callback_observations[0]
    _assert(
        callback_results == (first_result,),
        "terminal callback did not observe committed result",
    )
    _assert(
        callback_diagnostics["terminal_commit_count"] == 1,
        "terminal callback did not observe committed diagnostics",
    )
    _assert(
        callback_diagnostics["registry_size"] == 1,
        "terminal callback registry size drift",
    )

    terminal_events_before_duplicate = [
        event
        for event in canonical_events
        if event.type is RealtimeEventType.TURN_COMPLETED
        and event.turn_id == first_turn_id
    ]
    event_count_before_duplicate = len(canonical_events)
    legacy_count_before_duplicate = len(legacy_events)

    duplicate_result = session.run_turn(
        RealtimeTurn(
            turn_id=first_turn_id,
            input_text="must-not-replace",
            public_metadata={"turn_descriptor_attempt": "duplicate"},
        ),
        public_metadata={"attempt": "duplicate"},
    )

    _assert(
        duplicate_result is first_result,
        "duplicate did not return first committed result object",
    )
    _assert(
        len(canonical_events) == event_count_before_duplicate,
        "duplicate run emitted canonical lifecycle events",
    )
    _assert(
        len(legacy_events) == legacy_count_before_duplicate,
        "duplicate run emitted legacy lifecycle events",
    )
    terminal_events_after_duplicate = [
        event
        for event in canonical_events
        if event.type is RealtimeEventType.TURN_COMPLETED
        and event.turn_id == first_turn_id
    ]
    _assert(
        len(terminal_events_before_duplicate) == 1
        and len(terminal_events_after_duplicate) == 1,
        "duplicate terminal event was not suppressed",
    )

    private_record = session._terminal_registry.get(first_turn_id)
    _assert(private_record is not None, "first terminal record missing")
    _assert(private_record.result is first_result, "first result was replaced")
    _assert(private_record.reason == "mock_turn_completed", "terminal reason drift")
    _assert(
        private_record.outcome is TurnOutcome.COMPLETED,
        "terminal outcome drift",
    )
    _assert(
        first_result.input_text == "first-input",
        "duplicate input replaced first result",
    )
    _assert(
        first_result.public_metadata["attempt"] == "first",
        "duplicate metadata replaced first result",
    )

    diagnostics = session.terminal_diagnostics
    _assert(set(diagnostics) == EXPECTED_TERMINAL_DIAGNOSTIC_KEYS, "terminal diagnostic keys drift")
    _assert(diagnostics["terminal_commit_count"] == 1, "commit count drift")
    _assert(diagnostics["duplicate_terminal_count"] == 1, "duplicate count drift")
    _assert(diagnostics["terminal_regression_count"] == 0, "regression count drift")
    _assert(diagnostics["late_non_terminal_count"] == 0, "late count drift")
    _assert(diagnostics["registry_size"] == 1, "registry size drift")
    _assert(
        set(session.event_diagnostics) == EXPECTED_EVENT_DIAGNOSTIC_KEYS,
        "event diagnostic keys changed",
    )
    _assert(session.terminal_results == (first_result,), "terminal result history drift")

    second_turn_id = TurnId.new()
    second_result = session.run_turn(
        RealtimeTurn(turn_id=second_turn_id, input_text="second-input")
    )
    _assert(
        session.terminal_results == (first_result, second_result),
        "terminal result commit order drift",
    )
    _assert(
        session.terminal_diagnostics["terminal_commit_count"] == 2,
        "second commit count drift",
    )
    _assert(
        session.terminal_diagnostics["registry_size"] == 2,
        "second registry size drift",
    )
    _assert(
        sum(
            event.type is RealtimeEventType.TURN_COMPLETED
            and event.turn_id == second_turn_id
            for event in canonical_events
        )
        == 1,
        "second turn terminal event count drift",
    )

    results_snapshot = session.terminal_results
    diagnostics_snapshot = session.terminal_diagnostics
    _assert(type(results_snapshot) is tuple, "terminal_results is not tuple")
    try:
        diagnostics_snapshot["registry_size"] = 99
    except TypeError:
        pass
    else:
        raise AssertionError("terminal_diagnostics mapping was mutable")

    session.close()
    _assert(
        session.terminal_results == results_snapshot,
        "close erased terminal results",
    )
    _assert(
        dict(session.terminal_diagnostics) == dict(diagnostics_snapshot),
        "close changed terminal diagnostics",
    )

    print("[OK] first terminal commits before callback delivery and sequential duplicates emit nothing")


def check_docs() -> None:
    for relative in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-2c-B-REALTIME-SESSION-TERMINAL-ADOPTION:BEGIN",
            "terminal callback observes committed result:",
            "same turn_id retry terminal event:",
            "terminal_results:",
            "terminal_diagnostics:",
            "DEFERRED / FW-RT6-2c Control C",
        ):
            _assert(phrase in text, f"Control B public doc phrase missing: {phrase}")

    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_terminal_registry_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "## Control B — RealtimeSession adoption",
        "1. construct RealtimeTurnResult.completed",
        "2. atomically commit result/outcome/recovery/reason",
        "receives a turn ID that already has a terminal record",
        "current mock `run_turn(...)` completion path",
        "reentrant late non-terminal hardening:",
        "Control C",
    ):
        _assert(phrase in contract, f"Control B terminal contract phrase missing: {phrase}")

    print("[OK] public integration docs and terminal registry contract record Control B adoption")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] Control B validation stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_source_contract()
    check_import_safety()
    check_public_compatibility()
    check_atomic_terminal_delivery_and_duplicate_suppression()
    check_docs()
    check_import_safety()

    print("v600_rt6_2c_control_b_status: implemented-awaiting-review")
    print("v600_rt6_2c_control_b_exact_change_surface_count: 5")
    print("v600_rt6_2c_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_2c_control_b_session_registry_owned: True")
    print("v600_rt6_2c_control_b_terminal_commit_before_event: True")
    print("v600_rt6_2c_control_b_terminal_callback_observes_commit: True")
    print("v600_rt6_2c_control_b_one_terminal_event_per_turn: PASS")
    print("v600_rt6_2c_control_b_duplicate_terminal_suppressed: PASS")
    print("v600_rt6_2c_control_b_duplicate_run_emits_non_terminal_events: False")
    print("v600_rt6_2c_control_b_first_result_replaced: False")
    print("v600_rt6_2c_control_b_terminal_results_read_only: True")
    print("v600_rt6_2c_control_b_terminal_diagnostics_count_only: True")
    print("v600_rt6_2c_control_b_event_diagnostics_changed: False")
    print("v600_rt6_2c_control_b_reentrant_late_non_terminal_hardening: deferred-Control-C")
    print("v600_rt6_2c_control_b_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2c_next_control: FW-RT6-2c Control C")
    print("v600_rt6_2c_next_control_authorized: False")
    print("[OK] FW-RT6-2c Control B RealtimeSession terminal-registry adoption passed")


if __name__ == "__main__":
    main()
