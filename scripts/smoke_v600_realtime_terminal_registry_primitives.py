"""FW-RT6-2c Control A terminal registry primitive smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or host-application repository operation occurs.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Lock, Thread

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "9d0913b9c302b34a2317c4000e3117b814e90447"
EXPECTED_BASELINE_PARENT = "d12e562a0c0b0111386776d50286b1a4cbdf54d2"
EXPECTED_BASELINE_SUBJECT = "docs/test: accept realtime event hub"
EXPECTED_BASELINE_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_event_hub_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_terminal_registry.py",
    "scripts/smoke_v600_realtime_terminal_registry_primitives.py",
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
        "accepted FW-RT6-2b Control D surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted FW-RT6-2b baseline and exact five-file Control A surface conform")


def check_source_and_import_safety() -> None:
    source_path = PROJECT_ROOT / "framework" / "realtime_terminal_registry.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")

    for forbidden in FORBIDDEN_IMPORT_FRAGMENTS:
        _assert(
            not any(forbidden in imported.lower() for imported in imports),
            f"terminal registry imported forbidden dependency: {forbidden}",
        )

    for phrase in (
        "class TerminalCommitStatus",
        "class TerminalRecord",
        "class TerminalCommitDecision",
        "class TerminalRegistryDiagnostics",
        "class RealtimeTerminalRegistry",
        "self._lock = RLock()",
        "validate_terminal_transition(",
        "def admit_non_terminal",
        "def commit(",
    ):
        _assert(phrase in source, f"terminal registry source missing: {phrase}")

    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    for internal_name in (
        "TerminalCommitStatus",
        "TerminalRecord",
        "TerminalCommitDecision",
        "TerminalRegistryDiagnostics",
        "RealtimeTerminalRegistry",
    ):
        _assert(
            internal_name not in framework.__all__,
            f"internal terminal primitive leaked root-public: {internal_name}",
        )
        _assert(
            internal_name not in framework.__dict__,
            f"internal terminal primitive eagerly bound at root: {internal_name}",
        )

    _assert(
        "framework.realtime_terminal_registry" not in sys.modules,
        "root import eagerly loaded terminal registry",
    )
    print("[OK] terminal registry source and root import stayed provider/runtime safe")


def check_first_duplicate_regression_and_retention() -> None:
    from framework.identity import TurnId
    from framework.lifecycle import (
        LifecycleTransitionErrorCode,
        RecoveryAction,
        TurnOutcome,
    )
    from framework.realtime_terminal_registry import (
        RealtimeTerminalRegistry,
        TerminalCommitStatus,
    )

    registry: RealtimeTerminalRegistry[dict[str, str]] = (
        RealtimeTerminalRegistry()
    )
    turn_id = TurnId.new()
    first_result = {"result": "first"}

    first = registry.commit(
        turn_id,
        TurnOutcome.COMPLETED,
        recovery_action=RecoveryAction.REUSE_SESSION,
        reason="completed",
        result=first_result,
    )
    duplicate = registry.commit(
        turn_id,
        TurnOutcome.COMPLETED,
        recovery_action=RecoveryAction.CLOSE_SESSION,
        reason="must-not-replace",
        result={"result": "duplicate"},
    )
    regression = registry.commit(
        turn_id,
        TurnOutcome.FAILED,
        recovery_action=RecoveryAction.PERMANENT_FAILURE,
        reason="must-not-replace",
        result={"result": "regression"},
    )

    _assert(first.accepted, "first terminal was not accepted")
    _assert(
        first.status is TerminalCommitStatus.FIRST_TERMINAL,
        "first status drift",
    )
    _assert(not duplicate.accepted, "duplicate terminal was accepted")
    _assert(
        duplicate.status is TerminalCommitStatus.DUPLICATE_TERMINAL,
        "duplicate status drift",
    )
    _assert(
        duplicate.error_code
        is LifecycleTransitionErrorCode.DUPLICATE_TERMINAL,
        "duplicate lifecycle code drift",
    )
    _assert(not regression.accepted, "terminal regression was accepted")
    _assert(
        regression.status is TerminalCommitStatus.TERMINAL_REGRESSION,
        "regression status drift",
    )
    _assert(
        regression.error_code
        is LifecycleTransitionErrorCode.TERMINAL_REGRESSION,
        "regression lifecycle code drift",
    )

    record = registry.get(turn_id)
    _assert(record is first.record, "first record identity was not retained")
    _assert(duplicate.record is record, "duplicate did not point to first record")
    _assert(regression.record is record, "regression did not point to first record")
    _assert(record is not None, "terminal record missing")
    _assert(record.outcome is TurnOutcome.COMPLETED, "first outcome was replaced")
    _assert(
        record.recovery_action is RecoveryAction.REUSE_SESSION,
        "first recovery action was replaced",
    )
    _assert(record.reason == "completed", "first reason was replaced")
    _assert(record.result is first_result, "first result was replaced")
    _assert(registry.is_terminal(turn_id), "terminal lookup drift")

    _assert(registry.admit_non_terminal(TurnId.new()), "fresh turn was rejected")
    _assert(
        registry.admit_non_terminal(turn_id) is False,
        "late non-terminal was admitted",
    )
    _assert(
        registry.admit_non_terminal(turn_id) is False,
        "second late non-terminal was admitted",
    )

    diagnostics = registry.diagnostics
    _assert(diagnostics.terminal_commit_count == 1, "commit count drift")
    _assert(diagnostics.duplicate_terminal_count == 1, "duplicate count drift")
    _assert(diagnostics.terminal_regression_count == 1, "regression count drift")
    _assert(diagnostics.late_non_terminal_count == 2, "late count drift")
    _assert(diagnostics.registry_size == 1, "registry size drift")
    _assert(len(registry.records) == 1, "record snapshot size drift")

    for frozen_object, attribute, value in (
        (record, "reason", "mutated"),
        (first, "accepted", False),
        (diagnostics, "registry_size", 99),
    ):
        try:
            setattr(frozen_object, attribute, value)
        except (FrozenInstanceError, AttributeError):
            pass
        else:
            raise AssertionError(f"immutable object was mutated: {attribute}")

    diagnostic_fields = set(diagnostics.__dataclass_fields__)
    _assert("result" not in diagnostic_fields, "diagnostics exposed result")
    _assert("reason" not in diagnostic_fields, "diagnostics exposed reason")
    print("[OK] first terminal is retained and duplicate/regression/late attempts are counted and suppressed")


def check_identity_compatibility_and_validation() -> None:
    from framework.lifecycle import TurnOutcome
    from framework.realtime_terminal_registry import RealtimeTerminalRegistry

    registry: RealtimeTerminalRegistry[str] = RealtimeTerminalRegistry()
    legacy_turn = "host-turn-legacy"
    decision = registry.commit(
        legacy_turn,
        TurnOutcome.REJECTED,
        reason="rejected-before-admission",
        result="typed-result",
    )
    _assert(decision.accepted, "compatible legacy turn ID was rejected")
    _assert(
        registry.get(legacy_turn) is decision.record,
        "legacy turn lookup drift",
    )

    invalid_values = (
        None,
        123,
        "fw_session_00000000000000000000000000000000",
        " fw_turn_00000000000000000000000000000000",
    )
    for invalid in invalid_values:
        try:
            registry.commit(invalid, TurnOutcome.FAILED)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid turn ID was accepted: {invalid!r}")

    print("[OK] Framework and compatible legacy turn identity rules conform")


def check_atomic_multi_thread_race() -> None:
    from framework.identity import TurnId
    from framework.lifecycle import RecoveryAction, TurnOutcome
    from framework.realtime_terminal_registry import RealtimeTerminalRegistry

    registry: RealtimeTerminalRegistry[str] = RealtimeTerminalRegistry()
    turn_id = TurnId.new()
    attempt_count = 24
    barrier = Barrier(attempt_count)
    decisions = []
    failures = []
    result_lock = Lock()

    def worker(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            outcome = (
                TurnOutcome.COMPLETED
                if index % 2 == 0
                else TurnOutcome.FAILED
            )
            decision = registry.commit(
                turn_id,
                outcome,
                recovery_action=(
                    RecoveryAction.REUSE_SESSION
                    if outcome is TurnOutcome.COMPLETED
                    else RecoveryAction.RESET_TURN
                ),
                reason=f"candidate-{index}",
                result=f"result-{index}",
            )
            with result_lock:
                decisions.append(decision)
        except Exception as exc:  # test-only capture
            with result_lock:
                failures.append(exc)

    threads = [
        Thread(target=worker, args=(index,))
        for index in range(attempt_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    _assert(
        all(not thread.is_alive() for thread in threads),
        "terminal race worker hung",
    )
    _assert(not failures, f"terminal race failures: {failures!r}")
    _assert(len(decisions) == attempt_count, "terminal race decision count drift")

    accepted = [decision for decision in decisions if decision.accepted]
    suppressed = [decision for decision in decisions if not decision.accepted]
    _assert(len(accepted) == 1, "terminal race accepted more than one winner")
    _assert(
        len(suppressed) == attempt_count - 1,
        "terminal race suppression count drift",
    )
    _assert(len(registry) == 1, "terminal race stored multiple records")

    stored = registry.get(turn_id)
    _assert(stored is accepted[0].record, "race winner record was replaced")
    _assert(
        all(decision.record is stored for decision in suppressed),
        "suppressed decision did not retain first record",
    )

    diagnostics = registry.diagnostics
    _assert(diagnostics.terminal_commit_count == 1, "race commit count drift")
    _assert(
        diagnostics.duplicate_terminal_count
        + diagnostics.terminal_regression_count
        == attempt_count - 1,
        "race suppressed diagnostic total drift",
    )
    _assert(diagnostics.registry_size == 1, "race registry size drift")
    print("[OK] multi-thread terminal race has exactly one atomic first-terminal winner")


def check_docs() -> None:
    for relative in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-2c-A-TERMINAL-REGISTRY-PRIMITIVES:BEGIN",
            "first terminal commit:",
            "accepted atomically",
            "duplicate/regression exception escapes caller:",
            "False",
            "RealtimeSession adoption:",
            "DEFERRED / FW-RT6-2c Control B",
        ):
            _assert(phrase in text, f"Control A doc phrase missing: {phrase}")

    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_terminal_registry_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "FW-RT6-2c Realtime Terminal Registry Contract",
        "FIRST_TERMINAL / accepted",
        "DUPLICATE_TERMINAL / suppressed",
        "TERMINAL_REGRESSION / suppressed",
        "terminal_commit_count",
        "accepted decisions:",
        "1",
        "RealtimeSession adoption:",
        "Control B",
    ):
        _assert(phrase in contract, f"terminal contract phrase missing: {phrase}")

    print("[OK] public integration docs and dedicated terminal registry contract conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] terminal registry primitive validation stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_source_and_import_safety()
    check_import_safety()
    check_first_duplicate_regression_and_retention()
    check_identity_compatibility_and_validation()
    check_atomic_multi_thread_race()
    check_docs()
    check_import_safety()

    print("v600_rt6_2c_control_a_status: implemented-awaiting-review")
    print("v600_rt6_2c_control_a_exact_change_surface_count: 5")
    print("v600_rt6_2c_control_a_root_public_names: 121 / unchanged")
    print("v600_rt6_2c_control_a_realtime_session_changed: False")
    print("v600_rt6_2c_control_a_first_terminal_atomic: True")
    print("v600_rt6_2c_control_a_duplicate_terminal_suppressed: True")
    print("v600_rt6_2c_control_a_terminal_regression_suppressed: True")
    print("v600_rt6_2c_control_a_late_non_terminal_rejected: True")
    print("v600_rt6_2c_control_a_terminal_reason_result_retained: True")
    print("v600_rt6_2c_control_a_diagnostics_count_only: True")
    print("v600_rt6_2c_control_a_multi_thread_winner_count: 1")
    print("v600_rt6_2c_control_a_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2c_next_control: FW-RT6-2c Control B")
    print("v600_rt6_2c_next_control_authorized: False")
    print("[OK] FW-RT6-2c Control A terminal registry primitive foundation passed")


if __name__ == "__main__":
    main()
