"""FW-RT6-1a Control B realtime identity adoption gate.

Mock-safe: no provider, network, microphone, playback, VTS, or host-app
execution is performed.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "0b435e407a3fec018dce29b7446082948d1d2307"
EXPECTED_SURFACE = {
    "framework/identity.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "framework/output_control.py",
    "scripts/smoke_v600_realtime_identity_adoption.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "docs/v600_public_identity_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
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
        paths.update(line.replace("\\", "/") for line in _git(*args).splitlines() if line.strip())
    return paths


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control B baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control B surface: {sorted(_changed_paths())}")
    print("[OK] Control B baseline and exact ten-file surface match")


def check_import_safety():
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    hits = sorted(name for name in loaded if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS))
    _assert(not hits, f"identity adoption imported forbidden modules: {hits}")
    _assert(len(framework.__all__) == 99, "root-public count changed")
    return framework


def check_identity_adoption(framework) -> None:
    session = framework.create_realtime_session()
    _assert(isinstance(session.info.session_id, framework.SessionId), "new session_id is not SessionId")

    events = []
    session.on_event(events.append)
    result = session.run_turn(input_text="identity")
    _assert(isinstance(result.turn_id, framework.TurnId), "run_turn result ID is not TurnId")
    _assert(all(event.session_id == session.info.session_id for event in events), "session identity drift")
    _assert(all(isinstance(event.session_id, framework.SessionId) for event in events), "event session ID type drift")
    turn_events = [event for event in events if event.turn_id is not None]
    _assert(turn_events, "turn events missing")
    _assert(all(event.turn_id == result.turn_id for event in turn_events), "turn identity drift")
    _assert(all(isinstance(event.turn_id, framework.TurnId) for event in turn_events), "event turn ID type drift")

    turn = framework.RealtimeTurn()
    _assert(isinstance(turn.turn_id, framework.TurnId), "new RealtimeTurn is not TurnId")

    sid_text = str(framework.SessionId.new())
    tid_text = str(framework.TurnId.new())
    event = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
        session_id=sid_text,
        turn_id=tid_text,
    )
    _assert(isinstance(event.session_id, framework.SessionId), "serialized SessionId did not normalize")
    _assert(isinstance(event.turn_id, framework.TurnId), "serialized TurnId did not normalize")
    _assert(event.as_dict()["session_id"] == sid_text, "session JSON scalar drift")
    _assert(event.as_dict()["turn_id"] == tid_text, "turn JSON scalar drift")

    legacy = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
        session_id="session-1",
        turn_id="turn-1",
    )
    _assert(type(legacy.session_id) is str and legacy.session_id == "session-1", "legacy session ID changed")
    _assert(type(legacy.turn_id) is str and legacy.turn_id == "turn-1", "legacy turn ID changed")

    provider_like = framework.InterruptRequest(turn_id="provider-request-123")
    _assert(type(provider_like.turn_id) is str, "provider-like legacy ID was reclassified")

    for factory in (
        lambda: framework.RealtimeTurn(session_id=str(framework.TurnId.new())),
        lambda: framework.InterruptRequest(turn_id=str(framework.SessionId.new())),
        lambda: framework.RealtimeEvent(
            type=framework.RealtimeEventType.TURN_STARTED,
            state=framework.RealtimeState.LISTENING,
            turn_id="fw_turn_invalid",
        ),
    ):
        try:
            factory()
        except ValueError:
            pass
        else:
            raise AssertionError("wrong-kind or malformed fw_* identity was accepted")

    _assert("sequence" not in framework.RealtimeEvent.__dataclass_fields__, "EventSequence wired prematurely")
    _assert("generation_id" not in framework.RealtimeEvent.__dataclass_fields__, "GenerationId wired prematurely")
    print("[OK] Framework-generated realtime identities are typed and stable")
    print("[OK] serialized v6 IDs normalize while legacy host strings remain compatible")
    print("[OK] wrong-kind and malformed reserved identities are rejected")


def check_docs() -> None:
    for relative in (
        "docs/v600_public_identity_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert("FW-RT6-1a-B-REALTIME-IDENTITY-ADOPTION" in text, f"missing Control B marker: {relative}")
        _assert("legacy host session/turn strings: PRESERVED" in text, f"missing legacy policy: {relative}")
        _assert("RealtimeEvent sequence/generation wiring: False" in text, f"premature event claim: {relative}")
    print("[OK] identity adoption documentation records compatibility and deferrals")


def main() -> None:
    check_repository_contract()
    framework = check_import_safety()
    check_identity_adoption(framework)
    check_docs()
    print("v600_realtime_identity_adoption_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 10")
    print("v600_root_public_name_count: 99")
    print("v600_framework_generated_session_id_typed: True")
    print("v600_framework_generated_turn_id_typed: True")
    print("v600_legacy_host_ids_preserved: True")
    print("v600_valid_serialized_ids_normalized: True")
    print("v600_wrong_kind_identity_rejected: True")
    print("v600_provider_identifier_promoted: False")
    print("v600_event_sequence_wired: False")
    print("v600_generation_id_wired: False")
    print("v600_terminal_behavior_changed: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1a Control C")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1a Control B realtime identity adoption smoke passed")


if __name__ == "__main__":
    main()
