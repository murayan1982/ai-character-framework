"""Aggregate FW-RT6-1b lifecycle foundation acceptance checker.

Mock-safe: this checker performs no provider, network, microphone, playback,
VTube Studio, or host-application operation.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTROL_C_COMMIT = "8bc71a990762c8161d262bc7617a44e0dfb2c8e3"
EXPECTED_CONTROL_B_COMMIT = "5cbb1cbe40805db4aa475149030099ee68eb889b"
EXPECTED_CORRECTIVE_COMMIT = "6443e524d8bc4e32eb4d7e7ecba75e26244c9f10"
EXPECTED_CONTROL_A_COMMIT = "c2dc6f26711d013a4e0eb9c912e41eab49afdfda"
EXPECTED_CONTROL_A_PARENT = "c89ca5f0ae186564a8f7bced2ea7ce1462459172"

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_lifecycle_acceptance.py",
}
CONTROL_A_SUBJECT = "feat/test: add public lifecycle models"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_lifecycle_contract.md",
    "framework/__init__.py",
    "framework/lifecycle.py",
    "framework/public_api.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_lifecycle_models.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}
CORRECTIVE_SUBJECT = "docs/test: correct v6 checkpoint baselines"
CORRECTIVE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
}
CONTROL_B_SUBJECT = "refactor/test: separate realtime turn outcomes"
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_lifecycle_contract.md",
    "framework/realtime.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_turn_outcome_adoption.py",
}
CONTROL_C_SUBJECT = "refactor/test: adopt realtime phase model"
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_lifecycle_contract.md",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_phase_adoption.py",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    "openai", "elevenlabs", "pyvts", "websocket", "pyaudio",
    "sounddevice", "speech_recognition",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    import subprocess
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
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
            for line in _git(*args).splitlines() if line.strip()
        )
    return paths


def _commit_subject(commit: str) -> str:
    return _git("show", "-s", "--format=%s", commit)


def _commit_parent(commit: str) -> str:
    return _git("rev-parse", f"{commit}^")


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines() if line.strip()
    }


def _assert_commit(commit: str, parent: str, subject: str, surface: set[str]) -> None:
    _assert(_commit_subject(commit) == subject, f"subject drift: {subject}")
    _assert(_commit_parent(commit) == parent, f"parent drift: {subject}")
    _assert(_commit_surface(commit) == surface, f"surface drift: {subject}")


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_CONTROL_C_COMMIT, "unexpected Control D baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control D surface: {sorted(_changed_paths())}")
    _assert_commit(EXPECTED_CONTROL_A_COMMIT, EXPECTED_CONTROL_A_PARENT, CONTROL_A_SUBJECT, CONTROL_A_SURFACE)
    _assert_commit(EXPECTED_CORRECTIVE_COMMIT, EXPECTED_CONTROL_A_COMMIT, CORRECTIVE_SUBJECT, CORRECTIVE_SURFACE)
    _assert_commit(EXPECTED_CONTROL_B_COMMIT, EXPECTED_CORRECTIVE_COMMIT, CONTROL_B_SUBJECT, CONTROL_B_SURFACE)
    _assert_commit(EXPECTED_CONTROL_C_COMMIT, EXPECTED_CONTROL_B_COMMIT, CONTROL_C_SUBJECT, CONTROL_C_SURFACE)
    print("[OK] Control A/corrective/B/C history and exact Control D surface conform")


def check_public_manifest(framework) -> None:
    from framework.public_api import (
        IDENTITY_PUBLIC_EXPORTS, LIFECYCLE_PUBLIC_EXPORTS,
        PUBLIC_API_GROUPS, PUBLIC_API_NAMES,
    )
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 104, "root-public count drift")
    _assert(len(PUBLIC_API_NAMES) == len(set(PUBLIC_API_NAMES)), "duplicate root-public name")
    flattened = tuple(name for group in PUBLIC_API_GROUPS.values() for name in group)
    _assert(flattened == PUBLIC_API_NAMES, "public groups do not flatten canonically")
    _assert(PUBLIC_API_NAMES[95:99] == tuple(IDENTITY_PUBLIC_EXPORTS), "identity position drift")
    _assert(
        tuple(LIFECYCLE_PUBLIC_EXPORTS) == (
            "RealtimePhase", "TurnOutcome", "RecoveryAction",
            "LifecycleTransitionErrorCode", "LifecycleTransitionError",
        ),
        "lifecycle suffix drift",
    )
    _assert(PUBLIC_API_NAMES[-5:] == tuple(LIFECYCLE_PUBLIC_EXPORTS), "lifecycle names not appended")
    print("[OK] canonical 104-name public manifest preserves the 99-name prefix")


def _expect_lifecycle_error(factory, framework, code) -> None:
    try:
        factory()
    except framework.LifecycleTransitionError as exc:
        _assert(exc.code is code, f"unexpected lifecycle error code: {exc.code}")
        _assert(str(exc) == exc.safe_message, "unsafe lifecycle error text")
    else:
        raise AssertionError(f"expected lifecycle error: {code.value}")


def check_lifecycle_primitives(framework) -> None:
    from framework.lifecycle import validate_phase_transition, validate_terminal_transition
    _assert([x.value for x in framework.RealtimePhase] == [
        "idle", "listening", "transcribing", "thinking",
        "speaking", "motion", "recovering",
    ], "RealtimePhase values drift")
    _assert([x.value for x in framework.TurnOutcome] == [
        "completed", "interrupted", "cancelled", "failed", "rejected", "closed",
    ], "TurnOutcome values drift")
    _assert(set(x.value for x in framework.RealtimePhase).isdisjoint(
        set(x.value for x in framework.TurnOutcome)
    ), "phase/outcome values overlap")
    _assert(framework.TurnOutcome.CANCELLED is not framework.TurnOutcome.INTERRUPTED, "cancelled aliases interrupted")
    _assert(validate_phase_transition("idle", "listening") is framework.RealtimePhase.LISTENING, "valid phase transition drift")
    _assert(validate_phase_transition("speaking", "speaking") is framework.RealtimePhase.SPEAKING, "idempotent phase drift")
    _expect_lifecycle_error(
        lambda: validate_phase_transition("speaking", "thinking"), framework,
        framework.LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION,
    )
    _assert(validate_terminal_transition(None, "completed") is framework.TurnOutcome.COMPLETED, "first terminal drift")
    _expect_lifecycle_error(
        lambda: validate_terminal_transition("completed", "completed"), framework,
        framework.LifecycleTransitionErrorCode.DUPLICATE_TERMINAL,
    )
    _expect_lifecycle_error(
        lambda: validate_terminal_transition("completed", "failed"), framework,
        framework.LifecycleTransitionErrorCode.TERMINAL_REGRESSION,
    )
    print("[OK] phase matrix and terminal validation primitive conform")


def check_turn_result_contract(framework) -> None:
    turn_id = framework.TurnId.new()
    cases = (
        (framework.RealtimeTurnResult.completed(turn_id=turn_id), framework.TurnOutcome.COMPLETED, framework.RecoveryAction.NONE, False),
        (framework.RealtimeTurnResult.interrupted(turn_id=turn_id), framework.TurnOutcome.INTERRUPTED, framework.RecoveryAction.RESET_TURN, True),
        (framework.RealtimeTurnResult.cancelled(turn_id=turn_id), framework.TurnOutcome.CANCELLED, framework.RecoveryAction.RESET_TURN, True),
        (framework.RealtimeTurnResult.failed(turn_id=turn_id), framework.TurnOutcome.FAILED, framework.RecoveryAction.RESET_SESSION, False),
        (framework.RealtimeTurnResult.rejected(turn_id=turn_id), framework.TurnOutcome.REJECTED, framework.RecoveryAction.REUSE_SESSION, False),
        (framework.RealtimeTurnResult.closed(turn_id=turn_id), framework.TurnOutcome.CLOSED, framework.RecoveryAction.NONE, False),
    )
    for result, outcome, recovery, retryable in cases:
        _assert(type(result.outcome) is framework.TurnOutcome, "non-canonical result outcome")
        _assert(result.outcome is outcome, "result outcome drift")
        _assert(type(result.recovery_action) is framework.RecoveryAction, "non-canonical recovery action")
        _assert(result.recovery_action is recovery, "recovery mapping drift")
        _assert(result.retryable is retryable, "retryable mapping drift")
        _assert(result.is_terminal, "terminal result classified non-terminal")
    legacy = framework.RealtimeTurnResult(turn_id=turn_id, outcome=framework.RealtimeState.COMPLETED)
    _assert(legacy.outcome is framework.TurnOutcome.COMPLETED, "legacy terminal input did not normalize")
    _assert(legacy.outcome == framework.RealtimeState.COMPLETED, "legacy value comparison broke")
    _expect_lifecycle_error(
        lambda: framework.RealtimeTurnResult(turn_id=turn_id, outcome=framework.RealtimeState.THINKING),
        framework, framework.LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH,
    )
    print("[OK] canonical turn outcomes, recovery actions, and legacy comparison conform")


def check_session_phase_contract(framework) -> None:
    session = framework.create_realtime_session()
    snapshots = []
    session.on_event(lambda event: snapshots.append((event.type, event.state, session.phase)))
    session.emit_created()
    result = session.run_turn(input_text="lifecycle aggregate")
    expected = [
        (framework.RealtimeEventType.SESSION_CREATED, framework.RealtimeState.IDLE, framework.RealtimePhase.IDLE),
        (framework.RealtimeEventType.TURN_STARTED, framework.RealtimeState.LISTENING, framework.RealtimePhase.LISTENING),
        (framework.RealtimeEventType.VOICE_INPUT_STARTED, framework.RealtimeState.LISTENING, framework.RealtimePhase.LISTENING),
        (framework.RealtimeEventType.VOICE_INPUT_COMPLETED, framework.RealtimeState.TRANSCRIBING, framework.RealtimePhase.TRANSCRIBING),
        (framework.RealtimeEventType.TEXT_CHAT_STARTED, framework.RealtimeState.THINKING, framework.RealtimePhase.THINKING),
        (framework.RealtimeEventType.TEXT_CHAT_COMPLETED, framework.RealtimeState.SPEAKING, framework.RealtimePhase.SPEAKING),
        (framework.RealtimeEventType.VOICE_OUTPUT_STARTED, framework.RealtimeState.SPEAKING, framework.RealtimePhase.SPEAKING),
        (framework.RealtimeEventType.VOICE_OUTPUT_COMPLETED, framework.RealtimeState.COMPLETED, framework.RealtimePhase.SPEAKING),
        (framework.RealtimeEventType.TURN_COMPLETED, framework.RealtimeState.COMPLETED, framework.RealtimePhase.SPEAKING),
    ]
    _assert(snapshots == expected, f"legacy event/phase progression drift: {snapshots}")
    _assert(result.outcome is framework.TurnOutcome.COMPLETED, "run_turn outcome drift")
    _assert(session.state is framework.RealtimeState.IDLE, "post-turn legacy state drift")
    _assert(session.phase is framework.RealtimePhase.IDLE, "post-turn phase drift")
    _assert(session.info.phase is framework.RealtimePhase.IDLE, "session info phase drift")
    turn = framework.RealtimeTurn(state=framework.RealtimeState.THINKING)
    _assert(turn.phase is framework.RealtimePhase.THINKING, "RealtimeTurn phase normalization drift")

    invalid = framework.create_realtime_session()
    invalid._set_phase(framework.RealtimePhase.SPEAKING)
    _expect_lifecycle_error(
        lambda: invalid._set_phase(framework.RealtimePhase.THINKING), framework,
        framework.LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION,
    )
    invalid.close()
    _assert(invalid.phase is None, "closed session retained canonical phase")
    _assert(invalid.state is framework.RealtimeState.CLOSED, "closed legacy state drift")
    _expect_lifecycle_error(
        lambda: invalid._set_phase(framework.RealtimePhase.IDLE), framework,
        framework.LifecycleTransitionErrorCode.SESSION_CLOSED,
    )
    session.close()
    print("[OK] RealtimeSession canonical phase and legacy event/state compatibility conform")


def check_truthful_deferrals(framework) -> None:
    event_fields = {field.name for field in fields(framework.RealtimeEvent)}
    for name in ("phase", "sequence", "generation_id", "terminal", "payload"):
        _assert(name not in event_fields, f"RealtimeEvent overreach: {name}")
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8").lower()
    for fragment in (
        "_terminal_registry", "terminal_registry =", "atomic_terminal_commit",
        "duplicate_terminal_suppression", "exactly_once_terminal",
    ):
        _assert(fragment not in source, f"terminal registry/suppression overreach: {fragment}")
    _assert("generation_id" not in source, "generation runtime wiring appeared")
    print("[OK] event-v6, terminal registry, exactly-once, and generation work remain deferred")


def check_docs() -> None:
    required = {
        "README.md": (
            "FW-RT6-1b-D-LIFECYCLE-ACCEPTANCE",
            "per-session terminal registry: False",
            "next checkpoint: FW-RT6-1c",
        ),
        "docs/v600_tasklist.md": (
            "FW-RT6-1b-D-ACCEPTANCE-SYNC",
            "- [x] transient phase enumを定義する。",
            "exactly-once terminal registry:\nFalse / DEFERRED",
        ),
        "docs/v600_current_source_gap_inventory.md": (
            "FW-RT6-1b-D-GAP-RESOLUTION-SYNC",
            "common RealtimePhase model: RESOLVED",
            "G-04 per-session terminal registry: UNRESOLVED",
            "G-03 RealtimeEvent sequence: UNRESOLVED / FW-RT6-1c",
        ),
    }
    for relative, fragments in required.items():
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for fragment in fragments:
            _assert(fragment in text, f"missing lifecycle acceptance doc fragment: {relative}: {fragment}")
        _assert("__CONTROL_" not in text, f"unresolved placeholder: {relative}")
    print("[OK] README, tasklist, and gap inventory record truthful lifecycle acceptance")


def check_import_safety() -> None:
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    after = set(sys.modules) - before
    forbidden = sorted(
        module for module in after
        if any(fragment in module.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports: {forbidden}")
    check_public_manifest(framework)
    check_lifecycle_primitives(framework)
    check_turn_result_contract(framework)
    check_session_phase_contract(framework)
    check_truthful_deferrals(framework)
    print("[OK] aggregate lifecycle import stayed provider/network/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_docs()
    print("v600_lifecycle_acceptance_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 4")
    print("v600_root_public_name_count: 104")
    print("v600_transient_phase_terminal_outcome_separate: True")
    print("v600_realtime_turn_result_outcome_type: TurnOutcome")
    print("v600_recovery_action_adopted: True")
    print("v600_realtime_session_phase_type: RealtimePhase-or-None")
    print("v600_legacy_realtime_state_preserved: True")
    print("v600_invalid_transition_typed_failure: True")
    print("v600_terminal_regression_prohibited: True")
    print("v600_terminal_registry_implemented: False")
    print("v600_exactly_once_terminal_enforcement: False")
    print("v600_realtime_event_v6_fields_added: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_checkpoint: FW-RT6-1c")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-1b lifecycle foundation aggregate acceptance passed")


if __name__ == "__main__":
    main()
