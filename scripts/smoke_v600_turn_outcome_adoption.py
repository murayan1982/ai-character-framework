"""FW-RT6-1b Control B turn-outcome adoption smoke.

Offline-safe: validates RealtimeTurnResult terminal outcome/recovery adoption,
legacy v5 value compatibility, lifecycle semantic preservation, and explicit
deferrals without provider or network execution.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "6443e524d8bc4e32eb4d7e7ecba75e26244c9f10"
EXPECTED_CONTROL_A_COMMIT = "c2dc6f26711d013a4e0eb9c912e41eab49afdfda"
CORRECTIVE_SUBJECT = "docs/test: correct v6 checkpoint baselines"
CORRECTIVE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
}
EXPECTED_IDENTITY_CONTROL_B_BASELINE = "0b435e407a3fec018dce29b7446082948d1d2307"
EXPECTED_LIFECYCLE_CONTROL_A_BASELINE = "c89ca5f0ae186564a8f7bced2ea7ce1462459172"
FORBIDDEN_SYNTHETIC_BASELINES = ("faef0cf09dc965ce5069687cd021f00bbfebdc0f", "f6a279e57b3f8ff966dfdca107a7dce8cc3b84fe")
EXPECTED_SURFACE = {
    "framework/realtime.py",
    "scripts/smoke_v600_turn_outcome_adoption.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "docs/v600_lifecycle_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
FORBIDDEN_IMPORTS = {
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "speech_recognition", "pyaudio", "google.genai", "xai_sdk",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
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
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control B baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control B surface: {sorted(_changed_paths())}")
    _assert(_git("show", "-s", "--format=%s", EXPECTED_BASELINE_HEAD) == CORRECTIVE_SUBJECT, "corrective subject drift")
    _assert(_git("rev-parse", f"{EXPECTED_BASELINE_HEAD}^") == EXPECTED_CONTROL_A_COMMIT, "corrective parent drift")
    corrective_surface = {
        line.replace("\\", "/")
        for line in _git("diff-tree", "--no-commit-id", "--name-only", "-r", EXPECTED_BASELINE_HEAD).splitlines()
        if line.strip()
    }
    _assert(corrective_surface == CORRECTIVE_SURFACE, "corrective exact surface drift")
    print("[OK] corrective history and Control B exact six-file surface match")


def check_control_a_semantics() -> None:
    import smoke_v600_lifecycle_models as control_a

    control_a.check_root_public_manifest()
    control_a.check_enum_contracts()
    control_a.check_phase_matrix()
    control_a.check_terminal_validation()
    control_a.check_import_safety()
    print("[OK] accepted Control A lifecycle semantics remain intact")


def check_turn_outcome_contract() -> None:
    import framework

    turn_id = framework.TurnId.new()
    completed = framework.RealtimeTurnResult.completed(turn_id=turn_id)
    interrupted = framework.RealtimeTurnResult.interrupted(turn_id=turn_id)
    cancelled = framework.RealtimeTurnResult.cancelled(turn_id=turn_id)
    failed = framework.RealtimeTurnResult.failed(turn_id=turn_id)
    rejected = framework.RealtimeTurnResult.rejected(turn_id=turn_id)
    closed = framework.RealtimeTurnResult.closed(turn_id=turn_id)

    expected = (
        (completed, framework.TurnOutcome.COMPLETED, framework.RecoveryAction.NONE, False),
        (interrupted, framework.TurnOutcome.INTERRUPTED, framework.RecoveryAction.RESET_TURN, True),
        (cancelled, framework.TurnOutcome.CANCELLED, framework.RecoveryAction.RESET_TURN, True),
        (failed, framework.TurnOutcome.FAILED, framework.RecoveryAction.RESET_SESSION, False),
        (rejected, framework.TurnOutcome.REJECTED, framework.RecoveryAction.REUSE_SESSION, False),
        (closed, framework.TurnOutcome.CLOSED, framework.RecoveryAction.NONE, False),
    )
    for result, outcome, recovery, retryable in expected:
        _assert(type(result.outcome) is framework.TurnOutcome, "outcome did not normalize to TurnOutcome")
        _assert(result.outcome is outcome, "turn outcome drift")
        _assert(type(result.recovery_action) is framework.RecoveryAction, "recovery did not normalize")
        _assert(result.recovery_action is recovery, "default recovery mapping drift")
        _assert(result.retryable is retryable, "retryable contract drift")
        _assert(result.is_terminal, "constructed turn result must be terminal")

    _assert(completed.is_completed, "completed result should be completed")
    _assert(not interrupted.is_completed, "interrupted result should not be completed")
    _assert(cancelled.public_error_code is framework.RealtimeErrorCode.CANCELLED, "cancelled error code drift")
    _assert(rejected.public_error_code is framework.RealtimeErrorCode.REJECTED, "rejected error code drift")

    explicit = framework.RealtimeTurnResult.failed(
        turn_id=turn_id,
        recovery_action="reconnect",
    )
    _assert(explicit.recovery_action is framework.RecoveryAction.RECONNECT, "explicit recovery normalization drift")
    print("[OK] RealtimeTurnResult uses canonical terminal outcomes and recovery actions")


def check_legacy_compatibility_and_rejections() -> None:
    import framework

    turn_id = framework.TurnId.new()
    terminal_states = (
        (framework.RealtimeState.COMPLETED, framework.TurnOutcome.COMPLETED),
        (framework.RealtimeState.INTERRUPTED, framework.TurnOutcome.INTERRUPTED),
        (framework.RealtimeState.FAILED, framework.TurnOutcome.FAILED),
        (framework.RealtimeState.CLOSED, framework.TurnOutcome.CLOSED),
    )
    for legacy, canonical in terminal_states:
        result = framework.RealtimeTurnResult(turn_id=turn_id, outcome=legacy)
        _assert(result.outcome is canonical, "legacy terminal state normalization drift")
        _assert(result.outcome == legacy, "legacy value-level comparison drift")

    for phase in (
        framework.RealtimeState.IDLE,
        framework.RealtimeState.LISTENING,
        framework.RealtimeState.TRANSCRIBING,
        framework.RealtimeState.THINKING,
        framework.RealtimeState.SPEAKING,
        framework.RealtimeState.MOTION,
        "thinking",
    ):
        try:
            framework.RealtimeTurnResult(turn_id=turn_id, outcome=phase)
        except framework.LifecycleTransitionError as exc:
            _assert(
                exc.code is framework.LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH,
                "phase/outcome mismatch code drift",
            )
            _assert(exc.safe_message == str(exc), "typed mismatch should expose fixed safe message")
        else:
            raise AssertionError(f"transient phase accepted as terminal outcome: {phase}")

    invalid = (
        dict(outcome=framework.TurnOutcome.COMPLETED, recovery_action=framework.RecoveryAction.RESET_TURN),
        dict(outcome=framework.TurnOutcome.CLOSED, recovery_action=framework.RecoveryAction.RESET_SESSION),
        dict(outcome=framework.TurnOutcome.FAILED, recovery_action=framework.RecoveryAction.CLOSE_SESSION, retryable=True),
        dict(outcome=framework.TurnOutcome.FAILED, recovery_action=framework.RecoveryAction.PERMANENT_FAILURE, retryable=True),
    )
    for values in invalid:
        try:
            framework.RealtimeTurnResult(turn_id=turn_id, **values)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid recovery contract accepted: {values}")
    print("[OK] legacy terminal values remain compatible and invalid phase/recovery inputs are rejected")


def check_session_compatibility_and_deferrals() -> None:
    import framework

    session = framework.create_realtime_session()
    result = session.run_turn(input_text="hello")
    _assert(result.outcome is framework.TurnOutcome.COMPLETED, "run_turn should return TurnOutcome.COMPLETED")
    _assert(result.recovery_action is framework.RecoveryAction.NONE, "run_turn recovery drift")
    _assert(session.state is framework.RealtimeState.IDLE, "legacy session state changed in Control B")
    session.close()
    closed = session.run_turn(input_text="after close")
    _assert(closed.outcome is framework.TurnOutcome.CLOSED, "closed run_turn outcome drift")
    _assert(closed.recovery_action is framework.RecoveryAction.NONE, "closed run_turn recovery drift")

    realtime_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    event_source = (PROJECT_ROOT / "framework/realtime.py").read_text(encoding="utf-8")
    _assert("RealtimePhase" not in realtime_source, "RealtimeSession phase adopted prematurely")
    _assert("sequence:" not in event_source, "RealtimeEvent sequence added prematurely")
    _assert("generation_id:" not in event_source, "RealtimeEvent generation added prematurely")
    _assert("terminal:" not in event_source, "RealtimeEvent terminal flag added prematurely")
    _assert("terminal_registry" not in realtime_source, "terminal registry added prematurely")
    print("[OK] session legacy state and Control C/1c/registry deferrals remain intact")


def check_docs_and_import_safety() -> None:
    for relative in (
        "docs/v600_lifecycle_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert("FW-RT6-1b-B-TURN-OUTCOME-ADOPTION:BEGIN" in text, f"Control B marker missing: {relative}")
        _assert("__CONTROL_" not in text, f"unresolved placeholder: {relative}")
        _assert(
            EXPECTED_LIFECYCLE_CONTROL_A_BASELINE in text,
            f"Control A lifecycle baseline drift: {relative}",
        )
        for forbidden in FORBIDDEN_SYNTHETIC_BASELINES:
            _assert(forbidden not in text, f"synthetic baseline leaked into {relative}")
        if relative in {"docs/public_facade.md", "docs/app_integration_contract.md"}:
            _assert(
                EXPECTED_IDENTITY_CONTROL_B_BASELINE in text,
                f"identity Control B baseline drift: {relative}",
            )
    contract = (PROJECT_ROOT / "docs/v600_lifecycle_contract.md").read_text(encoding="utf-8")
    for phrase in (
        "RealtimeTurnResult canonical outcome: TurnOutcome",
        "cancelled and interrupted: DISTINCT",
        "RealtimeSession phase adoption: DEFERRED TO CONTROL C",
        "terminal registry: NOT IMPLEMENTED",
    ):
        _assert(phrase in contract, f"Control B lifecycle contract phrase missing: {phrase}")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider SDK imported by Control B smoke")
    print("[OK] Control B documentation and provider-safe import contract conform")


def main() -> None:
    check_repository_contract()
    check_control_a_semantics()
    check_turn_outcome_contract()
    check_legacy_compatibility_and_rejections()
    check_session_compatibility_and_deferrals()
    check_docs_and_import_safety()
    print("v600_turn_outcome_adoption_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 6")
    print("v600_root_public_name_count: 104")
    print("v600_realtime_turn_result_outcome_type: TurnOutcome")
    print("v600_recovery_action_adopted: True")
    print("v600_cancelled_interrupted_distinct: True")
    print("v600_legacy_terminal_state_comparison_preserved: True")
    print("v600_transient_phase_outcome_rejected: True")
    print("v600_realtime_session_phase_adopted: False")
    print("v600_event_sequence_generation_wired: False")
    print("v600_terminal_registry_implemented: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1b Control C")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1b Control B turn-outcome adoption smoke passed")


if __name__ == "__main__":
    main()
