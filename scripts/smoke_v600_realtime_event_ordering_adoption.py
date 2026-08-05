"""FW-RT6-1c Control D ordered RealtimeSession event adoption smoke.

Offline-safe: validates canonical/legacy callback routing, session-lifetime event
sequence allocation, per-admitted-turn generation identity, typed payloads,
automatic timestamps, and truthful runtime deferrals.
"""

from __future__ import annotations

import importlib
import math
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "007e1577a18c92a1dafdf9ede814b97dc2d0a05c"
EXPECTED_BASELINE_SUBJECT = "feat/test: add realtime event v5 adapter"
EXPECTED_CONTROL_D_SUBJECT = "refactor/test: adopt ordered realtime events"
EXPECTED_ROOT_PUBLIC_COUNT = 114
EXPECTED_SURFACE = {
    "framework/realtime.py",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_event_ordering_adoption.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "docs/v600_realtime_event_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
FORBIDDEN_IMPORTS = {
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "speech_recognition", "pyaudio", "google.genai", "xai_sdk",
}
CANONICAL_TURN_ORDER = (
    "TURN_STARTED",
    "LISTENING_STARTED",
    "LISTENING_COMPLETED",
    "TRANSCRIPT_FINAL",
    "RESPONSE_STARTED",
    "RESPONSE_COMPLETED",
    "SYNTHESIS_STARTED",
    "SYNTHESIS_COMPLETED",
    "TURN_COMPLETED",
)
LEGACY_TURN_ORDER = (
    "TURN_STARTED",
    "VOICE_INPUT_STARTED",
    "VOICE_INPUT_COMPLETED",
    "TEXT_CHAT_STARTED",
    "TEXT_CHAT_COMPLETED",
    "VOICE_OUTPUT_STARTED",
    "VOICE_OUTPUT_COMPLETED",
    "TURN_COMPLETED",
)
PAYLOAD_TYPES = (
    "LifecycleEventPayload",
    "LifecycleEventPayload",
    "LifecycleEventPayload",
    "TranscriptEventPayload",
    "ResponseEventPayload",
    "ResponseEventPayload",
    "SynthesisEventPayload",
    "SynthesisEventPayload",
    "LifecycleEventPayload",
)
DOC_MARKER = "FW-RT6-1c-D-ORDERED-EVENT-ADOPTION"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _git_available() -> bool:
    return _git("rev-parse", "--is-inside-work-tree", check=False).returncode == 0


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).stdout.splitlines()
            if line.strip()
        )
    return paths


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).stdout.splitlines()
        if line.strip()
    }


def _check_git_checkpoint() -> bool:
    if not _git_available():
        print("v600_rt6_1c_control_d_git_checkpoint_checked: False / ARCHIVE_SOURCE")
        return False

    head = _git("rev-parse", "HEAD").stdout.strip()
    subject = _git("show", "-s", "--format=%s", "HEAD").stdout.strip()
    changed = _changed_paths()

    if head == EXPECTED_BASELINE_HEAD:
        _assert(subject == EXPECTED_BASELINE_SUBJECT, "baseline subject drift")
        _assert(changed == EXPECTED_SURFACE, f"Control D exact surface drift: {sorted(changed)}")
        print("v600_rt6_1c_control_d_status: implemented-awaiting-review")
        print("v600_rt6_1c_control_d_exact_change_surface: True")
        return True

    parent = _git("rev-parse", "HEAD^").stdout.strip()
    _assert(parent == EXPECTED_BASELINE_HEAD, "Control D parent drift")
    _assert(subject == EXPECTED_CONTROL_D_SUBJECT, "Control D commit subject drift")
    _assert(_commit_surface(head) == EXPECTED_SURFACE, "Control D committed surface drift")
    _assert(not changed, "working tree must be clean after Control D commit")
    print("v600_rt6_1c_control_d_status: committed-awaiting-acceptance")
    print("v600_rt6_1c_control_d_exact_change_surface: True")
    return True


def _check_docs() -> None:
    for relative in (
        "docs/v600_realtime_event_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8", errors="strict")
        _assert(DOC_MARKER in text, f"missing Control D marker: {relative}")
        _assert("on_legacy_event" in text, f"missing legacy callback contract: {relative}")
        _assert("EventSequence" in text, f"missing ordering contract: {relative}")


def _import_framework_safely():
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = {name for name in loaded if name.split(".", 1)[0] in FORBIDDEN_IMPORTS}
    _assert(not forbidden, f"provider/runtime modules imported: {sorted(forbidden)}")
    _assert(len(framework.__all__) == EXPECTED_ROOT_PUBLIC_COUNT, "root-public name count drift")
    return framework


def _names(events) -> tuple[str, ...]:
    return tuple(event.type.name for event in events)


def _assert_common_envelope(framework, events) -> None:
    _assert(events, "no events emitted")
    _assert(
        [int(event.sequence) for event in events] == list(range(1, len(events) + 1)),
        "EventSequence must start at 1 and remain session-monotonic",
    )
    _assert(
        all(isinstance(event.sequence, framework.EventSequence) for event in events),
        "runtime events must expose EventSequence",
    )
    _assert(
        all(event.timestamp is not None and math.isfinite(event.timestamp) and event.timestamp >= 0 for event in events),
        "runtime events must expose finite non-negative timestamps",
    )
    _assert(
        all(
            event.monotonic_timestamp is not None
            and math.isfinite(event.monotonic_timestamp)
            and event.monotonic_timestamp >= 0
            for event in events
        ),
        "runtime events must expose finite non-negative monotonic timestamps",
    )
    monotonic_values = [event.monotonic_timestamp for event in events]
    _assert(monotonic_values == sorted(monotonic_values), "monotonic timestamps regressed")


def _assert_projection(canonical, legacy) -> None:
    mapped = [event.to_v5() for event in canonical]
    expected = [event for event in mapped if event is not None]
    _assert(len(expected) == len(legacy), "legacy callback projection count drift")
    for projected, observed in zip(expected, legacy):
        _assert(projected.type is observed.type, "legacy projected type drift")
        _assert(projected.sequence == observed.sequence, "legacy projected sequence drift")
        _assert(projected.generation_id == observed.generation_id, "legacy projected generation drift")
        _assert(projected.timestamp == observed.timestamp, "legacy projected timestamp drift")
        _assert(projected.monotonic_timestamp == observed.monotonic_timestamp, "legacy monotonic timestamp drift")
        _assert(projected.payload is observed.payload, "legacy typed payload identity drift")


def _check_ordered_session(framework) -> None:
    canonical = []
    legacy = []
    session = framework.create_realtime_session()
    session.on_event(canonical.append)
    session.on_legacy_event(legacy.append)

    created = session.emit_created()
    _assert(created.type is framework.RealtimeEventType.SESSION_STARTED, "session start must be canonical")
    _assert(created.generation_id is None, "session start generation must be None")
    _assert(legacy[-1].type is framework.RealtimeEventType.SESSION_CREATED, "session start legacy projection drift")

    first_start = len(canonical)
    first_result = session.run_turn(input_text="fixture-alpha")
    first_events = canonical[first_start:]
    first_legacy_start = 1
    first_legacy = legacy[first_legacy_start:]
    _assert(first_result.outcome is framework.TurnOutcome.COMPLETED, "first turn result drift")
    _assert(_names(first_events) == CANONICAL_TURN_ORDER, "canonical completed-turn order drift")
    _assert(_names(first_legacy) == LEGACY_TURN_ORDER, "legacy completed-turn order drift")
    _assert(
        tuple(type(event.payload).__name__ for event in first_events) == PAYLOAD_TYPES,
        "canonical typed payload category drift",
    )
    first_generation = first_events[0].generation_id
    _assert(isinstance(first_generation, framework.GenerationId), "first turn generation missing")
    _assert(all(event.generation_id == first_generation for event in first_events), "first turn generation changed")
    _assert(first_events[-1].terminal is True, "turn completed must be terminal")
    _assert(all(not event.terminal for event in first_events[:-1]), "non-terminal turn event marked terminal")

    second_start = len(canonical)
    second_legacy_start = len(legacy)
    second_result = session.run_turn(input_text="fixture-beta")
    second_events = canonical[second_start:]
    second_legacy = legacy[second_legacy_start:]
    _assert(second_result.outcome is framework.TurnOutcome.COMPLETED, "second turn result drift")
    _assert(_names(second_events) == CANONICAL_TURN_ORDER, "second canonical turn order drift")
    _assert(_names(second_legacy) == LEGACY_TURN_ORDER, "second legacy turn order drift")
    second_generation = second_events[0].generation_id
    _assert(isinstance(second_generation, framework.GenerationId), "second turn generation missing")
    _assert(second_generation != first_generation, "GenerationId must change per admitted turn")
    _assert(all(event.generation_id == second_generation for event in second_events), "second turn generation changed")

    session.close()
    _assert(canonical[-1].type is framework.RealtimeEventType.SESSION_CLOSED, "session close type drift")
    _assert(canonical[-1].generation_id is None, "session close generation must be None")

    rejected_start = len(canonical)
    rejected_legacy_start = len(legacy)
    closed_result = session.run_turn(input_text="fixture-rejected")
    rejected = canonical[rejected_start:]
    rejected_legacy = legacy[rejected_legacy_start:]
    _assert(closed_result.outcome is framework.TurnOutcome.CLOSED, "closed result drift")
    _assert(_names(rejected) == ("TURN_REJECTED",), "closed session must emit turn rejected")
    _assert(rejected[0].generation_id is None, "rejected-before-admission generation must be None")
    _assert(rejected[0].terminal is True, "turn rejected must be terminal")
    _assert(_names(rejected_legacy) == ("TURN_FAILED",), "turn rejected legacy projection drift")

    _assert_common_envelope(framework, canonical)
    _assert_projection(canonical, legacy)
    _assert(all(event.session_id == session.info.session_id for event in canonical), "session correlation drift")


def _check_runtime_deferrals() -> None:
    source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    for forbidden in (
        "terminal_registry",
        "duplicate_terminal",
        "stale_result",
        "event_overflow_queue",
        "provider_partial_transcript",
        "response_delta_callback",
    ):
        _assert(forbidden not in source.lower(), f"deferred runtime feature adopted unexpectedly: {forbidden}")
    _assert("time.time()" in source, "automatic public timestamp allocation missing")
    _assert("time.monotonic()" in source, "automatic monotonic timestamp allocation missing")


def main() -> None:
    _check_git_checkpoint()
    _check_docs()
    framework = _import_framework_safely()
    _check_ordered_session(framework)
    _check_runtime_deferrals()
    print("v600_rt6_1c_control_d_root_public_names: 114 / unchanged")
    print("v600_rt6_1c_control_d_canonical_turn_events: 9")
    print("v600_rt6_1c_control_d_legacy_turn_events: 8")
    print("v600_rt6_1c_control_d_session_sequence_starts_at_one: True")
    print("v600_rt6_1c_control_d_sequence_resets_between_turns: False")
    print("v600_rt6_1c_control_d_generation_per_admitted_turn: True")
    print("v600_rt6_1c_control_d_session_or_rejected_generation: None")
    print("v600_rt6_1c_control_d_terminal_registry: False / deferred")
    print("v600_rt6_1c_control_d_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_1c_control_d_ordering_adoption: OK")


if __name__ == "__main__":
    main()
