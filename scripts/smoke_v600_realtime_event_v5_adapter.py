"""FW-RT6-1c Control C explicit RealtimeEvent v5 adapter smoke.

Offline-safe: validates the immutable mapping, identity projections, lossy drops,
field preservation, legacy serialization, and truthful runtime deferrals.
"""

from __future__ import annotations

import dataclasses
import importlib
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "532d7852bfe9370514180800a84bfc0a8e13fa9c"
EXPECTED_CONTROL_B_PARENT = "a29b90cadcb6b7917499c30cbe753d2c72ea353b"
EXPECTED_CONTROL_B_SUBJECT = "feat/test: add realtime event v6 envelope"
EXPECTED_CONTROL_C_SUBJECT = "feat/test: add realtime event v5 adapter"
EXPECTED_CONTROL_B_SURFACE = {
    "framework/realtime.py",
    "scripts/smoke_v600_realtime_event_envelope.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "docs/v600_realtime_event_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
EXPECTED_SURFACE = {
    "framework/realtime.py",
    "scripts/smoke_v600_realtime_event_v5_adapter.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "docs/v600_realtime_event_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
IDENTITY_NAMES = (
    "SESSION_CREATED", "TURN_STARTED", "VOICE_INPUT_STARTED",
    "VOICE_INPUT_COMPLETED", "TEXT_CHAT_STARTED", "TEXT_CHAT_COMPLETED",
    "VOICE_OUTPUT_STARTED", "VOICE_OUTPUT_COMPLETED", "MOTION_STARTED",
    "MOTION_COMPLETED", "TURN_COMPLETED", "TURN_INTERRUPTED",
    "TURN_FAILED", "SESSION_CLOSED", "INTERRUPT_REQUESTED",
    "INTERRUPT_ACCEPTED", "INTERRUPT_COMPLETED", "INTERRUPT_UNSUPPORTED",
    "OUTPUT_FLUSH_REQUESTED", "OUTPUT_FLUSH_COMPLETED",
    "OUTPUT_FLUSH_UNSUPPORTED", "BARGE_IN_DETECTED", "BARGE_IN_ACCEPTED",
    "BARGE_IN_REJECTED",
)
MAPPING_NAMES = {
    "SESSION_STARTED": "SESSION_CREATED",
    "LISTENING_STARTED": "VOICE_INPUT_STARTED",
    "TRANSCRIPT_FINAL": "VOICE_INPUT_COMPLETED",
    "RESPONSE_STARTED": "TEXT_CHAT_STARTED",
    "RESPONSE_COMPLETED": "TEXT_CHAT_COMPLETED",
    "SYNTHESIS_STARTED": "VOICE_OUTPUT_STARTED",
    "SYNTHESIS_COMPLETED": "VOICE_OUTPUT_COMPLETED",
    "TURN_CANCELLED": "TURN_INTERRUPTED",
    "TURN_REJECTED": "TURN_FAILED",
}
UNMAPPED_NAMES = (
    "LISTENING_COMPLETED", "SPEECH_STARTED", "SPEECH_ENDED",
    "TRANSCRIPT_PARTIAL", "RESPONSE_DELTA", "AUDIO_AVAILABLE",
    "AUDIO_INVALIDATED", "MOTION_REQUESTED", "MOTION_FAILED",
    "STALE_RESULT_DROPPED", "EVENT_OVERFLOW",
)
LEGACY_KEYS = (
    "type", "state", "previous_state", "turn_id", "session_id",
    "boundary", "public_error_code", "safe_message", "retryable",
    "public_metadata",
)
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
            for line in _git(*args).splitlines() if line.strip()
        )
    return paths


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit,
        ).splitlines() if line.strip()
    }


def _is_ancestor(ancestor: str, descendant: str = "HEAD") -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _control_c_commit() -> str | None:
    head = _git("rev-parse", "HEAD")
    if head == EXPECTED_BASELINE_HEAD:
        return None
    _assert(
        _is_ancestor(EXPECTED_BASELINE_HEAD, head),
        "Control B baseline is not an ancestor of HEAD",
    )
    commits = [
        line.strip()
        for line in _git(
            "rev-list",
            "--reverse",
            "--ancestry-path",
            f"{EXPECTED_BASELINE_HEAD}..{head}",
        ).splitlines()
        if line.strip()
    ]
    _assert(commits, "Control C descendant commit is missing")
    return commits[0]


def check_repository_contract() -> None:
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE_HEAD}^") == EXPECTED_CONTROL_B_PARENT,
        "Control B parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE_HEAD)
        == EXPECTED_CONTROL_B_SUBJECT,
        "Control B subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE_HEAD) == EXPECTED_CONTROL_B_SURFACE,
        "Control B exact surface drift",
    )

    control_c_commit = _control_c_commit()
    if control_c_commit is None:
        _assert(
            _changed_paths() == EXPECTED_SURFACE,
            f"unexpected Control C surface: {sorted(_changed_paths())}",
        )
        mode = "candidate"
    else:
        _assert(
            _git("rev-parse", f"{control_c_commit}^") == EXPECTED_BASELINE_HEAD,
            "Control C parent drift",
        )
        _assert(
            _git("show", "-s", "--format=%s", control_c_commit)
            == EXPECTED_CONTROL_C_SUBJECT,
            "Control C subject drift",
        )
        _assert(
            _commit_surface(control_c_commit) == EXPECTED_SURFACE,
            "Control C exact surface drift",
        )
        mode = "committed-descendant"

    print(
        "[OK] committed Control B history and Control C "
        f"{mode} contract match"
    )


def check_mapping_tables(framework, realtime_module) -> None:
    from framework.public_api import PUBLIC_API_NAMES

    _assert(len(PUBLIC_API_NAMES) == 114, "root-public count drift")
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    identity = realtime_module._V5_REALTIME_EVENT_TYPES
    mapping = realtime_module._V6_TO_V5_REALTIME_EVENT_TYPE
    _assert(isinstance(identity, frozenset), "v5 identity set must be immutable")
    _assert(isinstance(mapping, MappingProxyType), "v6-to-v5 mapping must be immutable")
    expected_identity = frozenset(getattr(framework.RealtimeEventType, name) for name in IDENTITY_NAMES)
    expected_mapping = {
        getattr(framework.RealtimeEventType, source): getattr(framework.RealtimeEventType, target)
        for source, target in MAPPING_NAMES.items()
    }
    _assert(identity == expected_identity, "v5 identity set drift")
    _assert(dict(mapping) == expected_mapping, "v6-to-v5 mapping table drift")
    print("[OK] immutable identity set and explicit v6-to-v5 mapping conform")


def _event(framework, event_type, *, error_code="none", payload=None):
    terminal = event_type in {
        framework.RealtimeEventType.TURN_COMPLETED,
        framework.RealtimeEventType.TURN_INTERRUPTED,
        framework.RealtimeEventType.TURN_CANCELLED,
        framework.RealtimeEventType.TURN_FAILED,
        framework.RealtimeEventType.TURN_REJECTED,
        framework.RealtimeEventType.SESSION_CLOSED,
    }
    return framework.RealtimeEvent(
        type=event_type,
        state=framework.RealtimeState.COMPLETED if terminal else framework.RealtimeState.LISTENING,
        previous_state=framework.RealtimeState.IDLE,
        session_id=framework.SessionId.new(),
        turn_id=framework.TurnId.new(),
        generation_id=framework.GenerationId.new(),
        sequence=3,
        phase=framework.RealtimePhase.LISTENING,
        payload=payload,
        terminal=terminal,
        timestamp=12.5,
        monotonic_timestamp=4.0,
        public_error_code=error_code,
        safe_message="safe",
        retryable=False,
        public_metadata={"visible": "ok"},
    )


def check_identity_and_explicit_mappings(framework) -> None:
    for name in IDENTITY_NAMES:
        event_type = getattr(framework.RealtimeEventType, name)
        event = _event(framework, event_type)
        _assert(event.to_v5() is event, f"identity projection drift: {name}")
        _assert(event.as_v5_dict() == event.as_dict(), f"identity serialization drift: {name}")

    for source_name, target_name in MAPPING_NAMES.items():
        source = getattr(framework.RealtimeEventType, source_name)
        target = getattr(framework.RealtimeEventType, target_name)
        error = "cancelled" if source_name == "TURN_CANCELLED" else ("rejected" if source_name == "TURN_REJECTED" else "none")
        payload = (
            framework.LifecycleEventPayload(
                outcome="cancelled" if source_name == "TURN_CANCELLED" else "rejected",
            )
            if source_name in {"TURN_CANCELLED", "TURN_REJECTED"}
            else None
        )
        event = _event(framework, source, error_code=error, payload=payload)
        mapped = event.to_v5()
        _assert(mapped is not None and mapped is not event, f"mapped event allocation drift: {source_name}")
        _assert(mapped.type is target, f"mapped event type drift: {source_name}")
        for field in dataclasses.fields(framework.RealtimeEvent):
            if field.name != "type":
                _assert(getattr(mapped, field.name) == getattr(event, field.name), f"mapped field drift: {source_name}.{field.name}")
        legacy = event.as_v5_dict()
        _assert(legacy is not None and tuple(legacy.keys()) == LEGACY_KEYS, f"legacy key drift: {source_name}")
        _assert(legacy["type"] == target.value, f"legacy mapped type drift: {source_name}")
        _assert(legacy["public_error_code"] == error, f"public error code drift: {source_name}")
    print("[OK] identity and explicit v6-to-v5 projections preserve compatible fields")


def check_unmapped_and_order(framework) -> None:
    for name in UNMAPPED_NAMES:
        event = _event(framework, getattr(framework.RealtimeEventType, name))
        _assert(event.to_v5() is None, f"unmapped event projected: {name}")
        _assert(event.as_v5_dict() is None, f"unmapped dictionary projected: {name}")

    canonical = (
        "TURN_STARTED", "LISTENING_STARTED", "LISTENING_COMPLETED",
        "TRANSCRIPT_FINAL", "RESPONSE_STARTED", "RESPONSE_COMPLETED",
        "SYNTHESIS_STARTED", "SYNTHESIS_COMPLETED", "TURN_COMPLETED",
    )
    projected = []
    for name in canonical:
        mapped = _event(framework, getattr(framework.RealtimeEventType, name)).to_v5()
        if mapped is not None:
            projected.append(mapped.type.name)
    _assert(
        tuple(projected) == (
            "TURN_STARTED", "VOICE_INPUT_STARTED", "VOICE_INPUT_COMPLETED",
            "TEXT_CHAT_STARTED", "TEXT_CHAT_COMPLETED",
            "VOICE_OUTPUT_STARTED", "VOICE_OUTPUT_COMPLETED", "TURN_COMPLETED",
        ),
        "canonical-to-v5 order drift",
    )
    print("[OK] unmapped partial/delta events stay dropped and projected order is stable")


def check_serialization_and_deferrals(framework) -> None:
    event = _event(framework, framework.RealtimeEventType.RESPONSE_COMPLETED)
    before_legacy = event.as_dict()
    before_v6 = event.as_v6_dict()
    mapped = event.to_v5()
    _assert(mapped is not None, "response completed mapping missing")
    _assert(tuple(before_legacy.keys()) == LEGACY_KEYS, "legacy as_dict key order drift")
    _assert(event.as_dict() == before_legacy, "legacy as_dict mutation drift")
    _assert(event.as_v6_dict() == before_v6, "as_v6_dict mutation drift")

    session_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    _assert("on_legacy_event" not in session_source, "legacy callback adopted prematurely")
    _assert("EventSequence.first" not in session_source, "sequence allocation adopted prematurely")
    _assert("GenerationId.new" not in session_source, "generation ownership adopted prematurely")
    _assert("terminal_registry" not in session_source, "terminal registry adopted prematurely")
    for relative_path in (
        "docs/v600_realtime_event_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        _assert("FW-RT6-1c-C-V5-EVENT-ADAPTER" in text, f"Control C marker missing: {relative_path}")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider SDK imported by v5 adapter")
    print("[OK] existing serialization remains stable and session/runtime work stays deferred")


def main() -> None:
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    realtime_module = importlib.import_module("framework.realtime")
    check_repository_contract()
    check_mapping_tables(framework, realtime_module)
    check_identity_and_explicit_mappings(framework)
    check_unmapped_and_order(framework)
    check_serialization_and_deferrals(framework)
    _assert(not (FORBIDDEN_IMPORTS & (set(sys.modules) - before)), "provider module imported during smoke")
    print("v600_realtime_event_v5_adapter_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 7")
    print("v600_root_public_name_count: 114")
    print("v600_v5_identity_projection_supported: True")
    print("v600_explicit_v6_to_v5_mapping_count: 9")
    print("v600_unmapped_v6_event_count: 11")
    print("v600_legacy_dictionary_key_count: 10")
    print("v600_realtime_session_emission_changed: False")
    print("v600_on_legacy_event_callback_adopted: False")
    print("v600_sequence_generation_runtime_wiring: False")
    print("v600_terminal_registry_implemented: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1c Control D")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1c Control C realtime event v5 adapter smoke passed")


if __name__ == "__main__":
    main()
