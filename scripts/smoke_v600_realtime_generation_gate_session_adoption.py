"""FW-RT6-2d Control B RealtimeSession generation-gate adoption smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or DRC repository operation occurs.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "e3f5ce7088596e1f2ceaa3c504a16b35c47863b8"
EXPECTED_BASELINE_PARENT = "498e27ec264b0120f1f94a859cff6462bdfc7acd"
EXPECTED_BASELINE_SUBJECT = "feat/test: add realtime generation gate primitives"
EXPECTED_BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_generation_gate_contract.md",
    "framework/realtime_generation_gate.py",
    "scripts/smoke_v600_realtime_generation_gate_primitives.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_generation_gate_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_generation_gate_primitives.py",
    "scripts/smoke_v600_realtime_generation_gate_session_adoption.py",
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
GENERATION_DIAGNOSTIC_KEYS = {
    "generation_start_count",
    "generation_advance_count",
    "accepted_completion_count",
    "stale_completion_count",
    "active_generation_count",
    "registry_size",
}
EVENT_DIAGNOSTIC_KEYS = {
    "emitted_event_count",
    "callback_error_count",
    "slow_callback_count",
    "history_overflow_count",
    "rejected_after_close_count",
    "subscriber_count",
    "history_limit",
}
TERMINAL_DIAGNOSTIC_KEYS = {
    "terminal_commit_count",
    "duplicate_terminal_count",
    "terminal_regression_count",
    "late_non_terminal_count",
    "registry_size",
}


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
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == EXPECTED_BASELINE_SURFACE,
        "accepted Control A surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted Control A baseline and exact six-file Control B surface conform")


def check_lazy_internal_adoption() -> tuple[Any, Any, Any]:
    import framework

    _assert(len(framework.__all__) == 121, "root-public name count drift")
    _assert(
        "framework.realtime_generation_gate" not in sys.modules,
        "root import eagerly loaded the internal generation gate",
    )
    for name in (
        "RealtimeGenerationGate",
        "RealtimeStageCompletionEnvelope",
        "GenerationAdvanceReason",
        "StaleCompletionReason",
        "GenerationAdmissionDecision",
    ):
        _assert(name not in framework.__dict__, f"internal symbol leaked: {name}")
        _assert(name not in framework.__all__, f"internal export leaked: {name}")

    session = framework.create_realtime_session()
    _assert(
        "framework.realtime_generation_gate" in sys.modules,
        "session construction did not lazily load the generation gate",
    )

    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )

    _assert(
        isinstance(session._generation_gate, RealtimeGenerationGate),
        "RealtimeSession does not own a generation gate",
    )
    _assert(
        set(session.generation_diagnostics) == GENERATION_DIAGNOSTIC_KEYS,
        "generation diagnostics keys drift",
    )
    try:
        session.generation_diagnostics["stale_completion_count"] = 0
    except TypeError:
        pass
    else:
        raise AssertionError("generation diagnostics are mutable")

    _assert(
        set(session.event_diagnostics) == EVENT_DIAGNOSTIC_KEYS,
        "event diagnostics keys changed",
    )
    _assert(
        set(session.terminal_diagnostics) == TERMINAL_DIAGNOSTIC_KEYS,
        "terminal diagnostics keys changed",
    )
    _assert(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == ("project_root", "public_metadata", "real_runtime_enabled"),
        "RealtimeSession factory signature changed",
    )
    session.close()
    print("[OK] session lazily owns the internal gate without root-public drift")
    return (
        framework,
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )


def check_source_contract() -> None:
    path = PROJECT_ROOT / "framework" / "realtime_session.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for phrase in (
        "if TYPE_CHECKING:",
        "RealtimeGenerationGate()",
        "def generation_diagnostics(",
        "def _start_turn_generation(",
        "def _advance_generation(",
        "def _apply_stage_completion(",
        "def _emit_stale_completion_diagnostic(",
        '"turn_terminal"',
        '"interrupt"',
        '"cancel"',
        '"session_closed"',
        "RealtimeEventType.STALE_RESULT_DROPPED",
        'code="stale_stage_completion"',
        'safe_message="Stale realtime stage completion was dropped."',
    ):
        _assert(phrase in source, f"session adoption source phrase missing: {phrase}")

    _assert(
        "self._active_generation_id = GenerationId.new()" not in source,
        "run_turn still creates an unmanaged generation",
    )
    terminal_start = source.index("    def _commit_terminal_result(")
    terminal_end = source.index("    @contextmanager", terminal_start)
    terminal_source = source[terminal_start:terminal_end]
    _assert(
        terminal_source.index("self._advance_generation(")
        < terminal_source.index("self._transition("),
        "terminal generation must retire before terminal event delivery",
    )

    top_level_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_level_imports.add(node.module or "")
    _assert(
        "framework.realtime_generation_gate" not in top_level_imports,
        "generation gate must remain a lazy session-construction import",
    )
    print("[OK] session source centralizes generation admission and lazy ownership")


def _start_internal_generation(
    session: Any,
    framework: Any,
    turn_id: Any,
) -> Any:
    with session._serialized_operation():
        generation_id = session._start_turn_generation(turn_id)
        session._state = framework.RealtimeState.LISTENING
        session._phase = framework.RealtimePhase.LISTENING
        return generation_id


def check_normal_turn_terminal_retirement(
    framework: Any,
    RealtimeStageCompletionEnvelope: Any,
    StaleCompletionReason: Any,
) -> None:
    events = []
    legacy_events = []
    session = framework.create_realtime_session()
    session.on_event(events.append)
    session.on_legacy_event(legacy_events.append)

    result = session.run_turn(input_text="generation adoption")
    turn_events = [event for event in events if event.turn_id == result.turn_id]
    generation_ids = {event.generation_id for event in turn_events}

    _assert(len(generation_ids) == 1, "normal turn events do not share one generation")
    generation_id = next(iter(generation_ids))
    _assert(generation_id is not None, "normal turn generation is missing")
    terminal_events = [
        event
        for event in turn_events
        if event.type is framework.RealtimeEventType.TURN_COMPLETED
    ]
    _assert(len(terminal_events) == 1, "normal turn terminal event count drift")
    _assert(
        terminal_events[0].generation_id == generation_id,
        "terminal event lost the turn generation",
    )
    _assert(
        session.generation_diagnostics["generation_start_count"] == 1,
        "normal turn generation start count drift",
    )
    _assert(
        session.generation_diagnostics["generation_advance_count"] == 1,
        "normal turn terminal did not retire the generation",
    )
    _assert(
        session.generation_diagnostics["active_generation_count"] == 0,
        "normal turn retained an active gate generation",
    )

    delivered = []
    state_before = session.state
    phase_before = session.phase
    terminal_before = dict(session.terminal_diagnostics)
    legacy_before = len(legacy_events)
    stale = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=result.turn_id,
            generation_id=generation_id,
            stage="text_generation",
            value={"text": "late"},
        ),
        deliver=delivered.append,
    )
    _assert(not stale.accepted, "terminal-retired completion was accepted")
    _assert(
        stale.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
        "terminal-retired stale reason drift",
    )
    _assert(
        stale.retired_by.value == "turn_terminal",
        "terminal retirement reason drift",
    )
    _assert(not delivered, "terminal-retired value was delivered")
    _assert(session.state is state_before, "stale diagnostic changed session state")
    _assert(session.phase is phase_before, "stale diagnostic changed session phase")
    _assert(
        dict(session.terminal_diagnostics) == terminal_before,
        "stale diagnostic changed terminal diagnostics",
    )
    stale_events = [
        event
        for event in session.event_history
        if event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED
    ]
    _assert(len(stale_events) == 1, "terminal stale diagnostic count drift")
    diagnostic = stale_events[0]
    _assert(diagnostic.turn_id == result.turn_id, "stale diagnostic turn drift")
    _assert(diagnostic.generation_id == generation_id, "stale diagnostic generation drift")
    _assert(diagnostic.payload.code == "stale_stage_completion", "diagnostic code drift")
    _assert(diagnostic.payload.drop_reason == "retired_generation", "drop reason drift")
    _assert(
        diagnostic.public_metadata["retired_by"] == "turn_terminal",
        "terminal retired_by metadata drift",
    )
    _assert(
        len(legacy_events) == legacy_before,
        "v6-only stale diagnostic leaked to legacy callbacks",
    )
    session.close()
    print("[OK] normal turn shares one generation and retires before stale admission")


def check_current_new_turn_unknown_and_mismatch(
    framework: Any,
    GenerationAdvanceReason: Any,
    RealtimeStageCompletionEnvelope: Any,
    StaleCompletionReason: Any,
) -> None:
    session = framework.create_realtime_session()
    events = []
    legacy_events = []
    session.on_event(events.append)
    session.on_legacy_event(legacy_events.append)

    turn_a = framework.TurnId.new()
    generation_a = _start_internal_generation(session, framework, turn_a)

    delivered = []
    accepted = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_a,
            generation_id=generation_a,
            stage="response_delta",
            value="accepted",
        ),
        deliver=delivered.append,
    )
    _assert(accepted.accepted, "current completion was rejected")
    _assert(delivered == ["accepted"], "current completion delivery drift")
    _assert(
        not any(
            event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED
            for event in events
        ),
        "current completion emitted a stale diagnostic",
    )

    turn_b = framework.TurnId.new()
    with session._serialized_operation():
        generation_b = session._start_turn_generation(turn_b)

    delivered.clear()
    retired = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_a,
            generation_id=generation_a,
            stage="response_delta",
            value="old response",
        ),
        deliver=delivered.append,
    )
    _assert(not retired.accepted, "new-turn retired response was accepted")
    _assert(
        retired.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
        "new-turn retired reason drift",
    )
    _assert(
        retired.retired_by is GenerationAdvanceReason.NEW_TURN,
        "new-turn retirement reason was not retained",
    )
    _assert(not delivered, "old response delta was delivered")

    unknown = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_b,
            generation_id=framework.GenerationId.new(),
            stage="voice_output",
            value="unknown artifact",
        ),
        deliver=delivered.append,
    )
    _assert(
        unknown.stale_reason is StaleCompletionReason.UNKNOWN_GENERATION,
        "unknown generation reason drift",
    )

    mismatch = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_a,
            generation_id=generation_b,
            stage="motion",
            value="wrong turn",
        ),
        deliver=delivered.append,
    )
    _assert(
        mismatch.stale_reason is StaleCompletionReason.TURN_MISMATCH,
        "turn mismatch reason drift",
    )
    _assert(not delivered, "stale completion value was delivered")

    diagnostics = [
        event
        for event in events
        if event.type is framework.RealtimeEventType.STALE_RESULT_DROPPED
    ]
    _assert(len(diagnostics) == 3, "open-session stale diagnostic count drift")
    _assert(
        [event.payload.drop_reason for event in diagnostics]
        == ["retired_generation", "unknown_generation", "turn_mismatch"],
        "typed stale diagnostic ordering drift",
    )
    _assert(
        not any(
            event.type
            in {
                framework.RealtimeEventType.RESPONSE_DELTA,
                framework.RealtimeEventType.AUDIO_AVAILABLE,
                framework.RealtimeEventType.MOTION_COMPLETED,
            }
            for event in events
        ),
        "original stale stage event was delivered",
    )
    _assert(not legacy_events, "stale diagnostics reached legacy callbacks")
    session.close()
    print("[OK] current, new-turn, unknown, and mismatch completion ingress conforms")


def check_interrupt_cancel_and_unrelated_turn(
    framework: Any,
    GenerationAdvanceReason: Any,
    RealtimeStageCompletionEnvelope: Any,
    StaleCompletionReason: Any,
) -> None:
    for method_name, expected_reason in (
        ("interrupt", GenerationAdvanceReason.INTERRUPT),
        ("cancel_current_turn", GenerationAdvanceReason.CANCEL),
    ):
        session = framework.create_realtime_session()
        turn_id = framework.TurnId.new()
        generation_id = _start_internal_generation(session, framework, turn_id)

        result = getattr(session, method_name)()
        _assert(
            result.outcome is framework.InterruptOutcome.NOT_IMPLEMENTED,
            f"{method_name} public outcome changed",
        )
        decision = session._apply_stage_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=turn_id,
                generation_id=generation_id,
                stage="voice_output",
                value="late audio",
            ),
            deliver=lambda value: (_ for _ in ()).throw(
                AssertionError(f"{method_name} delivered stale audio: {value}")
            ),
        )
        _assert(
            decision.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
            f"{method_name} stale reason drift",
        )
        _assert(
            decision.retired_by is expected_reason,
            f"{method_name} retirement reason drift",
        )
        session.close()

    no_active = framework.create_realtime_session()
    before = dict(no_active.generation_diagnostics)
    result = no_active.interrupt()
    _assert(
        result.outcome is framework.InterruptOutcome.NO_ACTIVE_TURN,
        "no-active interrupt outcome changed",
    )
    _assert(
        dict(no_active.generation_diagnostics) == before,
        "no-active interrupt advanced generation diagnostics",
    )
    no_active.close()

    unrelated = framework.create_realtime_session()
    active_turn = framework.TurnId.new()
    active_generation = _start_internal_generation(
        unrelated,
        framework,
        active_turn,
    )
    explicit_turn = framework.TurnId.new()
    explicit = unrelated.interrupt(
        framework.InterruptRequest.user_barge_in(turn_id=explicit_turn)
    )
    _assert(
        explicit.outcome is framework.InterruptOutcome.NOT_IMPLEMENTED,
        "unrelated explicit interrupt outcome changed",
    )
    _assert(
        unrelated._generation_gate.current_generation_id == active_generation,
        "unrelated explicit interrupt retired the current generation",
    )
    _assert(
        unrelated.generation_diagnostics["generation_advance_count"] == 0,
        "unrelated explicit interrupt advanced the gate",
    )
    unrelated.close()
    print("[OK] interrupt, cancel, no-active, and unrelated-turn advance rules conform")


def check_close_requested_and_post_close_observability(
    framework: Any,
    RealtimeStageCompletionEnvelope: Any,
    StaleCompletionReason: Any,
) -> None:
    session = framework.create_realtime_session()
    events = []
    legacy_events = []
    session.on_event(events.append)
    session.on_legacy_event(legacy_events.append)
    turn_id = framework.TurnId.new()
    generation_id = _start_internal_generation(session, framework, turn_id)

    delivered = []
    with session._serialized_operation():
        session.close()
        _assert(session._close_requested, "close was not deferred inside operation")
        event_count = len(events)
        decision = session._apply_stage_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=turn_id,
                generation_id=generation_id,
                stage="text_generation",
                value="after close request",
            ),
            deliver=delivered.append,
        )
        _assert(
            decision.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
            "close-requested completion stale reason drift",
        )
        _assert(
            decision.retired_by.value == "session_closed",
            "close retirement reason drift",
        )
        _assert(not delivered, "close-requested completion was delivered")
        _assert(
            len(events) == event_count,
            "close-requested stale diagnostic event was emitted",
        )

    _assert(session.is_closed, "deferred close did not complete")
    _assert(
        [event.type for event in events]
        == [framework.RealtimeEventType.SESSION_CLOSED],
        "close boundary emitted unexpected events",
    )
    _assert(
        [event.type for event in legacy_events]
        == [framework.RealtimeEventType.SESSION_CLOSED],
        "legacy close event count drift",
    )

    post_close_event_count = len(events)
    stale_before = session.generation_diagnostics["stale_completion_count"]
    post_close = session._apply_stage_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_id,
            generation_id=generation_id,
            stage="voice_output",
            value="post close",
        ),
        deliver=delivered.append,
    )
    _assert(not post_close.accepted, "post-close completion was accepted")
    _assert(not delivered, "post-close completion was delivered")
    _assert(
        len(events) == post_close_event_count,
        "post-close stale diagnostic event was emitted",
    )
    _assert(
        session.generation_diagnostics["stale_completion_count"]
        == stale_before + 1,
        "post-close stale drop was not count-observable",
    )

    advance_before = session.generation_diagnostics["generation_advance_count"]
    session.close()
    _assert(
        session.generation_diagnostics["generation_advance_count"] == advance_before,
        "duplicate close advanced generation diagnostics",
    )
    print("[OK] close-requested and post-close stale completion behavior conforms")


def check_docs_and_safety() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_realtime_generation_gate_contract.md",
    ):
        normalized = " ".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8").split()
        )
        for phrase in (
            "FW-RT6-2d-A-GENERATION-GATE-PRIMITIVES:BEGIN",
            "FW-RT6-2d-B-REALTIME-SESSION-GENERATION-ADOPTION:BEGIN",
            "exact change surface: 6 files",
            "STALE_RESULT_DROPPED",
            "stale_stage_completion",
            "generation_diagnostics",
            "Control C race and VTS alignment: NOT_AUTHORIZED",
        ):
            _assert(phrase in normalized, f"Control B contract missing {phrase}: {relative}")

    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] Control B docs and provider/runtime safety conform")


def main() -> None:
    check_repository_contract()
    (
        framework,
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    ) = check_lazy_internal_adoption()
    check_source_contract()
    check_normal_turn_terminal_retirement(
        framework,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )
    check_current_new_turn_unknown_and_mismatch(
        framework,
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )
    check_interrupt_cancel_and_unrelated_turn(
        framework,
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )
    check_close_requested_and_post_close_observability(
        framework,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )
    check_docs_and_safety()

    print("v600_rt6_2d_control_b_status: implemented-awaiting-review")
    print("v600_rt6_2d_control_b_exact_change_surface_count: 6")
    print("v600_rt6_2d_control_b_control_a_regression_updated: True")
    print("v600_rt6_2d_control_b_generation_gate_lazy_session_owned: True")
    print("v600_rt6_2d_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_2d_control_b_normal_turn_generation_shared: True")
    print("v600_rt6_2d_control_b_terminal_retired_before_callback: source-order-verified")
    print("v600_rt6_2d_control_b_current_completion_delivered: True")
    print("v600_rt6_2d_control_b_stale_completion_delivered: False")
    print("v600_rt6_2d_control_b_stale_diagnostic_typed: True")
    print("v600_rt6_2d_control_b_stale_diagnostic_legacy_projection: None")
    print("v600_rt6_2d_control_b_close_requested_stale_event: False")
    print("v600_rt6_2d_control_b_post_close_stale_count_observable: True")
    print("v600_rt6_2d_control_b_event_diagnostics_changed: False")
    print("v600_rt6_2d_control_b_terminal_diagnostics_changed: False")
    print("v600_rt6_2d_control_b_factory_signature_changed: False")
    print("v600_rt6_2d_control_b_public_reset_added: False")
    print("v600_rt6_2d_control_b_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2d_control_c_authorized: False")
    print("[OK] FW-RT6-2d Control B RealtimeSession generation adoption conforms")


if __name__ == "__main__":
    main()
