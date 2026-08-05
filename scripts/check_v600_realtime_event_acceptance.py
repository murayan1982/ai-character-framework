"""Aggregate FW-RT6-1c ordered realtime event acceptance checker.

Mock-safe: this checker performs no provider, network, microphone, playback,
VTube Studio, or host-application operation.
"""

from __future__ import annotations

import importlib
import math
import sys
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTROL_D_COMMIT = "80e5c550bbb994bc8dfc3340340691c881f0449d"
EXPECTED_CONTROL_C_COMMIT = "007e1577a18c92a1dafdf9ede814b97dc2d0a05c"
EXPECTED_CONTROL_B_COMMIT = "532d7852bfe9370514180800a84bfc0a8e13fa9c"
EXPECTED_ENCODING_REPAIR_COMMIT = "a29b90cadcb6b7917499c30cbe753d2c72ea353b"
EXPECTED_ENCODING_CORRUPT_COMMIT = "be7a3731901f165982dbdc03307f7cefcd270638"
EXPECTED_CONTROL_A_COMMIT = "cd80c840fb8dcc23ee4e942de18a7cf693bdab51"
EXPECTED_CONTROL_A_PARENT = "285e546d7065eee24d144a4fc39da82d3097bd1f"

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_event_acceptance.py",
}
CONTROL_A_SUBJECT = "feat/test: add typed realtime event payloads"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_contract.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime_event_payloads.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_event_payload_models.py",
    "scripts/smoke_v600_version_metadata.py",
}
ENCODING_CORRUPT_SUBJECT = "docs: restore lifecycle baseline history"
ENCODING_CORRUPT_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
}
ENCODING_REPAIR_SUBJECT = "docs: repair lifecycle history encoding"
ENCODING_REPAIR_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
}
CONTROL_B_SUBJECT = "feat/test: add realtime event v6 envelope"
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_contract.md",
    "framework/realtime.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_event_envelope.py",
}
CONTROL_C_SUBJECT = "feat/test: add realtime event v5 adapter"
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_contract.md",
    "framework/realtime.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_event_v5_adapter.py",
}
CONTROL_D_SUBJECT = "refactor/test: adopt ordered realtime events"
CONTROL_D_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_contract.md",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_event_ordering_adoption.py",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    "openai", "elevenlabs", "pyvts", "websocket", "pyaudio",
    "sounddevice", "speech_recognition", "google.genai", "xai_sdk",
)
LEGACY_KEYS = (
    "type", "state", "previous_state", "turn_id", "session_id",
    "boundary", "public_error_code", "safe_message", "retryable",
    "public_metadata",
)
V6_KEYS = (
    "type", "state", "previous_state", "session_id", "turn_id",
    "generation_id", "sequence", "phase", "payload", "terminal",
    "timestamp", "monotonic_timestamp", "boundary", "public_error_code",
    "safe_message", "retryable", "public_metadata",
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
    _assert(_git("rev-parse", "HEAD") == EXPECTED_CONTROL_D_COMMIT, "unexpected Control E baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control E surface: {sorted(_changed_paths())}")
    _assert_commit(EXPECTED_CONTROL_A_COMMIT, EXPECTED_CONTROL_A_PARENT, CONTROL_A_SUBJECT, CONTROL_A_SURFACE)
    _assert_commit(EXPECTED_ENCODING_CORRUPT_COMMIT, EXPECTED_CONTROL_A_COMMIT, ENCODING_CORRUPT_SUBJECT, ENCODING_CORRUPT_SURFACE)
    _assert_commit(EXPECTED_ENCODING_REPAIR_COMMIT, EXPECTED_ENCODING_CORRUPT_COMMIT, ENCODING_REPAIR_SUBJECT, ENCODING_REPAIR_SURFACE)
    _assert_commit(EXPECTED_CONTROL_B_COMMIT, EXPECTED_ENCODING_REPAIR_COMMIT, CONTROL_B_SUBJECT, CONTROL_B_SURFACE)
    _assert_commit(EXPECTED_CONTROL_C_COMMIT, EXPECTED_CONTROL_B_COMMIT, CONTROL_C_SUBJECT, CONTROL_C_SURFACE)
    _assert_commit(EXPECTED_CONTROL_D_COMMIT, EXPECTED_CONTROL_C_COMMIT, CONTROL_D_SUBJECT, CONTROL_D_SURFACE)
    print("[OK] Control A/encoding repair/B/C/D history and exact Control E surface conform")


def check_public_manifest(framework) -> None:
    from framework.public_api import (
        PUBLIC_API_GROUPS, PUBLIC_API_NAMES, REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS,
    )
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 114, "root-public count drift")
    _assert(len(PUBLIC_API_NAMES) == len(set(PUBLIC_API_NAMES)), "duplicate root-public name")
    flattened = tuple(name for group in PUBLIC_API_GROUPS.values() for name in group)
    _assert(flattened == PUBLIC_API_NAMES, "public groups do not flatten canonically")
    _assert(len(REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS) == 10, "payload export count drift")
    _assert(PUBLIC_API_NAMES[-10:] == tuple(REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS), "payload models not appended")
    print("[OK] canonical 114-name public manifest preserves the 104-name prefix")


def check_payload_and_envelope_contract(framework) -> None:
    payload_types = (
        framework.LifecycleEventPayload,
        framework.TranscriptEventPayload,
        framework.ResponseEventPayload,
        framework.SynthesisEventPayload,
        framework.AudioEventPayload,
        framework.MotionEventPayload,
        framework.InterruptEventPayload,
        framework.DiagnosticEventPayload,
    )
    _assert(len(payload_types) == 8, "typed payload family count drift")
    _assert(set(framework.RealtimeEventPayload.__args__) == set(payload_types), "payload union drift")
    field_names = tuple(field.name for field in fields(framework.RealtimeEvent))
    _assert(field_names == (
        "type", "state", "previous_state", "turn_id", "session_id",
        "boundary", "public_error_code", "safe_message", "retryable",
        "public_metadata", "sequence", "generation_id", "phase", "payload",
        "terminal", "timestamp", "monotonic_timestamp",
    ), "RealtimeEvent field order drift")
    event = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TRANSCRIPT_FINAL,
        state=framework.RealtimeState.TRANSCRIBING,
        sequence=1,
        generation_id=framework.GenerationId.new(),
        phase=framework.RealtimePhase.TRANSCRIBING,
        payload=framework.TranscriptEventPayload(text="safe", is_final=True),
        timestamp=1.0,
        monotonic_timestamp=2.0,
    )
    _assert(tuple(event.as_dict()) == LEGACY_KEYS, "legacy dictionary keys drift")
    _assert(tuple(event.as_v6_dict()) == V6_KEYS, "v6 dictionary keys drift")
    _assert(event.terminal is False, "non-terminal event inferred terminal")
    terminal = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_COMPLETED,
        state=framework.RealtimeState.COMPLETED,
    )
    _assert(terminal.terminal is True, "terminal event not identifiable")
    for value in (event.timestamp, event.monotonic_timestamp):
        _assert(value is not None and math.isfinite(value) and value >= 0.0, "invalid public timestamp")
    print("[OK] typed payload union, v6 envelope, terminal flag, and serializers conform")


def check_v5_projection_contract(framework) -> None:
    mappings = {
        framework.RealtimeEventType.SESSION_STARTED: framework.RealtimeEventType.SESSION_CREATED,
        framework.RealtimeEventType.LISTENING_STARTED: framework.RealtimeEventType.VOICE_INPUT_STARTED,
        framework.RealtimeEventType.TRANSCRIPT_FINAL: framework.RealtimeEventType.VOICE_INPUT_COMPLETED,
        framework.RealtimeEventType.RESPONSE_STARTED: framework.RealtimeEventType.TEXT_CHAT_STARTED,
        framework.RealtimeEventType.RESPONSE_COMPLETED: framework.RealtimeEventType.TEXT_CHAT_COMPLETED,
        framework.RealtimeEventType.SYNTHESIS_STARTED: framework.RealtimeEventType.VOICE_OUTPUT_STARTED,
        framework.RealtimeEventType.SYNTHESIS_COMPLETED: framework.RealtimeEventType.VOICE_OUTPUT_COMPLETED,
        framework.RealtimeEventType.TURN_CANCELLED: framework.RealtimeEventType.TURN_INTERRUPTED,
        framework.RealtimeEventType.TURN_REJECTED: framework.RealtimeEventType.TURN_FAILED,
    }
    unmapped = {
        framework.RealtimeEventType.LISTENING_COMPLETED,
        framework.RealtimeEventType.SPEECH_STARTED,
        framework.RealtimeEventType.SPEECH_ENDED,
        framework.RealtimeEventType.TRANSCRIPT_PARTIAL,
        framework.RealtimeEventType.RESPONSE_DELTA,
        framework.RealtimeEventType.AUDIO_AVAILABLE,
        framework.RealtimeEventType.AUDIO_INVALIDATED,
        framework.RealtimeEventType.MOTION_REQUESTED,
        framework.RealtimeEventType.MOTION_FAILED,
        framework.RealtimeEventType.STALE_RESULT_DROPPED,
        framework.RealtimeEventType.EVENT_OVERFLOW,
    }
    identity = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
    )
    _assert(identity.to_v5() is identity, "v5 identity projection drift")
    for source_type, target_type in mappings.items():
        event = framework.RealtimeEvent(type=source_type, state=framework.RealtimeState.IDLE)
        mapped = event.to_v5()
        _assert(mapped is not None and mapped.type is target_type, f"mapping drift: {source_type.value}")
    for event_type in unmapped:
        event = framework.RealtimeEvent(type=event_type, state=framework.RealtimeState.IDLE)
        _assert(event.to_v5() is None, f"unmapped event promoted: {event_type.value}")
    _assert(len(mappings) == 9 and len(unmapped) == 11, "v5 adapter cardinality drift")
    print("[OK] explicit v5 identity, mapping, and intentional-drop contract conforms")


def check_ordered_session_contract(framework) -> None:
    canonical = []
    legacy = []
    session = framework.create_realtime_session()
    session.on_event(canonical.append)
    session.on_legacy_event(legacy.append)
    session.emit_created()
    first = session.run_turn(input_text="first")
    first_boundary = len(canonical)
    second = session.run_turn(input_text="second")
    _assert(first.outcome is framework.TurnOutcome.COMPLETED, "first turn outcome drift")
    _assert(second.outcome is framework.TurnOutcome.COMPLETED, "second turn outcome drift")
    expected_turn = (
        framework.RealtimeEventType.TURN_STARTED,
        framework.RealtimeEventType.LISTENING_STARTED,
        framework.RealtimeEventType.LISTENING_COMPLETED,
        framework.RealtimeEventType.TRANSCRIPT_FINAL,
        framework.RealtimeEventType.RESPONSE_STARTED,
        framework.RealtimeEventType.RESPONSE_COMPLETED,
        framework.RealtimeEventType.SYNTHESIS_STARTED,
        framework.RealtimeEventType.SYNTHESIS_COMPLETED,
        framework.RealtimeEventType.TURN_COMPLETED,
    )
    expected_legacy_turn = (
        framework.RealtimeEventType.TURN_STARTED,
        framework.RealtimeEventType.VOICE_INPUT_STARTED,
        framework.RealtimeEventType.VOICE_INPUT_COMPLETED,
        framework.RealtimeEventType.TEXT_CHAT_STARTED,
        framework.RealtimeEventType.TEXT_CHAT_COMPLETED,
        framework.RealtimeEventType.VOICE_OUTPUT_STARTED,
        framework.RealtimeEventType.VOICE_OUTPUT_COMPLETED,
        framework.RealtimeEventType.TURN_COMPLETED,
    )
    _assert(tuple(event.type for event in canonical[1:10]) == expected_turn, "first canonical turn order drift")
    _assert(tuple(event.type for event in canonical[10:19]) == expected_turn, "second canonical turn order drift")
    _assert(tuple(event.type for event in legacy[1:9]) == expected_legacy_turn, "first legacy turn order drift")
    _assert(tuple(event.type for event in legacy[9:17]) == expected_legacy_turn, "second legacy turn order drift")
    sequences = [int(event.sequence) for event in canonical]
    _assert(sequences == list(range(1, len(canonical) + 1)), "session-lifetime sequence drift")
    _assert(int(canonical[first_boundary].sequence) == first_boundary + 1, "sequence reset between turns")
    _assert(canonical[0].generation_id is None, "session event gained generation")
    first_generation = canonical[1].generation_id
    second_generation = canonical[10].generation_id
    _assert(first_generation is not None and second_generation is not None, "admitted turn generation missing")
    _assert(first_generation != second_generation, "generation did not change between turns")
    _assert(all(event.generation_id == first_generation for event in canonical[1:10]), "first generation unstable")
    _assert(all(event.generation_id == second_generation for event in canonical[10:19]), "second generation unstable")
    _assert(all(event.timestamp is not None for event in canonical), "automatic timestamp missing")
    _assert(all(event.monotonic_timestamp is not None for event in canonical), "automatic monotonic timestamp missing")
    _assert(all(
        canonical[index].monotonic_timestamp <= canonical[index + 1].monotonic_timestamp
        for index in range(len(canonical) - 1)
    ), "monotonic timestamp regressed")
    payload_types = (
        framework.LifecycleEventPayload,
        framework.LifecycleEventPayload,
        framework.LifecycleEventPayload,
        framework.TranscriptEventPayload,
        framework.ResponseEventPayload,
        framework.ResponseEventPayload,
        framework.SynthesisEventPayload,
        framework.SynthesisEventPayload,
        framework.LifecycleEventPayload,
    )
    _assert(tuple(type(event.payload) for event in canonical[1:10]) == payload_types, "canonical typed payload progression drift")
    session.close()
    rejected = session.run_turn(input_text="closed")
    _assert(rejected.outcome is framework.TurnOutcome.CLOSED, "closed turn result drift")
    _assert(canonical[-1].type is framework.RealtimeEventType.TURN_REJECTED, "closed turn rejection event drift")
    _assert(canonical[-1].generation_id is None, "rejected-before-admission event gained generation")
    print("[OK] canonical/legacy ordering, session sequence, generation, payload, and timestamps conform")


def check_truthful_deferrals() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for fragment in (
        "_terminal_registry", "terminal_registry =", "atomic_terminal_commit",
        "duplicate_terminal_suppression", "exactly_once_terminal",
        "bounded_event_queue", "event_queue_capacity", "stale_generation_gate",
    ):
        _assert(fragment not in lowered, f"deferred runtime overreach: {fragment}")
    for event_name in (
        "TRANSCRIPT_PARTIAL", "RESPONSE_DELTA", "STALE_RESULT_DROPPED",
        "EVENT_OVERFLOW", "AUDIO_AVAILABLE", "AUDIO_INVALIDATED",
    ):
        _assert(f"RealtimeEventType.{event_name}" not in source, f"deferred provider/runtime event wiring appeared: {event_name}")
    _assert("real_runtime_enabled" in source, "truthful runtime guard disappeared")
    print("[OK] terminal registry, stale rejection, queue, and provider partial/delta work remain deferred")


def check_docs() -> None:
    required = {
        "README.md": (
            "FW-RT6-1c-E-REALTIME-EVENT-ACCEPTANCE",
            "canonical completed-turn events: 9",
            "next checkpoint: FW-RT6-1d",
        ),
        "docs/v600_tasklist.md": (
            "FW-RT6-1c-E-ACCEPTANCE-SYNC",
            "- [x] `RealtimeEvent`へsequenceを追加する。",
            "terminal registry / exactly-once enforcement:\nFalse / DEFERRED",
        ),
        "docs/v600_current_source_gap_inventory.md": (
            "FW-RT6-1c-E-GAP-RESOLUTION-SYNC",
            "G-03 canonical RealtimeEvent v6 envelope: RESOLVED",
            "G-04 per-session terminal registry: UNRESOLVED",
            "G-06 capability truthfulness: UNRESOLVED / FW-RT6-1d",
        ),
    }
    for relative, fragments in required.items():
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for fragment in fragments:
            _assert(fragment in text, f"missing realtime acceptance doc fragment: {relative}: {fragment}")
        _assert("__CONTROL_" not in text, f"unresolved placeholder: {relative}")
    print("[OK] README, tasklist, and gap inventory record truthful event acceptance")


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
    check_payload_and_envelope_contract(framework)
    check_v5_projection_contract(framework)
    check_ordered_session_contract(framework)
    check_truthful_deferrals()
    print("[OK] aggregate realtime event import stayed provider/network/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_docs()
    print("v600_realtime_event_acceptance_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 4")
    print("v600_root_public_name_count: 114")
    print("v600_legacy_root_public_prefix: 104 / unchanged")
    print("v600_canonical_completed_turn_events: 9")
    print("v600_legacy_completed_turn_events: 8")
    print("v600_event_sequence_session_lifetime: True")
    print("v600_event_sequence_resets_between_turns: False")
    print("v600_generation_per_admitted_turn: True")
    print("v600_session_or_rejected_generation: None")
    print("v600_typed_payload_adopted: True")
    print("v600_automatic_public_timestamps: True")
    print("v600_terminal_registry_implemented: False")
    print("v600_stale_result_rejection_automatic: False")
    print("v600_bounded_event_queue_runtime: False")
    print("v600_provider_partial_or_delta_callbacks: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_checkpoint: FW-RT6-1d")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-1c ordered realtime event foundation aggregate acceptance passed")


if __name__ == "__main__":
    main()
