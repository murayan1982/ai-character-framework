"""FW-RT6-1b Control C realtime phase adoption smoke.

Mock-safe: this smoke performs no provider, network, microphone, playback,
VTube Studio, or host-application execution.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "5cbb1cbe40805db4aa475149030099ee68eb889b"
EXPECTED_CORRECTIVE_COMMIT = "6443e524d8bc4e32eb4d7e7ecba75e26244c9f10"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_lifecycle_contract.md",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_phase_adoption.py",
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
FORBIDDEN_IMPORT_FRAGMENTS = (
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
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
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
        if line.strip()
    }


def check_repository_contract() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control C baseline")
    _require(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control C surface: {sorted(_changed_paths())}")
    _require(_git("show", "-s", "--format=%s", EXPECTED_BASELINE_HEAD) == CONTROL_B_SUBJECT, "Control B subject drift")
    _require(_git("rev-parse", f"{EXPECTED_BASELINE_HEAD}^") == EXPECTED_CORRECTIVE_COMMIT, "Control B parent drift")
    _require(_commit_surface(EXPECTED_BASELINE_HEAD) == CONTROL_B_SURFACE, "Control B exact surface drift")
    print("[OK] Control C baseline and exact eight-file surface match")


def import_framework_safely():
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    hits = sorted(
        name
        for name in loaded
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _require(not hits, f"provider/runtime imports were loaded: {hits[:12]}")
    return framework


def check_public_phase_types(framework) -> None:
    _require(len(framework.__all__) == 104, "root-public count drift")
    _require(
        tuple(framework.__all__[-5:])
        == (
            "RealtimePhase",
            "TurnOutcome",
            "RecoveryAction",
            "LifecycleTransitionErrorCode",
            "LifecycleTransitionError",
        ),
        "lifecycle public suffix drift",
    )

    info = framework.RealtimeSessionInfo()
    _require(info.phase is framework.RealtimePhase.IDLE, "default session info phase should be idle")
    closed_info = framework.RealtimeSessionInfo(state=framework.RealtimeState.CLOSED)
    _require(closed_info.phase is None, "closed legacy session info should have no canonical phase")

    turn = framework.RealtimeTurn(state=framework.RealtimeState.THINKING)
    _require(turn.phase is framework.RealtimePhase.THINKING, "RealtimeTurn phase should derive from legacy state")
    explicit = framework.RealtimeTurn(phase="speaking")
    _require(explicit.phase is framework.RealtimePhase.SPEAKING, "serialized RealtimeTurn phase should normalize")

    try:
        framework.RealtimeTurn(state=framework.RealtimeState.COMPLETED)
    except framework.LifecycleTransitionError as exc:
        _require(
            exc.code is framework.LifecycleTransitionErrorCode.PHASE_OUTCOME_MISMATCH,
            "terminal RealtimeTurn state mismatch code drift",
        )
    else:
        raise AssertionError("terminal legacy state was accepted as a transient RealtimeTurn phase")

    _require("phase" not in {field.name for field in fields(framework.RealtimeEvent)}, "RealtimeEvent phase field belongs to FW-RT6-1c")
    print("[OK] RealtimeTurn and RealtimeSessionInfo expose canonical transient phases")


def check_session_phase_progression(framework) -> None:
    session = framework.create_realtime_session()
    observations: list[tuple[object, object, object]] = []

    def record(event) -> None:
        observations.append((event.type, session.phase, session.state))

    session.on_event(record)
    _require(session.phase is framework.RealtimePhase.IDLE, "new session phase should be idle")
    _require(session.info.phase is framework.RealtimePhase.IDLE, "new session info phase should be idle")

    session.emit_created()
    result = session.run_turn(input_text="phase smoke")

    expected = [
        (framework.RealtimeEventType.SESSION_CREATED, framework.RealtimePhase.IDLE, framework.RealtimeState.IDLE),
        (framework.RealtimeEventType.TURN_STARTED, framework.RealtimePhase.LISTENING, framework.RealtimeState.LISTENING),
        (framework.RealtimeEventType.VOICE_INPUT_STARTED, framework.RealtimePhase.LISTENING, framework.RealtimeState.LISTENING),
        (framework.RealtimeEventType.VOICE_INPUT_COMPLETED, framework.RealtimePhase.TRANSCRIBING, framework.RealtimeState.TRANSCRIBING),
        (framework.RealtimeEventType.TEXT_CHAT_STARTED, framework.RealtimePhase.THINKING, framework.RealtimeState.THINKING),
        (framework.RealtimeEventType.TEXT_CHAT_COMPLETED, framework.RealtimePhase.SPEAKING, framework.RealtimeState.SPEAKING),
        (framework.RealtimeEventType.VOICE_OUTPUT_STARTED, framework.RealtimePhase.SPEAKING, framework.RealtimeState.SPEAKING),
        (framework.RealtimeEventType.VOICE_OUTPUT_COMPLETED, framework.RealtimePhase.SPEAKING, framework.RealtimeState.COMPLETED),
        (framework.RealtimeEventType.TURN_COMPLETED, framework.RealtimePhase.SPEAKING, framework.RealtimeState.COMPLETED),
    ]
    _require(observations == expected, f"phase/event progression drift: {observations}")
    _require(result.outcome is framework.TurnOutcome.COMPLETED, "run_turn terminal outcome drift")
    _require(session.phase is framework.RealtimePhase.IDLE, "completed turn should return phase to idle")
    _require(session.state is framework.RealtimeState.IDLE, "completed turn should preserve legacy idle state")
    _require(session.info.phase is framework.RealtimePhase.IDLE, "completed session info phase should be idle")
    print("[OK] mock turn uses canonical phase progression and preserves legacy event states")


def check_transition_and_interrupt_contract(framework) -> None:
    invalid = framework.create_realtime_session()
    invalid._set_phase(framework.RealtimePhase.SPEAKING)
    try:
        invalid._set_phase(framework.RealtimePhase.THINKING)
    except framework.LifecycleTransitionError as exc:
        _require(
            exc.code is framework.LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION,
            "invalid session phase transition code drift",
        )
    else:
        raise AssertionError("invalid session phase transition was accepted")

    active = framework.create_realtime_session()
    active._active_turn_id = framework.TurnId.new()
    active._state = framework.RealtimeState.LISTENING
    active._set_phase(framework.RealtimePhase.LISTENING)
    interrupt_observations: list[tuple[object, object]] = []
    active.on_event(lambda event: interrupt_observations.append((event.type, active.phase)))
    result = active.interrupt(
        framework.InterruptRequest.user_barge_in(turn_id=active._active_turn_id)
    )
    _require(result.outcome is framework.InterruptOutcome.NOT_IMPLEMENTED, "mock active interrupt outcome drift")
    _require(
        interrupt_observations[-1]
        == (framework.RealtimeEventType.INTERRUPT_UNSUPPORTED, framework.RealtimePhase.RECOVERING),
        "active interrupt should expose recovering during terminal legacy event",
    )
    _require(active.phase is framework.RealtimePhase.IDLE, "interrupt should return canonical phase to idle")
    _require(active.state is framework.RealtimeState.IDLE, "interrupt should preserve legacy idle recovery")
    print("[OK] session phase matrix and mock interrupt recovery are enforced")


def check_close_and_deferrals(framework) -> None:
    session = framework.create_realtime_session()
    session.close()
    _require(session.is_closed, "closed flag drift")
    _require(session.phase is None, "closed session should have no canonical active phase")
    _require(session.info.phase is None, "closed session info should have no canonical active phase")
    _require(session.state is framework.RealtimeState.CLOSED, "legacy closed state drift")
    result = session.run_turn(input_text="after close")
    _require(result.outcome is framework.TurnOutcome.CLOSED, "closed turn outcome drift")

    try:
        session._set_phase(framework.RealtimePhase.IDLE)
    except framework.LifecycleTransitionError as exc:
        _require(
            exc.code is framework.LifecycleTransitionErrorCode.SESSION_CLOSED,
            "closed session transition code drift",
        )
    else:
        raise AssertionError("closed session accepted an active phase transition")

    event_fields = {field.name for field in fields(framework.RealtimeEvent)}
    _require("sequence" not in event_fields, "EventSequence wiring belongs to FW-RT6-1c")
    _require("generation_id" not in event_fields, "GenerationId event wiring belongs to FW-RT6-1c")
    _require("terminal" not in event_fields, "terminal event flag belongs to FW-RT6-1c")
    _require(not hasattr(session, "_terminal_registry"), "terminal registry is not authorized in Control C")
    print("[OK] close removes canonical phase and later event/terminal work remains deferred")


def check_docs() -> None:
    required = {
        "docs/v600_lifecycle_contract.md": (
            "FW-RT6-1b-C-REALTIME-PHASE-ADOPTION",
            "RealtimeSession canonical phase: IMPLEMENTED",
            "RealtimeEvent phase field added: False",
        ),
        "docs/public_facade.md": (
            "FW-RT6-1b-C-REALTIME-PHASE-ADOPTION",
            "session.phase",
            "legacy `session.state`",
        ),
        "docs/app_integration_contract.md": (
            "FW-RT6-1b-C-REALTIME-PHASE-ADOPTION",
            "RealtimePhase",
            "TurnOutcome",
        ),
    }
    for relative, phrases in required.items():
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8", errors="replace")
        for phrase in phrases:
            _require(phrase in text, f"{relative} missing phrase: {phrase}")
        _require("faef0cf09dc965ce5069687cd021f00bbfebdc0f" not in text, f"{relative} retained synthetic identity baseline")
        _require("f6a279e57b3f8ff966dfdca107a7dce8cc3b84fe" not in text, f"{relative} retained synthetic lifecycle baseline")
        _require("__CONTROL_" not in text, f"{relative} retained unresolved placeholder")
    print("[OK] Control C docs preserve accepted history and phase/outcome guidance")


def main() -> None:
    check_repository_contract()
    framework = import_framework_safely()
    check_public_phase_types(framework)
    check_session_phase_progression(framework)
    check_transition_and_interrupt_contract(framework)
    check_close_and_deferrals(framework)
    check_docs()

    print("v600_realtime_phase_adoption_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 8")
    print("v600_root_public_name_count: 104")
    print("v600_realtime_session_phase_type: RealtimePhase-or-None")
    print("v600_realtime_session_info_phase_adopted: True")
    print("v600_realtime_turn_phase_adopted: True")
    print("v600_legacy_realtime_state_preserved: True")
    print("v600_invalid_session_transition_typed_failure: True")
    print("v600_closed_session_phase_none: True")
    print("v600_realtime_event_phase_field_added: False")
    print("v600_event_sequence_generation_wired: False")
    print("v600_terminal_registry_implemented: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1b Control D")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1b Control C realtime phase adoption smoke passed")


if __name__ == "__main__":
    main()
