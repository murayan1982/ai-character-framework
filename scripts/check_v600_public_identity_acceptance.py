"""Aggregate FW-RT6-1a public identity acceptance checker.

Mock-safe: this checker performs no provider, network, microphone, playback,
VTube Studio, or host-application operation.
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTROL_C_COMMIT = "9d955955d4462006ed8aacc8e4c6e43ae487fb35"
EXPECTED_CONTROL_B_COMMIT = "f740b374a35ed1a448beb6dc17a25427acb547fc"
EXPECTED_CONTROL_A_COMMIT = "0b435e407a3fec018dce29b7446082948d1d2307"
EXPECTED_CONTROL_A_PARENT = "24b0e24e89e1382e0151f4172ae850b25ccd48a1"

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_public_identity_acceptance.py",
}
CONTROL_A_SUBJECT = "feat/test: add public identity primitives"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_identity_contract.md",
    "framework/__init__.py",
    "framework/identity.py",
    "framework/public_api.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_public_identity_types.py",
    "scripts/smoke_v600_version_metadata.py",
}
CONTROL_B_SUBJECT = "feat/test: adopt realtime public identities"
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_identity_contract.md",
    "framework/identity.py",
    "framework/output_control.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_identity_adoption.py",
}
CONTROL_C_SUBJECT = "feat/test: adopt motion session identity"
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_identity_contract.md",
    "framework/motion.py",
    "framework/motion_session.py",
    "scripts/smoke_v520_motion_public_contract_conformance_gate.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "scripts/smoke_v600_motion_identity_adoption.py",
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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    import subprocess

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


def _commit_subject(commit: str) -> str:
    return _git("show", "-s", "--format=%s", commit)


def _commit_parent(commit: str) -> str:
    return _git("rev-parse", f"{commit}^")


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
        if line.strip()
    }


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_CONTROL_C_COMMIT, "unexpected Control D baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control D surface: {sorted(_changed_paths())}")

    _assert(_commit_subject(EXPECTED_CONTROL_C_COMMIT) == CONTROL_C_SUBJECT, "Control C subject drift")
    _assert(_commit_surface(EXPECTED_CONTROL_C_COMMIT) == CONTROL_C_SURFACE, "Control C exact surface drift")
    _assert(_commit_parent(EXPECTED_CONTROL_C_COMMIT) == EXPECTED_CONTROL_B_COMMIT, "Control C parent drift")

    _assert(_commit_subject(EXPECTED_CONTROL_B_COMMIT) == CONTROL_B_SUBJECT, "Control B subject drift")
    _assert(_commit_surface(EXPECTED_CONTROL_B_COMMIT) == CONTROL_B_SURFACE, "Control B exact surface drift")
    _assert(_commit_parent(EXPECTED_CONTROL_B_COMMIT) == EXPECTED_CONTROL_A_COMMIT, "Control B parent drift")

    _assert(_commit_subject(EXPECTED_CONTROL_A_COMMIT) == CONTROL_A_SUBJECT, "Control A subject drift")
    _assert(_commit_surface(EXPECTED_CONTROL_A_COMMIT) == CONTROL_A_SURFACE, "Control A exact surface drift")
    _assert(_commit_parent(EXPECTED_CONTROL_A_COMMIT) == EXPECTED_CONTROL_A_PARENT, "Control A parent drift")

    print("[OK] Control A/B/C history and exact Control D surface conform")


def check_primitive_contract(framework) -> None:
    _assert(len(framework.__all__) == 99, "root-public count drift")
    _assert(
        tuple(framework.__all__[-4:])
        == ("SessionId", "TurnId", "GenerationId", "EventSequence"),
        "identity public suffix drift",
    )

    session_id = framework.SessionId.new()
    turn_id = framework.TurnId.new()
    generation_id = framework.GenerationId.new()
    sequence = framework.EventSequence.first()

    _assert(session_id.startswith("fw_session_"), "SessionId format drift")
    _assert(turn_id.startswith("fw_turn_"), "TurnId format drift")
    _assert(generation_id.startswith("fw_generation_"), "GenerationId format drift")
    _assert(sequence == 1 and sequence.next() == 2, "EventSequence contract drift")
    _assert(framework.SessionId.parse(session_id.to_json_value()) == session_id, "SessionId roundtrip drift")
    _assert(framework.TurnId.parse(turn_id.to_json_value()) == turn_id, "TurnId roundtrip drift")
    _assert(framework.GenerationId.parse(generation_id.to_json_value()) == generation_id, "GenerationId roundtrip drift")
    _assert(framework.EventSequence.parse(sequence.to_json_value()) == sequence, "EventSequence roundtrip drift")
    json.dumps([session_id.to_json_value(), turn_id.to_json_value(), generation_id.to_json_value(), sequence.to_json_value()])

    for factory in (
        lambda: framework.SessionId.parse(str(turn_id)),
        lambda: framework.TurnId.parse(str(session_id)),
        lambda: framework.GenerationId.parse("fw_generation_invalid"),
        lambda: framework.EventSequence.parse(0),
        lambda: framework.EventSequence.parse(True),
    ):
        try:
            factory()
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError("invalid identity value was accepted")

    print("[OK] identity primitive generation, validation, and JSON scalar contracts conform")


def check_realtime_contract(framework) -> None:
    events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)
    created = session.emit_created()
    result = session.run_turn(input_text="identity aggregate")

    _assert(isinstance(session.info.session_id, framework.SessionId), "RealtimeSession ID is not SessionId")
    _assert(created.session_id == session.info.session_id, "Realtime created event session ID drift")
    _assert(isinstance(result.turn_id, framework.TurnId), "Realtime result turn ID is not TurnId")
    _assert(all(event.session_id == session.info.session_id for event in events), "Realtime event session ID drift")
    turn_events = [event for event in events if event.turn_id is not None]
    _assert(turn_events and all(event.turn_id == result.turn_id for event in turn_events), "Realtime event turn ID drift")

    legacy = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
        session_id="session-1",
        turn_id="turn-1",
    )
    _assert(type(legacy.session_id) is str and legacy.session_id == "session-1", "legacy session ID changed")
    _assert(type(legacy.turn_id) is str and legacy.turn_id == "turn-1", "legacy turn ID changed")

    typed = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
        session_id=str(framework.SessionId.new()),
        turn_id=str(framework.TurnId.new()),
    )
    _assert(isinstance(typed.session_id, framework.SessionId), "serialized SessionId did not normalize")
    _assert(isinstance(typed.turn_id, framework.TurnId), "serialized TurnId did not normalize")

    provider_like = framework.InterruptRequest(turn_id="provider-request-123")
    _assert(type(provider_like.turn_id) is str, "provider-like raw ID was promoted")

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
            raise AssertionError("wrong-kind or malformed realtime identity was accepted")

    session.close()
    print("[OK] Realtime SessionId/TurnId adoption and legacy compatibility conform")


def check_motion_contract(framework) -> None:
    events = []
    session = framework.create_motion_session()
    session.on_event(events.append)
    session.emit_created()
    session_id = session.info.session_id
    result = session.apply_motion(framework.MotionRequest.expression_change("smile"))

    _assert(isinstance(session_id, framework.SessionId), "MotionSession ID is not SessionId")
    _assert(result.session_id == session_id, "MotionResult session ID drift")
    _assert(isinstance(result.session_id, framework.SessionId), "MotionResult session ID type drift")
    _assert(events and all(type(event["session_id"]) is str for event in events), "Motion callback ID is not JSON string")
    _assert(all(event["session_id"] == str(session_id) for event in events), "Motion callback identity drift")
    json.dumps([event["session_id"] for event in events])

    legacy = framework.MotionResult.completed(session_id="motion-session")
    _assert(type(legacy.session_id) is str and legacy.session_id == "motion-session", "legacy Motion ID changed")
    typed = framework.MotionResult.completed(session_id=str(framework.SessionId.new()))
    _assert(isinstance(typed.session_id, framework.SessionId), "serialized Motion SessionId did not normalize")

    try:
        framework.MotionResult.completed(session_id=str(framework.TurnId.new()))
    except ValueError:
        pass
    else:
        raise AssertionError("wrong-kind Motion session identity was accepted")

    request = framework.MotionRequest.expression_change("smile")
    _assert(type(request.request_id) is str, "MotionRequest request_id type changed")
    _assert(not request.request_id.startswith("fw_generation_"), "MotionRequest request_id became GenerationId")
    session.close()
    print("[OK] Motion SessionId propagation and callback serialization conform")


def check_truthful_deferrals(framework) -> None:
    realtime_event_fields = {field.name for field in fields(framework.RealtimeEvent)}
    motion_result_fields = {field.name for field in fields(framework.MotionResult)}
    text_result_fields = {field.name for field in fields(framework.TextChatResult)}
    voice_input_fields = {field.name for field in fields(framework.VoiceInputResult)}
    voice_output_fields = {field.name for field in fields(framework.VoiceOutputResult)}

    _assert("sequence" not in realtime_event_fields, "RealtimeEvent.sequence wired before FW-RT6-1c")
    _assert("generation_id" not in realtime_event_fields, "RealtimeEvent.generation_id wired before FW-RT6-1c")
    _assert("terminal" not in realtime_event_fields, "RealtimeEvent terminal flag wired before FW-RT6-1c")
    _assert("turn_id" not in motion_result_fields, "MotionResult.turn_id wired prematurely")
    _assert("generation_id" not in motion_result_fields, "MotionResult.generation_id wired prematurely")

    for name, field_names in (
        ("TextChatResult", text_result_fields),
        ("VoiceInputResult", voice_input_fields),
        ("VoiceOutputResult", voice_output_fields),
    ):
        _assert(
            not {"session_id", "turn_id", "generation_id"}.intersection(field_names),
            f"{name} correlation fields wired prematurely",
        )

    print("[OK] deferred result correlation and ordered event fields remain truthfully absent")


def check_docs() -> None:
    expected = {
        "README.md": "FW-RT6-1a-D-PUBLIC-IDENTITY-ACCEPTANCE",
        "docs/v600_current_source_gap_inventory.md": "FW-RT6-1a-D-GAP-RESOLUTION-SYNC",
        "docs/v600_tasklist.md": "FW-RT6-1a-D-ACCEPTANCE-SYNC",
    }
    for relative, marker in expected.items():
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(marker in text, f"missing Control D marker: {relative}")
        _assert("__CONTROL_" not in text, f"unresolved Control placeholder: {relative}")

    task_text = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for phrase in (
        "- [x] `SessionId`相当のopaque public typeを定義する。",
        "- [x] `TurnId`相当を定義する。",
        "- [x] `GenerationId`相当を定義する。",
        "- [x] `EventSequence`相当を定義する。",
        "all-stage runtime correlation wiring:\nFalse / DEFERRED",
        "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED",
    ):
        _assert(phrase in task_text, f"tasklist acceptance sync missing: {phrase}")

    gap_text = (PROJECT_ROOT / "docs/v600_current_source_gap_inventory.md").read_text(encoding="utf-8")
    for phrase in (
        "G-02 common public identity primitives: RESOLVED",
        "G-02 TextChat result correlation wiring: UNRESOLVED / LATER STAGE INTEGRATION",
        "G-03 RealtimeEvent sequence: UNRESOLVED / FW-RT6-1c",
        "phase/outcome/recovery separation: UNRESOLVED / FW-RT6-1b",
    ):
        _assert(phrase in gap_text, f"gap sync missing: {phrase}")

    print("[OK] README, gap inventory, and tasklist public identity acceptance are synchronized")


def main() -> None:
    check_repository_contract()

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    hits = sorted(
        name
        for name in loaded
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not hits, f"aggregate identity import loaded forbidden modules: {hits}")

    check_primitive_contract(framework)
    check_realtime_contract(framework)
    check_motion_contract(framework)
    check_truthful_deferrals(framework)
    check_docs()

    print("v600_public_identity_acceptance_status: implemented-awaiting-review")
    print("v600_control_a_accepted: True")
    print("v600_control_b_accepted: True")
    print("v600_control_c_accepted: True")
    print("v600_exact_change_surface_count: 4")
    print("v600_legacy_root_public_prefix_count: 95")
    print("v600_root_public_name_count: 99")
    print("v600_framework_generated_realtime_identity_typed: True")
    print("v600_framework_generated_motion_identity_typed: True")
    print("v600_provider_identifier_promoted: False")
    print("v600_all_stage_result_correlation_wired: False")
    print("v600_event_sequence_generation_wired: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_microphone_used: False")
    print("v600_audio_playback: False")
    print("v600_vts_execution: False")
    print("v600_drc_repository_accessed: False")
    print("v600_next_checkpoint: FW-RT6-1b")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-1a Control D public identity acceptance checker passed")


if __name__ == "__main__":
    main()
