"""FW-RT6-1c Control B RealtimeEvent v6 envelope smoke.

Offline-safe: validates the exact additive event-envelope surface, v5 prefix
compatibility, identity/phase/payload/timestamp normalization, terminal meaning,
and truthful runtime deferrals without provider or network execution.
"""

from __future__ import annotations

import dataclasses
import importlib
import math
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "a29b90cadcb6b7917499c30cbe753d2c72ea353b"
EXPECTED_CONTROL_A_COMMIT = "cd80c840fb8dcc23ee4e942de18a7cf693bdab51"
EXPECTED_CONTROL_D_COMMIT = "285e546d7065eee24d144a4fc39da82d3097bd1f"
EXPECTED_CONTROL_A_SUBJECT = "feat/test: add typed realtime event payloads"
EXPECTED_CONTROL_B_SUBJECT = "feat/test: add realtime event v6 envelope"
EXPECTED_REPAIR_SUBJECT = "docs: repair lifecycle history encoding"
EXPECTED_CORRUPT_CORRECTIVE_COMMIT = "be7a3731901f165982dbdc03307f7cefcd270638"
EXPECTED_CORRUPT_CORRECTIVE_SUBJECT = "docs: restore lifecycle baseline history"
EXPECTED_CORRECTIVE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
}
EXPECTED_CONTROL_A_SURFACE = {
    "framework/realtime_event_payloads.py",
    "framework/public_api.py",
    "framework/__init__.py",
    "scripts/smoke_v600_realtime_event_payload_models.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
    "scripts/smoke_app_sdk.py",
    "docs/v600_realtime_event_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
EXPECTED_SURFACE = {
    "framework/realtime.py",
    "scripts/smoke_v600_realtime_event_envelope.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "docs/v600_realtime_event_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
LEGACY_EVENT_VALUES = (
    "realtime.session.created",
    "realtime.turn.started",
    "realtime.voice_input.started",
    "realtime.voice_input.completed",
    "realtime.text_chat.started",
    "realtime.text_chat.completed",
    "realtime.voice_output.started",
    "realtime.voice_output.completed",
    "realtime.motion.started",
    "realtime.motion.completed",
    "realtime.turn.completed",
    "realtime.turn.interrupted",
    "realtime.turn.failed",
    "realtime.session.closed",
    "realtime.interrupt.requested",
    "realtime.interrupt.accepted",
    "realtime.interrupt.completed",
    "realtime.interrupt.unsupported",
    "realtime.output.flush.requested",
    "realtime.output.flush.completed",
    "realtime.output.flush.unsupported",
    "realtime.barge_in.detected",
    "realtime.barge_in.accepted",
    "realtime.barge_in.rejected",
)
V6_EVENT_VALUES = (
    "realtime.session.started",
    "realtime.turn.cancelled",
    "realtime.turn.rejected",
    "realtime.listening.started",
    "realtime.listening.completed",
    "realtime.speech.started",
    "realtime.speech.ended",
    "realtime.transcript.partial",
    "realtime.transcript.final",
    "realtime.response.started",
    "realtime.response.delta",
    "realtime.response.completed",
    "realtime.synthesis.started",
    "realtime.synthesis.completed",
    "realtime.audio.available",
    "realtime.audio.invalidated",
    "realtime.motion.requested",
    "realtime.motion.failed",
    "realtime.stale_result.dropped",
    "realtime.event.overflow",
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


def _expect_failure(callable_, expected: type[BaseException]) -> None:
    try:
        callable_()
    except expected:
        return
    raise AssertionError(f"expected {expected.__name__}")


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
        if line.strip()
    }


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def _expected_repaired_bytes(relative_path: str) -> bytes:
    source = _git_bytes("show", f"{EXPECTED_CONTROL_A_COMMIT}:{relative_path}")
    synthetic = b"3048984092bba58baf6c3841b53d58ec4c02b7fc"
    accepted = b"6443e524d8bc4e32eb4d7e7ecba75e26244c9f10"
    _assert(
        source.count(synthetic) == 1,
        f"unexpected synthetic baseline count in Control A source: {relative_path}",
    )
    return source.replace(synthetic, accepted)


def _assert_repair_and_candidate_bytes(relative_path: str) -> None:
    expected_base = _expected_repaired_bytes(relative_path)
    committed = _git_bytes("show", f"{EXPECTED_BASELINE_HEAD}:{relative_path}")
    _assert(
        committed == expected_base,
        f"encoding repair bytes drift: {relative_path}",
    )
    current = (PROJECT_ROOT / relative_path).read_bytes()
    marker = b"<!-- FW-RT6-1c-B-REALTIME-EVENT-ENVELOPE:BEGIN -->"
    _assert(marker in current, f"Control B marker missing: {relative_path}")
    prefix, _ = current.split(marker, 1)
    _assert(
        prefix == expected_base.rstrip(b"\r\n") + b"\n\n",
        f"Control B document base drift: {relative_path}",
    )


def _control_b_commit() -> str | None:
    value = _git(
        "log", "-1", "--format=%H", "--",
        "scripts/smoke_v600_realtime_event_envelope.py",
    )
    return value or None


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=PROJECT_ROOT, check=False, capture_output=True, text=True,
    ).returncode == 0


def check_repository_contract() -> None:
    head = _git("rev-parse", "HEAD")
    if head == EXPECTED_BASELINE_HEAD:
        _assert(
            _changed_paths() == EXPECTED_SURFACE,
            f"unexpected Control B candidate surface: {sorted(_changed_paths())}",
        )
        repository_mode = "candidate"
    else:
        control_b_commit = _control_b_commit()
        _assert(control_b_commit is not None, "committed Control B not found")
        _assert(
            _git("rev-parse", f"{control_b_commit}^") == EXPECTED_BASELINE_HEAD,
            "Control B parent drift",
        )
        _assert(
            _git("show", "-s", "--format=%s", control_b_commit)
            == EXPECTED_CONTROL_B_SUBJECT,
            "Control B subject drift",
        )
        _assert(
            _commit_surface(control_b_commit) == EXPECTED_SURFACE,
            "Control B committed exact surface drift",
        )
        _assert(
            _is_ancestor(control_b_commit, head),
            "Control B commit is not an ancestor of HEAD",
        )
        repository_mode = "committed"

    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE_HEAD}^")
        == EXPECTED_CORRUPT_CORRECTIVE_COMMIT,
        "encoding repair parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE_HEAD)
        == EXPECTED_REPAIR_SUBJECT,
        "encoding repair subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE_HEAD) == EXPECTED_CORRECTIVE_SURFACE,
        "encoding repair exact surface drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_CORRUPT_CORRECTIVE_COMMIT}^")
        == EXPECTED_CONTROL_A_COMMIT,
        "corrupt corrective parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_CORRUPT_CORRECTIVE_COMMIT)
        == EXPECTED_CORRUPT_CORRECTIVE_SUBJECT,
        "corrupt corrective subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_CORRUPT_CORRECTIVE_COMMIT)
        == EXPECTED_CORRECTIVE_SURFACE,
        "corrupt corrective exact surface drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_CONTROL_A_COMMIT)
        == EXPECTED_CONTROL_A_SUBJECT,
        "Control A subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_CONTROL_A_COMMIT) == EXPECTED_CONTROL_A_SURFACE,
        "Control A exact surface drift",
    )
    for relative_path in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
    ):
        _assert_repair_and_candidate_bytes(relative_path)
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        _assert(
            "3048984092bba58baf6c3841b53d58ec4c02b7fc" not in text,
            f"synthetic lifecycle baseline remains: {relative_path}",
        )
        _assert(
            "baseline head: 6443e524d8bc4e32eb4d7e7ecba75e26244c9f10" in text,
            f"accepted lifecycle baseline missing: {relative_path}",
        )
        _assert(
            f"baseline head: {EXPECTED_CONTROL_D_COMMIT}" in text,
            f"Control A baseline drift: {relative_path}",
        )
    event_contract = (PROJECT_ROOT / "docs/v600_realtime_event_contract.md").read_bytes()
    event_source = _git_bytes(
        "show",
        f"{EXPECTED_CONTROL_A_COMMIT}:docs/v600_realtime_event_contract.md",
    )
    marker = b"<!-- FW-RT6-1c-B-REALTIME-EVENT-ENVELOPE:BEGIN -->"
    event_prefix, _ = event_contract.split(marker, 1)
    _assert(
        event_prefix == event_source.rstrip(b"\r\n") + b"\n\n",
        "Realtime event contract Control A base drift",
    )
    print(
        "[OK] Control A/corrupt-corrective/encoding-repair history and "
        f"Control B {repository_mode} contract match"
    )


def check_manifest_and_field_layout(framework) -> None:
    from framework.public_api import PUBLIC_API_NAMES

    _assert(len(PUBLIC_API_NAMES) == 114, "root-public count drift")
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    names = tuple(field.name for field in dataclasses.fields(framework.RealtimeEvent))
    _assert(
        names[:10] == (
            "type", "state", "previous_state", "turn_id", "session_id",
            "boundary", "public_error_code", "safe_message", "retryable",
            "public_metadata",
        ),
        "legacy RealtimeEvent field prefix drift",
    )
    _assert(
        names[10:] == (
            "sequence", "generation_id", "phase", "payload", "terminal",
            "timestamp", "monotonic_timestamp",
        ),
        "v6 RealtimeEvent field suffix drift",
    )
    _assert(
        tuple(item.value for item in framework.RealtimeEventType)
        == LEGACY_EVENT_VALUES + V6_EVENT_VALUES,
        "RealtimeEventType prefix/suffix value order drift",
    )
    print("[OK] accepted 114-name manifest and additive event field/type layout conform")


def check_identity_phase_and_payload(framework) -> None:
    generation = framework.GenerationId.new()
    payload = framework.TranscriptEventPayload(
        text="hello", is_final=True, confidence=0.8,
    )
    event = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TRANSCRIPT_FINAL,
        state=framework.RealtimeState.TRANSCRIBING,
        sequence=1,
        generation_id=str(generation),
        phase="transcribing",
        payload=payload,
    )
    _assert(event.sequence is framework.EventSequence.first() or event.sequence == framework.EventSequence.first(), "sequence normalization drift")
    _assert(type(event.sequence) is framework.EventSequence, "sequence type drift")
    _assert(type(event.generation_id) is framework.GenerationId, "generation type drift")
    _assert(event.generation_id == generation, "generation value drift")
    _assert(event.phase is framework.RealtimePhase.TRANSCRIBING, "phase normalization drift")
    _assert(event.payload is payload, "typed payload preservation drift")
    _assert(event.terminal is False, "progress event terminal inference drift")

    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", sequence=True), TypeError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", sequence=0), ValueError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", sequence=1.0), TypeError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", generation_id=str(framework.SessionId.new())), ValueError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", generation_id="legacy-generation"), ValueError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", phase="completed"), ValueError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", payload={"text": "raw"}), TypeError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", payload=RuntimeError("raw")), TypeError)
    print("[OK] sequence, generation, phase, and typed payload normalization conform")


def check_terminal_and_timestamp_contract(framework) -> None:
    terminal_types = {
        framework.RealtimeEventType.TURN_COMPLETED,
        framework.RealtimeEventType.TURN_INTERRUPTED,
        framework.RealtimeEventType.TURN_CANCELLED,
        framework.RealtimeEventType.TURN_FAILED,
        framework.RealtimeEventType.TURN_REJECTED,
        framework.RealtimeEventType.SESSION_CLOSED,
    }
    for event_type in framework.RealtimeEventType:
        event = framework.RealtimeEvent(type=event_type, state="completed" if event_type in terminal_types else "idle")
        _assert(event.terminal is (event_type in terminal_types), f"terminal inference drift: {event_type}")

    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.completed", state="completed", terminal=False), ValueError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", terminal=True), ValueError)
    _expect_failure(lambda: framework.RealtimeEvent(type="realtime.turn.started", state="listening", terminal=1), TypeError)

    event = framework.RealtimeEvent(
        type="realtime.turn.started", state="listening",
        timestamp=0, monotonic_timestamp=1.25,
    )
    _assert(event.timestamp == 0.0 and type(event.timestamp) is float, "timestamp normalization drift")
    _assert(event.monotonic_timestamp == 1.25, "monotonic timestamp drift")
    for value, error in ((True, TypeError), (-1, ValueError), (math.nan, ValueError), (math.inf, ValueError)):
        _expect_failure(lambda value=value: framework.RealtimeEvent(type="realtime.turn.started", state="listening", timestamp=value), error)
    print("[OK] deterministic terminal inference and optional timestamp validation conform")


def check_serialization_and_legacy_compatibility(framework) -> None:
    generation = framework.GenerationId.new()
    event = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_COMPLETED,
        state=framework.RealtimeState.COMPLETED,
        previous_state=framework.RealtimeState.SPEAKING,
        session_id=framework.SessionId.new(),
        turn_id=framework.TurnId.new(),
        sequence=2,
        generation_id=generation,
        phase=framework.RealtimePhase.SPEAKING,
        payload=framework.LifecycleEventPayload(outcome="completed"),
        timestamp=10,
        monotonic_timestamp=5,
        public_metadata={"token": "secret", "visible": "ok"},
    )
    legacy = event.as_dict()
    _assert(isinstance(legacy, MappingProxyType), "legacy mapping mutability drift")
    _assert(
        tuple(legacy.keys()) == (
            "type", "state", "previous_state", "turn_id", "session_id",
            "boundary", "public_error_code", "safe_message", "retryable",
            "public_metadata",
        ),
        "legacy as_dict keys drift",
    )
    _assert("sequence" not in legacy and "payload" not in legacy, "v6 fields leaked into legacy mapping")
    _assert(legacy["public_metadata"]["token"] == "<redacted>", "legacy metadata redaction drift")

    v6 = event.as_v6_dict()
    _assert(isinstance(v6, MappingProxyType), "v6 mapping must be immutable")
    _assert(
        tuple(v6.keys()) == (
            "type", "state", "previous_state", "session_id", "turn_id",
            "generation_id", "sequence", "phase", "payload", "terminal",
            "timestamp", "monotonic_timestamp", "boundary",
            "public_error_code", "safe_message", "retryable", "public_metadata",
        ),
        "as_v6_dict key order drift",
    )
    _assert(v6["generation_id"] == str(generation), "v6 generation serialization drift")
    _assert(v6["sequence"] == 2, "v6 sequence serialization drift")
    _assert(v6["phase"] == "speaking", "v6 phase serialization drift")
    _assert(v6["payload"]["kind"] == "lifecycle", "v6 payload serialization drift")
    _assert(v6["terminal"] is True, "v6 terminal serialization drift")
    print("[OK] legacy serialization stays stable and canonical v6 serialization is complete")


def check_truthful_deferrals_and_import_safety(framework) -> bool:
    session_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    _assert("EventSequence.first" not in session_source, "session sequence ownership adopted prematurely")
    _assert("GenerationId.new" not in session_source, "session generation ownership adopted prematurely")
    _assert("as_v6_dict" not in session_source, "canonical event emission adopted prematurely")
    _assert("terminal_registry" not in session_source, "terminal registry adopted prematurely")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider SDK imported by event envelope")

    adapter_present = all(
        hasattr(framework.RealtimeEvent, name)
        for name in ("to_v5", "as_v5_dict")
    )
    contract = (PROJECT_ROOT / "docs/v600_realtime_event_contract.md").read_text(encoding="utf-8")
    public = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    integration = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    for text in (contract, public, integration):
        _assert("FW-RT6-1c-B-REALTIME-EVENT-ENVELOPE" in text, "Control B docs marker missing")
        _assert("terminal registry / exactly-once suppression: NOT IMPLEMENTED" in text, "terminal deferral missing")
    print(
        "[OK] session ordering, terminal registry, and provider work remain "
        "deferred; later-control v5 adapter presence is compatible"
    )
    return adapter_present


def main() -> None:
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    check_repository_contract()
    check_manifest_and_field_layout(framework)
    check_identity_phase_and_payload(framework)
    check_terminal_and_timestamp_contract(framework)
    check_serialization_and_legacy_compatibility(framework)
    adapter_present = check_truthful_deferrals_and_import_safety(framework)
    _assert(not (FORBIDDEN_IMPORTS & (set(sys.modules) - before)), "provider module imported during smoke")
    print("v600_realtime_event_envelope_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 7")
    print("v600_root_public_name_count: 114")
    print("v600_realtime_event_legacy_prefix_preserved: True")
    print("v600_realtime_event_v6_envelope_adopted: True")
    print("v600_event_sequence_type_adopted: True")
    print("v600_generation_id_type_adopted: True")
    print("v600_realtime_phase_field_adopted: True")
    print("v600_typed_payload_field_adopted: True")
    print("v600_terminal_flag_identifiable: True")
    print("v600_automatic_sequence_generation_wiring: False")
    print("v600_realtime_session_ordered_emission_adopted: False")
    print(f"v600_v5_mapping_adapter_currently_present: {adapter_present}")
    print("v600_v5_mapping_adapter_adopted_by_control_b: False")
    print("v600_terminal_registry_implemented: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1c Control C")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1c Control B realtime event envelope smoke passed")


if __name__ == "__main__":
    main()
